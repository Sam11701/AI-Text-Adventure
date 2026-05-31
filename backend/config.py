import json
import pathlib

LMSTUDIO_URL = "http://localhost:1234/v1/chat/completions"

# (id, label) — id is the LM Studio model identifier; label is what the user picks from.
# IDs must match what `GET http://localhost:1234/v1/models` returns.
STORY_MODELS = [
    ("wayfarer-2-12b",
     "Wayfarer 2 12B (AI Dungeon's own RP model, fast)"),
    ("peach-2.0-9b-8k-roleplay-heretic-i1",
     "Peach 2.0 9B (roleplay, fast)"),
    ("mistral-nemo-instruct-2407",
     "Mistral Nemo 12B (general purpose)"),
    ("equinox-31b",
     "Equinox 31B (larger, slower, stronger characters)"),
]
DEFAULT_STORY_MODEL = STORY_MODELS[0][0]
UTILITY_MODEL = "phi-4-mini-instruct"            # small/fast non-reasoning; used for bookkeeping + JSON

# Story-generation knobs the user can tweak from the UI.
# (key, default, min, max, blurb)
STORY_PARAMS = [
    ("temperature",    0.85, 0.0, 2.0,  "Randomness. Higher = wilder, lower = safer."),
    ("num_predict",    300,  32,  2048, "Max tokens per response. Higher = longer reply."),
    ("top_p",          0.95, 0.1, 1.0,  "Nucleus sampling. Lower = more focused."),
    ("repeat_penalty", 1.1,  1.0, 1.5,  "Penalty for repeating tokens. Raise if it loops."),
]
DEFAULT_STORY_PARAMS = {k: d for k, d, _, _, _ in STORY_PARAMS}


ROOT_DIR = pathlib.Path(__file__).parent.parent
ADVENTURES_DIR = ROOT_DIR / "adventures"
CONFIG_PATH = ROOT_DIR / "config.json"
CARD_CATEGORIES = ["characters", "classes", "races", "locations",
                   "factions", "items", "lore", "other"]

CONTEXT_RECENT_LINES = 12
LIBRARIAN_EVERY = 5
SUMMARIZE_EVERY = 10

INNER_FIELDS = ["memory", "goals", "secrets", "plans"]   # lists
INNER_TEXT_FIELDS = ["thoughts"]                          # short prose
INNER_CAPS = {"memory": 12, "goals": 6, "plans": 6, "secrets": 6}


def load_config():
    if CONFIG_PATH.is_file():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def current_story_model():
    return load_config().get("story_model") or DEFAULT_STORY_MODEL


def current_story_params():
    cfg = load_config().get("story_params", {})
    return {k: cfg.get(k, d) for k, d, _, _, _ in STORY_PARAMS}


def tune_story_params():
    cfg = load_config()
    params = current_story_params()
    while True:
        print("\nStory generation parameters:")
        for i, (k, default, mn, mx, blurb) in enumerate(STORY_PARAMS, 1):
            val = params[k]
            print(f"  {i}) {k} = {val}   (default {default}, range {mn}-{mx})")
            print(f"       {blurb}")
        print("  r) reset all to defaults")
        print("  (enter to go back)")
        sel = input("> ").strip().lower()
        if not sel:
            return
        if sel == "r":
            params = dict(DEFAULT_STORY_PARAMS)
            cfg["story_params"] = params
            save_config(cfg)
            print("[reset]")
            continue
        try:
            k, _, mn, mx, _ = STORY_PARAMS[int(sel) - 1]
        except (ValueError, IndexError):
            print("[invalid]"); continue
        new = input(f"new value for {k} ({mn}-{mx}): ").strip()
        if not new:
            continue
        try:
            v = float(new) if "." in new or k == "temperature" or k == "top_p" \
                or k == "repeat_penalty" else int(new)
        except ValueError:
            print("[not a number]"); continue
        if v < mn or v > mx:
            print(f"[out of range {mn}-{mx}]"); continue
        if k == "num_predict":
            v = int(v)
        params[k] = v
        cfg["story_params"] = params
        save_config(cfg)
        print(f"[{k} = {v}]")


def pick_story_model():
    current = current_story_model()
    print("\nStory model:")
    for i, (mid, label) in enumerate(STORY_MODELS, 1):
        marker = " (current)" if mid == current else ""
        print(f"  {i}) {label}{marker}")
    print("  (enter to keep current)")
    while True:
        sel = input("> ").strip()
        if not sel:
            return current
        try:
            chosen = STORY_MODELS[int(sel) - 1][0]
        except (ValueError, IndexError):
            print("[invalid choice]"); continue
        cfg = load_config()
        cfg["story_model"] = chosen
        save_config(cfg)
        return chosen
