import json, os, sys, time, re, shutil, datetime, threading, pathlib, requests


OLLAMA_URL = "http://localhost:11434/api/generate"

# (id, label) — id is what Ollama sees; label is what the user picks from.
STORY_MODELS = [
    ("nchapman/mn-12b-mag-mell-r1",
     "Mistral Nemo 12B (Mag-Mell, RP finetune, fast)"),
    ("gemma3:12b",
     "Gemma 3 12B (general purpose, fast)"),
    ("hf.co/TheDrummer/Cydonia-22B-v1.3-GGUF:Q3_K_M",
     "Cydonia 22B Q3 (larger, slower, stronger characters)"),
]
DEFAULT_STORY_MODEL = STORY_MODELS[0][0]
UTILITY_MODEL = "phi4-mini"                      # CPU, pinned (num_gpu=0)

# Story-generation knobs the user can tweak from the UI.
# (key, default, min, max, blurb)
STORY_PARAMS = [
    ("temperature",    0.85, 0.0, 2.0,  "Randomness. Higher = wilder, lower = safer."),
    ("num_predict",    300,  32,  2048, "Max tokens per response. Higher = longer reply."),
    ("top_p",          0.95, 0.1, 1.0,  "Nucleus sampling. Lower = more focused."),
    ("repeat_penalty", 1.1,  1.0, 1.5,  "Penalty for repeating tokens. Raise if it loops."),
]
DEFAULT_STORY_PARAMS = {k: d for k, d, _, _, _ in STORY_PARAMS}


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

ROOT_DIR = pathlib.Path(__file__).parent
ADVENTURES_DIR = ROOT_DIR / "adventures"
CONFIG_PATH = ROOT_DIR / "config.json"
CARD_CATEGORIES = ["characters", "classes", "races", "locations",
                   "factions", "items", "lore", "other"]

CONTEXT_RECENT_LINES = 12
LIBRARIAN_EVERY = 5
SUMMARIZE_EVERY = 10

state = {}   # populated by load_adventure()


# ---------------- spinner ----------------
class Spinner:
    def __init__(self, label):
        self.label = label
        self.running = False
        self.thread = None
    def __enter__(self):
        self.running = True
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()
        return self
    def __exit__(self, *a):
        self.running = False
        if self.thread:
            self.thread.join()
        sys.stdout.write("\r" + " " * (len(self.label) + 6) + "\r")
        sys.stdout.flush()
    def _spin(self):
        i = 0
        while self.running:
            dots = "." * ((i % 3) + 1)
            sys.stdout.write(f"\r\x1b[90m{self.label}{dots}   \x1b[0m")
            sys.stdout.flush()
            time.sleep(0.4)
            i += 1


# ---------------- model calls ----------------
def call(model, prompt, temperature=0.8, max_tokens=300, as_json=False,
         keep_alive="30m", num_gpu=None):
    options = {"temperature": temperature, "num_predict": max_tokens}
    if num_gpu is not None:
        options["num_gpu"] = num_gpu
    payload = {"model": model, "prompt": prompt, "stream": False,
               "options": options, "keep_alive": keep_alive}
    if as_json:
        payload["format"] = "json"
    r = requests.post(OLLAMA_URL, json=payload, timeout=180)
    return r.json()["response"].strip()


def util_call(prompt, label, **kw):
    with Spinner(label):
        return call(UTILITY_MODEL, prompt, num_gpu=0, **kw)


def story_stream(prompt, keep_alive="30m"):
    payload = {"model": current_story_model(), "prompt": prompt, "stream": True,
               "options": dict(current_story_params()),
               "keep_alive": keep_alive}
    sys.stdout.write("\n"); sys.stdout.flush()
    parts = []
    with requests.post(OLLAMA_URL, json=payload, stream=True, timeout=180) as r:
        for line in r.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            tok = chunk.get("response", "")
            if tok:
                sys.stdout.write(tok); sys.stdout.flush()
                parts.append(tok)
            if chunk.get("done"):
                break
    sys.stdout.write("\n")
    return "".join(parts).strip()


