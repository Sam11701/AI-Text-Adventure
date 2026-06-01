import json
import shutil
import datetime
import pathlib
import re

from config import ROOT_DIR, ADVENTURES_DIR, CONFIG_PATH, CARD_CATEGORIES

state = {}


def kebab(s):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return s or "unnamed"


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def list_adventures():
    if not ADVENTURES_DIR.exists():
        return []
    out = []
    for p in sorted(ADVENTURES_DIR.iterdir()):
        meta_path = p / "meta.json"
        if not meta_path.is_file():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            out.append((p, meta))
        except (json.JSONDecodeError, OSError):
            continue
    return out


def _read_opt(path):
    return path.read_text(encoding="utf-8").strip() if path.is_file() else ""


def create_adventure(display_name, premise_text):
    dirname = kebab(display_name)
    base = ADVENTURES_DIR / dirname
    if base.exists():
        raise FileExistsError(f"adventure '{dirname}' already exists")
    for cat in CARD_CATEGORIES:
        (base / "cards" / cat).mkdir(parents=True)
    meta = {"name": display_name, "dirname": dirname,
            "created": now(), "last_played": None, "turn_counter": 0}
    (base / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (base / "premise.md").write_text(premise_text.strip() + "\n", encoding="utf-8")
    (base / "summary.md").write_text("", encoding="utf-8")
    (base / "recent.json").write_text("[]", encoding="utf-8")
    (base / "plot_points.json").write_text("[]", encoding="utf-8")
    for fn in ("ai_instructions.md", "plot_essentials.md", "author_note.md"):
        (base / fn).write_text("", encoding="utf-8")
    return base


def load_adventure(base):
    state.clear()
    state["dir"] = base
    state["meta"] = json.loads((base / "meta.json").read_text(encoding="utf-8"))
    state["premise"] = (base / "premise.md").read_text(encoding="utf-8").strip()
    state["summary"] = (base / "summary.md").read_text(encoding="utf-8").strip()
    state["recent"] = json.loads((base / "recent.json").read_text(encoding="utf-8"))
    state["plot_points"] = json.loads((base / "plot_points.json").read_text(encoding="utf-8"))
    state["ai_instructions"] = _read_opt(base / "ai_instructions.md")
    state["plot_essentials"] = _read_opt(base / "plot_essentials.md")
    state["author_note"] = _read_opt(base / "author_note.md")
    # ensure card category dirs exist (in case the schema grew)
    for cat in CARD_CATEGORIES:
        (base / "cards" / cat).mkdir(parents=True, exist_ok=True)


def save_trunk():
    base = state["dir"]
    state["meta"]["last_played"] = now()
    (base / "meta.json").write_text(json.dumps(state["meta"], indent=2), encoding="utf-8")
    (base / "premise.md").write_text(state["premise"] + "\n", encoding="utf-8")
    (base / "summary.md").write_text(state["summary"] + ("\n" if state["summary"] else ""),
                                     encoding="utf-8")
    (base / "recent.json").write_text(json.dumps(state["recent"], indent=2), encoding="utf-8")
    (base / "plot_points.json").write_text(json.dumps(state["plot_points"], indent=2),
                                           encoding="utf-8")
    for field in ("ai_instructions", "plot_essentials", "author_note"):
        val = state.get(field, "")
        (base / f"{field}.md").write_text(val + ("\n" if val else ""), encoding="utf-8")


INNER_FIELDS = ["memory", "goals", "secrets", "plans"]   # lists
INNER_TEXT_FIELDS = ["thoughts"]                          # short prose


def ensure_inner_fields(card):
    """In-memory only — character cards get empty inner fields if missing."""
    if card.get("_category") != "characters":
        return card
    for f in INNER_FIELDS:
        if not isinstance(card.get(f), list):
            card[f] = []
    for f in INNER_TEXT_FIELDS:
        if not isinstance(card.get(f), str):
            card[f] = ""
    return card


def load_cards():
    """Live read of every card on disk. Called each turn so manual edits land immediately."""
    base = state["dir"]
    cards = []
    for cat in CARD_CATEGORIES:
        cat_dir = base / "cards" / cat
        if not cat_dir.is_dir():
            continue
        for f in sorted(cat_dir.glob("*.json")):
            try:
                card = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            card["_category"] = cat
            card["_path"] = f
            ensure_inner_fields(card)
            cards.append(card)
    return cards


def write_card(category, card):
    if category not in CARD_CATEGORIES:
        category = "other"
    base = state["dir"]
    filename = kebab(card["name"]) + ".json"
    path = base / "cards" / category / filename
    clean = {k: v for k, v in card.items() if not k.startswith("_")}
    path.write_text(json.dumps(clean, indent=2), encoding="utf-8")
    return path


def delete_adventure(base):
    shutil.rmtree(base)


def snapshot_state(last_action):
    base = state["dir"]
    cards = []
    for cat in CARD_CATEGORIES:
        for f in (base / "cards" / cat).glob("*.json"):
            cards.append({"category": cat, "filename": f.name,
                          "content": f.read_text(encoding="utf-8")})
    snap = {
        "last_action": last_action,
        "recent": list(state["recent"]),
        "plot_points": json.loads(json.dumps(state["plot_points"])),
        "summary": state["summary"],
        "turn_counter": state["meta"]["turn_counter"],
        "cards": cards,
    }
    (base / "_snapshot.json").write_text(json.dumps(snap, indent=2), encoding="utf-8")


def load_snapshot():
    p = state["dir"] / "_snapshot.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def restore_snapshot(snap):
    base = state["dir"]
    state["recent"] = snap["recent"]
    state["plot_points"] = snap["plot_points"]
    state["summary"] = snap["summary"]
    state["meta"]["turn_counter"] = snap["turn_counter"]
    for cat in CARD_CATEGORIES:
        for f in (base / "cards" / cat).glob("*.json"):
            f.unlink()
    for c in snap["cards"]:
        (base / "cards" / c["category"] / c["filename"]).write_text(
            c["content"], encoding="utf-8")
    save_trunk()
