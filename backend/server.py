import json
import re
import sys
import os
from contextlib import asynccontextmanager
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path

from config import (
    current_story_model, STORY_MODELS, STORY_PARAMS, current_story_params,
    load_config, save_config, pick_story_model, tune_story_params, CARD_CATEGORIES, INNER_FIELDS
)
from llm import ensure_models_loaded
from storage import (
    state, list_adventures, create_adventure, load_adventure, save_trunk,
    load_cards, write_card, delete_adventure, load_snapshot, restore_snapshot
)
from game import take_turn, take_turn_stream, librarian_batch


@asynccontextmanager
async def lifespan(app):
    ensure_models_loaded()
    yield


app = FastAPI(lifespan=lifespan)


class CreateAdventureBody(BaseModel):
    name: str
    premise: str


class TurnBody(BaseModel):
    action: str


class ModelBody(BaseModel):
    model_id: str


class ParamsBody(BaseModel):
    params: dict


class PlotBody(BaseModel):
    story_summary: str | None = None
    ai_instructions: str | None = None
    plot_essentials: str | None = None
    author_note: str | None = None


class CardBody(BaseModel):
    name: str
    category: str = "other"
    entry: str = ""
    card_state: str = ""
    triggers: list[str] = []
    notes: str = ""
    memory: list[str] = []
    goals: list[str] = []
    secrets: list[str] = []
    plans: list[str] = []
    thoughts: str = ""


class NewCardBody(BaseModel):
    name: str = "New Card"
    category: str = "other"


def _find_base(slug):
    for base, meta in list_adventures():
        if base.name == slug:
            return base
    raise HTTPException(status_code=404, detail=f"adventure '{slug}' not found")


@app.get("/api/adventures")
def get_adventures():
    return [{"slug": base.name, "meta": meta} for base, meta in list_adventures()]


@app.post("/api/adventures")
def post_adventure(body: CreateAdventureBody):
    try:
        base = create_adventure(body.name, body.premise)
        load_adventure(base)
        return {"slug": base.name}
    except FileExistsError:
        raise HTTPException(status_code=400, detail="adventure already exists")


@app.delete("/api/adventures/{slug}")
def delete_adv(slug: str):
    base = _find_base(slug)
    delete_adventure(base)
    return {"ok": True}


@app.post("/api/adventures/{slug}/load")
def load_adv(slug: str):
    base = _find_base(slug)
    load_adventure(base)
    return {"ok": True}


@app.post("/api/adventures/{slug}/turn")
def turn(slug: str, body: TurnBody):
    base = _find_base(slug)
    load_adventure(base)

    def event_gen():
        try:
            for event in take_turn_stream(body.action):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.post("/api/adventures/{slug}/save")
def save_adv(slug: str):
    _find_base(slug)
    librarian_batch()
    save_trunk()
    return {"ok": True}


@app.post("/api/adventures/{slug}/undo")
def undo(slug: str):
    base = _find_base(slug)
    load_adventure(base)
    if len(state.get("recent", [])) < 2:
        raise HTTPException(status_code=400, detail="nothing to undo")
    state["recent"] = state["recent"][:-2]
    state["meta"]["turn_counter"] = max(0, state["meta"]["turn_counter"] - 1)
    save_trunk()
    return {"ok": True, "recent": state["recent"]}


@app.post("/api/adventures/{slug}/retry")
def retry(slug: str):
    base = _find_base(slug)
    snap = load_snapshot()
    if not snap:
        raise HTTPException(status_code=400, detail="no snapshot available")

    load_adventure(base)
    restore_snapshot(snap)
    last_action = snap["last_action"]

    def event_gen():
        try:
            for event in take_turn_stream(last_action):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.get("/api/adventures/{slug}/plot")
def get_plot(slug: str):
    base = _find_base(slug)
    load_adventure(base)
    return {
        "story_summary": state["premise"],
        "ai_instructions": state.get("ai_instructions", ""),
        "plot_essentials": state.get("plot_essentials", ""),
        "author_note": state.get("author_note", ""),
    }