# ---------------- storage ----------------
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
    return base


def load_adventure(base):
    state.clear()
    state["dir"] = base
    state["meta"] = json.loads((base / "meta.json").read_text(encoding="utf-8"))
    state["premise"] = (base / "premise.md").read_text(encoding="utf-8").strip()
    state["summary"] = (base / "summary.md").read_text(encoding="utf-8").strip()
    state["recent"] = json.loads((base / "recent.json").read_text(encoding="utf-8"))
    state["plot_points"] = json.loads((base / "plot_points.json").read_text(encoding="utf-8"))
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


# ---------------- snapshot / retry ----------------
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


# ---------------- retrieve / write / think / librarian / summary ----------------
def find_triggered(cards, scan_lower):
    out = []
    for c in cards:
        for trig in c.get("triggers", []):
            if trig and trig.lower() in scan_lower:
                out.append(c); break
    return out


def _bullets(items, indent="     "):
    return "\n".join(f"{indent}- {x}" for x in items if x)


def format_card(c):
    cat = c["_category"]
    tag = cat[:-1] if cat.endswith("s") else cat
    head = f"- [{tag}] {c['name']}: {c.get('entry','').strip()}"
    if c.get("state"):
        head += f"  (currently: {c['state'].strip()})"
    if cat != "characters":
        return head
    inner_lines = []
    if c.get("memory"):
        inner_lines.append("   knows / has witnessed:\n" + _bullets(c["memory"]))
    if c.get("goals"):
        inner_lines.append("   wants:\n" + _bullets(c["goals"]))
    if c.get("plans"):
        inner_lines.append("   plans:\n" + _bullets(c["plans"]))
    if c.get("secrets"):
        inner_lines.append("   secrets (model only — never reveal directly):\n"
                           + _bullets(c["secrets"]))
    if c.get("thoughts"):
        inner_lines.append(f"   current thoughts: {c['thoughts'].strip()}")
    if inner_lines:
        head += "\n" + "\n".join(inner_lines)
    return head


def retrieve(player_action):
    cards = load_cards()
    scan_lower = (" ".join(state["recent"][-4:]) + " " + player_action).lower()
    triggered = find_triggered(cards, scan_lower)
    card_block = "\n".join(format_card(c) for c in triggered) or "(none relevant)"
    open_points = "\n".join(f"- {p['text']}" for p in state["plot_points"]
                            if not p["resolved"]) or "(none)"
    recent = "\n".join(state["recent"][-CONTEXT_RECENT_LINES:])
    return card_block, open_points, recent


def think(player_action, card_block, open_points, recent):
    prompt = f"""You are the hidden reasoning engine for a text adventure. Do NOT write prose.
Premise: {state['premise']}
Summary so far: {state['summary']}
Open plot threads:
{open_points}
Relevant cards (characters carry private memory/goals/plans/secrets — use them):
{card_block}
Recent events:
{recent}
Player's action: {player_action}

Think step by step. Use each present character's private mind:
- What does THIS character actually know (only what they witnessed)?
- What do they want, plan, or secretly hide?
- How would those drives shape their reaction RIGHT NOW?
- Realistic consequences? Anyone about to act out of character?
Answer in 3-5 terse bullets."""
    return util_call(prompt, "Thinking", temperature=0.4, max_tokens=250)


def write_story(player_action, card_block, recent, reasoning):
    prompt = f"""You are the narrator of an interactive text adventure. Write in second person
("You ..."). Write 2-4 vivid sentences continuing the story, then stop and let the player act.

HARD RULES — NEVER violate:
- Do NOT offer the player options, choices, or a menu.
- Do NOT use bullet points, numbered lists, or dashes for choices.
- Do NOT ask the player questions like "Do you...?", "Will you...?", "What do you do?".
- Do NOT decide, speak, or think for the player.
- Just describe what happens, then stop. The player will type what they do.
- Each character only knows what their card says they know. Never let them act on
  information they didn't witness. Let their goals/plans/secrets drive their behavior,
  but never quote secrets aloud.

Bad (never do this):
  You look around. Do you:
  - Search the body
  - Run away
Good:
  You crouch beside the body. The cold has already crept into her fingers.

Premise: {state['premise']}
Summary of earlier events: {state['summary']}
Relevant cards:
{card_block}
Recent events:
{recent}

[Planning notes - use these, do not mention them]
{reasoning}

Player's action: {player_action}

Continue (prose only, no choices, no questions to the player):"""
    return story_stream(prompt)


def librarian_batch():
    block = "\n".join(state["recent"][-LIBRARIAN_EVERY * 2:])
    existing = [f"{c['_category']}/{c['name']}" for c in load_cards()]
    prompt = f"""You maintain memory records for a text adventure. Read the last {LIBRARIAN_EVERY}
exchanges and return ONLY a JSON object. Be conservative; record only genuinely important
information that affects the future.

Card categories: {CARD_CATEGORIES}
Existing cards (do NOT recreate these — use card_updates instead):
{existing}

Recent exchanges:
{block}

JSON fields (use [] or {{}} when nothing applies):
{{
  "new_cards": [
    {{
      "category": "one of: {' | '.join(CARD_CATEGORIES)}",
      "name": "Display Name",
      "entry": "Stable identity / description.",
      "triggers": ["word", "alt name", "short phrase the AI would write"],
      "state": "current mood / location / condition (optional, may be empty)"
    }}
  ],
  "card_updates": [
    {{ "name": "Existing Name", "state": "new state if changed",
       "triggers_to_add": ["any new aliases observed"] }}
  ],
  "new_plot_points": ["short factual statements of NEW crucial events"],
  "resolved_points": ["exact text of any open plot point now resolved"]
}}
Output JSON only."""
    raw = util_call(prompt, "Updating memory", temperature=0.2, max_tokens=800, as_json=True)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return

    by_name = {c["name"].lower(): c for c in load_cards()}

    for nc in data.get("new_cards", []) or []:
        name = (nc.get("name") or "").strip()
        if not name:
            continue
        cat = nc.get("category", "other")
        if cat not in CARD_CATEGORIES:
            cat = "other"
        if name.lower() in by_name:
            # collision -> treat as update; never overwrite a non-empty entry
            c = by_name[name.lower()]
            if nc.get("state"):
                c["state"] = nc["state"]
            for t in nc.get("triggers", []) or []:
                if t and t not in c.get("triggers", []):
                    c.setdefault("triggers", []).append(t)
            if nc.get("entry") and not c.get("entry"):
                c["entry"] = nc["entry"]
            write_card(c["_category"], c)
        else:
            card = {
                "type": cat[:-1] if cat.endswith("s") else cat,
                "name": name,
                "triggers": nc.get("triggers") or [name],
                "entry": nc.get("entry", ""),
                "state": nc.get("state", ""),
                "notes": "",
            }
            if cat == "characters":
                card.update({"memory": [], "goals": [], "plans": [],
                             "secrets": [], "thoughts": ""})
            write_card(cat, card)

    by_name = {c["name"].lower(): c for c in load_cards()}
    for upd in data.get("card_updates", []) or []:
        nm = (upd.get("name") or "").lower()
        if nm not in by_name:
            continue
        c = by_name[nm]
        if upd.get("state"):
            c["state"] = upd["state"]
        for t in upd.get("triggers_to_add", []) or []:
            if t and t not in c.get("triggers", []):
                c.setdefault("triggers", []).append(t)
        write_card(c["_category"], c)

    for txt in data.get("new_plot_points", []) or []:
        state["plot_points"].append({"id": len(state["plot_points"]),
                                     "text": txt, "resolved": False})
    for txt in data.get("resolved_points", []) or []:
        for p in state["plot_points"]:
            if p["text"] == txt:
                p["resolved"] = True

    inner_self_pass(block)