@app.patch("/api/adventures/{slug}/plot")
def patch_plot(slug: str, body: PlotBody):
    base = _find_base(slug)
    load_adventure(base)
    if body.story_summary is not None:
        state["premise"] = body.story_summary
    if body.ai_instructions is not None:
        state["ai_instructions"] = body.ai_instructions
    if body.plot_essentials is not None:
        state["plot_essentials"] = body.plot_essentials
    if body.author_note is not None:
        state["author_note"] = body.author_note
    save_trunk()
    return {"ok": True}


@app.get("/api/adventures/{slug}/cards")
def get_cards(slug: str):
    base = _find_base(slug)
    load_adventure(base)
    return [{k: v for k, v in c.items() if k != "_path"} for c in load_cards()]


@app.post("/api/adventures/{slug}/cards/new")
def create_card(slug: str, body: NewCardBody):
    from storage import kebab as _keb
    base = _find_base(slug)
    load_adventure(base)
    cat = body.category if body.category in CARD_CATEGORIES else "other"
    write_card(cat, {"name": body.name, "entry": "", "state": "", "triggers": [], "notes": ""})
    return {"ok": True, "slug": _keb(body.name), "category": cat}


def _safe_card_path(category: str, slug: str):
    if category not in CARD_CATEGORIES or not re.fullmatch(r'[a-z0-9-]+', slug):
        raise HTTPException(400, "invalid card identifier")
    base_dir = (state["dir"] / "cards" / category).resolve()
    path = (base_dir / f"{slug}.json").resolve()
    if not str(path).startswith(str(base_dir) + os.sep):
        raise HTTPException(400, "invalid card identifier")
    return path


@app.put("/api/adventures/{slug}/cards/{old_category}/{old_slug}")
def put_card(slug: str, old_category: str, old_slug: str, body: CardBody):
    from storage import kebab as _keb
    base = _find_base(slug)
    load_adventure(base)
    old_path = _safe_card_path(old_category, old_slug)
    new_cat = body.category if body.category in CARD_CATEGORIES else "other"
    card = {
        "name": body.name, "entry": body.entry, "state": body.card_state,
        "triggers": body.triggers, "notes": body.notes,
    }
    if new_cat == "characters":
        card.update({"memory": body.memory, "goals": body.goals,
                     "secrets": body.secrets, "plans": body.plans, "thoughts": body.thoughts})
    write_card(new_cat, card)
    new_slug = _keb(body.name)
    if (old_category != new_cat or old_slug != new_slug) and old_path.exists():
        old_path.unlink()
    return {"ok": True, "slug": new_slug, "category": new_cat}


@app.delete("/api/adventures/{slug}/cards/{category}/{card_slug}")
def delete_card_ep(slug: str, category: str, card_slug: str):
    base = _find_base(slug)
    load_adventure(base)
    path = _safe_card_path(category, card_slug)
    if path.exists():
        path.unlink()
    return {"ok": True}


@app.get("/api/adventures/{slug}/state")
def get_state(slug: str):
    base = _find_base(slug)
    load_adventure(base)
    return JSONResponse(json.loads(
        json.dumps({k: v for k, v in state.items() if k != "dir"}, default=str)
    ))


@app.get("/api/config")
def get_config():
    return {
        "model": current_story_model(),
        "models": STORY_MODELS,
        "params": current_story_params(),
        "param_specs": STORY_PARAMS
    }


@app.post("/api/config/model")
def set_model(body: ModelBody):
    model_ids = [mid for mid, _ in STORY_MODELS]
    if body.model_id not in model_ids:
        raise HTTPException(status_code=400, detail="invalid model_id")
    cfg = load_config()
    cfg["story_model"] = body.model_id
    save_config(cfg)
    return {"ok": True, "model": body.model_id}


@app.post("/api/config/params")
def set_params(body: ParamsBody):
    cfg = load_config()
    cfg["story_params"] = body.params
    save_config(cfg)
    return {"ok": True}


DIST = Path(__file__).parent.parent / "frontend" / "dist"


@app.get("/")
def root():
    return FileResponse(DIST / "index.html")


if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    return FileResponse(DIST / "index.html")