# ---------------- inner-self (per-character private mind) ----------------
INNER_CAPS = {"memory": 12, "goals": 6, "plans": 6, "secrets": 6}


def _trim(lst, cap):
    return lst[-cap:] if len(lst) > cap else lst


def inner_self_pass(block):
    """For each character whose triggers fired recently, update their private
    memory/goals/plans/secrets/thoughts. They only learn what they witnessed."""
    cards = load_cards()
    scan_lower = " ".join(state["recent"][-LIBRARIAN_EVERY * 2:]).lower()
    present = [c for c in cards if c["_category"] == "characters"
               and any(t and t.lower() in scan_lower for t in c.get("triggers", []))]
    for c in present:
        update_one_character(c, block)


def update_one_character(c, block):
    name = c["name"]
    prior = {f: c.get(f, [] if f in INNER_FIELDS else "") for f in INNER_FIELDS + INNER_TEXT_FIELDS}
    prompt = f"""You are tracking the private inner state of ONE character: "{name}".
Update their mind based on the recent exchanges below.

CRITICAL: {name} only knows what they personally witnessed, said, or experienced.
If something happened off-stage (when {name} was not present), do NOT add it to their memory.
Be conservative — only record genuinely meaningful changes.

Character description: {c.get('entry','')}
Current visible state: {c.get('state','')}

{name}'s prior inner state:
  memory:   {prior['memory']}
  goals:    {prior['goals']}
  plans:    {prior['plans']}
  secrets:  {prior['secrets']}
  thoughts: {prior['thoughts']}

Recent exchanges:
{block}

Return ONLY a JSON object. Empty lists/strings are fine. "drop" entries must match
existing items exactly. "thoughts" replaces the prior thoughts (1-2 sentences max).
{{
  "memory_add":   ["new things {name} personally witnessed or learned"],
  "memory_drop":  ["exact prior memory items that are now wrong or obsolete"],
  "goals_add":    ["new wants/desires that emerged"],
  "goals_drop":   ["prior goals now achieved or abandoned"],
  "plans_add":    ["new intended actions"],
  "plans_drop":   ["plans now executed or no longer relevant"],
  "secrets_add":  ["new secrets {name} is now keeping"],
  "secrets_drop": ["secrets now revealed or no longer secret"],
  "thoughts":     "current inner monologue (1-2 sentences, or empty to keep prior)"
}}"""
    raw = util_call(prompt, f"Inner self: {name}",
                    temperature=0.3, max_tokens=500, as_json=True)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return

    for f in INNER_FIELDS:
        cur = list(c.get(f, []) or [])
        for drop in data.get(f + "_drop", []) or []:
            cur = [x for x in cur if x != drop]
        for add in data.get(f + "_add", []) or []:
            if add and add not in cur:
                cur.append(add)
        c[f] = _trim(cur, INNER_CAPS[f])

    new_thoughts = (data.get("thoughts") or "").strip()
    if new_thoughts:
        c["thoughts"] = new_thoughts

    write_card("characters", c)


def roll_summary():
    old = "\n".join(state["recent"][:-CONTEXT_RECENT_LINES])
    if not old.strip():
        return
    prompt = f"""Fold the older events into the running summary. Keep every fact that affects
the future; drop fluff. Be concise. Plain prose only.

Current summary: {state['summary']}
Older events:
{old}"""
    state["summary"] = util_call(prompt, "Summarizing", temperature=0.3, max_tokens=300)
    state["recent"] = state["recent"][-CONTEXT_RECENT_LINES:]


def run_bookkeeping():
    librarian_batch()
    if state["meta"]["turn_counter"] % SUMMARIZE_EVERY == 0:
        roll_summary()


def take_turn(player_action):
    snapshot_state(player_action)
    tc = state["meta"]["turn_counter"]
    if tc > 0 and tc % LIBRARIAN_EVERY == 0:
        run_bookkeeping()
    state["recent"].append(player_action)
    card_block, open_points, recent = retrieve(player_action)
    reasoning = think(player_action, card_block, open_points, recent)
    story = write_story(player_action, card_block, recent, reasoning)
    state["recent"].append(story)
    state["meta"]["turn_counter"] += 1
    save_trunk()   # autosave every turn


# ---------------- play loop ----------------
def play_loop():
    print(f"\n--- {state['meta']['name']} ---")
    print(f"Model: {current_story_model()}")
    print('Input: bare = action,  "..." = speech,  > ... = narrator,  empty Enter = continue')
    print("Commands: /retry, /model, /params, /records, /cards, /save, quit (returns to menu)\n")
    print(state["premise"])
    while True:
        raw = input("\n> ")
        cmd = raw.strip()
        if cmd.lower() == "quit":
            librarian_batch()
            save_trunk()
            print("[memory updated and saved]")
            return
        if cmd == "/save":
            librarian_batch()
            save_trunk()
            print("[memory updated and saved]")
            continue
        if cmd == "/retry":
            snap = load_snapshot()
            if not snap or not snap.get("last_action"):
                print("[nothing to retry]"); continue
            restore_snapshot(snap)
            print("[rerolling last turn]")
            take_turn(snap["last_action"])
            continue
        if cmd == "/model":
            new_id = pick_story_model()
            print(f"[model set to {new_id}]")
            continue
        if cmd == "/params":
            tune_story_params(); continue
        if cmd == "/records":
            print(json.dumps({k: v for k, v in state.items() if k != "dir"},
                             indent=2, default=str))
            continue
        if cmd == "/cards":
            for c in load_cards():
                print(f"  [{c['_category']}] {c['name']}  triggers={c.get('triggers')}")
                if c["_category"] == "characters":
                    for f in INNER_FIELDS:
                        if c.get(f):
                            print(f"      {f}: {c[f]}")
                    if c.get("thoughts"):
                        print(f"      thoughts: {c['thoughts']}")
            continue
        if cmd == "":
            action = "(no action - advance the scene by one beat; do not address the player)"
        elif cmd.startswith('"'):
            spoken = cmd.strip('"').strip()
            action = f'You say, "{spoken}"'
        elif cmd.startswith(">"):
            action = cmd[1:].strip()
        else:
            action = f"You {cmd}"
        take_turn(action)


# ---------------- main menu ----------------
def main_menu():
    ADVENTURES_DIR.mkdir(exist_ok=True)
    while True:
        advs = list_adventures()
        print("\n=== Local AI Dungeon ===")
        print(f"Model: {current_story_model()}")
        for i, (_, meta) in enumerate(advs, 1):
            turns = meta.get("turn_counter", 0)
            last = meta.get("last_played") or "never"
            print(f"  {i}) {meta['name']}  ·  {turns} turns  ·  last played {last}")
        print("  n) new adventure")
        if advs:
            print("  d) delete adventure")
        print("  m) change model")
        print("  p) tune story parameters")
        print("  q) quit")
        choice = input("> ").strip().lower()
        if not choice:
            continue
        if choice == "q":
            return
        if choice == "m":
            pick_story_model(); continue
        if choice == "p":
            tune_story_params(); continue
        if choice == "n":
            name = input("Adventure name: ").strip()
            if not name:
                continue
            premise = input("Premise / setting: ").strip()
            if not premise:
                continue
            try:
                base = create_adventure(name, premise)
            except FileExistsError as e:
                print(f"[error] {e}"); continue
            load_adventure(base)
            play_loop()
            continue
        if choice == "d" and advs:
            sel = input("Number to delete: ").strip()
            try:
                i = int(sel) - 1
                base, meta = advs[i]
            except (ValueError, IndexError):
                print("[invalid]"); continue
            confirm = input(f"Delete '{meta['name']}'? type 'yes': ")
            if confirm == "yes":
                delete_adventure(base)
                print("[deleted]")
            continue
        try:
            i = int(choice) - 1
            base, _ = advs[i]
        except (ValueError, IndexError):
            print("[invalid choice]"); continue
        load_adventure(base)
        play_loop()


if __name__ == "__main__":
    main_menu()
