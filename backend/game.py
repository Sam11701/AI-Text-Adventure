import json
import threading

from config import (
    CARD_CATEGORIES,
    CONTEXT_RECENT_LINES,
    LIBRARIAN_EVERY,
    SUMMARIZE_EVERY,
    INNER_FIELDS,
    INNER_TEXT_FIELDS,
    INNER_CAPS,
)
from llm import util_call, story_stream, story_stream_gen
from storage import state, load_cards, write_card, save_trunk, snapshot_state


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
    essentials = state.get("plot_essentials", "").strip()
    essentials_line = f"\nPlot essentials:\n{essentials}" if essentials else ""
    prompt = f"""You are the hidden reasoning engine for a text adventure. Do NOT write prose.
Premise: {state['premise']}
Summary so far: {state['summary']}{essentials_line}
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


def _build_story_prompt(player_action, card_block, recent, reasoning):
    ai_instr = state.get("ai_instructions", "").strip()
    essentials = state.get("plot_essentials", "").strip()
    author_note = state.get("author_note", "").strip()

    narrator = ai_instr or (
        'You are the narrator of an interactive text adventure. Write in second person\n'
        '("You ..."). Write 2-4 vivid sentences continuing the story, then stop and let the player act.'
    )
    essentials_block = f"\nPlot essentials:\n{essentials}\n" if essentials else ""
    note_block = f"\n[Author's note: {author_note}]" if author_note else ""

    return f"""{narrator}

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
Summary of earlier events: {state['summary']}{essentials_block}
Relevant cards:
{card_block}
Recent events:
{recent}

[Planning notes - use these, do not mention them]
{reasoning}{note_block}

Player's action: {player_action}

Continue (prose only, no choices, no questions to the player):"""


def write_story(player_action, card_block, recent, reasoning):
    return story_stream(_build_story_prompt(player_action, card_block, recent, reasoning))


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


def _trim(lst, cap):
    return lst[-cap:] if len(lst) > cap else lst


_INNER_SELF_CARD_NAME = "Configure Inner Self"

_INNER_SELF_ENTRY = (
    "Inner Self grants story characters the ability to learn, plan, and adapt over time. "
    "Each character with matching triggers develops private memory, goals, plans, secrets, "
    "and thoughts that influence their behaviour.\n\n"
    "Edit the notes field (not visible to the AI) to control behaviour."
)

_INNER_SELF_NOTES_DEFAULT = """\
enabled: true
characters: all
player name:
pov: 2
context percent: 30
lookback actions: 5
indicator: 🎭
thought chance: 60
half chance do say story: true
debug mode: false
thoughts every turn: true
ac enabled: false"""

_IS_DEFAULTS = {
    "enabled": True,
    "characters": "all",
    "player_name": "",
    "pov": 2,
    "context_percent": 30,
    "lookback_actions": 5,
    "indicator": "🎭",
    "thought_chance": 60,
    "half_chance_do_say_story": True,
    "debug_mode": False,
    "thoughts_every_turn": True,
    "ac_enabled": False,
}


def _get_inner_self_config():
    cards = load_cards()
    cfg_card = next((c for c in cards if c["name"] == _INNER_SELF_CARD_NAME), None)
    cfg = dict(_IS_DEFAULTS)
    if not cfg_card:
        return cfg
    for line in (cfg_card.get("notes") or "").splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower().replace(" ", "_")
        val_raw = val.strip()
        val_lo = val_raw.lower()
        b = val_lo in ("true", "yes", "1")
        if   key == "enabled":                    cfg["enabled"] = b
        elif key == "characters":                 cfg["characters"] = val_lo
        elif key == "player_name":                cfg["player_name"] = val_raw
        elif key == "pov":
            try: cfg["pov"] = int(val_lo)
            except ValueError: pass
        elif key == "context_percent":
            try: cfg["context_percent"] = max(1, min(95, int(val_lo)))
            except ValueError: pass
        elif key == "lookback_actions":
            try: cfg["lookback_actions"] = max(1, min(250, int(val_lo)))
            except ValueError: pass
        elif key == "indicator":                  cfg["indicator"] = val_raw
        elif key == "thought_chance":
            try: cfg["thought_chance"] = max(0, min(100, int(val_lo)))
            except ValueError: pass
        elif key == "half_chance_do_say_story":   cfg["half_chance_do_say_story"] = b
        elif key == "debug_mode":                 cfg["debug_mode"] = b
        elif key == "thoughts_every_turn":        cfg["thoughts_every_turn"] = b
        elif key == "ac_enabled":                 cfg["ac_enabled"] = b
    return cfg


def _ensure_inner_self_card():
    cards = load_cards()
    if not any(c["name"] == _INNER_SELF_CARD_NAME for c in cards):
        write_card("classes", {
            "name": _INNER_SELF_CARD_NAME,
            "entry": _INNER_SELF_ENTRY,
            "state": "",
            "triggers": [],
            "notes": _INNER_SELF_NOTES_DEFAULT,
        })


def _is_char_eligible(c, cfg):
    """Return True if this character card should be processed by Inner Self."""
    if cfg["characters"] != "all":
        allowed = {n.strip().lower() for n in cfg["characters"].split(",")}
        if c["name"].lower() not in allowed:
            return False
    if cfg["player_name"] and c["name"].lower() == cfg["player_name"].lower():
        return False
    return True


def _pov_note(pov):
    return {1: "first person (I/me)", 2: "second person (you/your)", 3: "third person (he/she/they)"}.get(pov, "second person (you/your)")



def inner_self_pass(block):
    """Batch pass: update full inner state for triggered characters."""
    _ensure_inner_self_card()
    cfg = _get_inner_self_config()
    if not cfg["enabled"]:
        return
    cards = load_cards()
    lookback = cfg["lookback_actions"]
    scan_lower = " ".join(state["recent"][-lookback:]).lower()
    present = [
        c for c in cards
        if c["_category"] == "characters"
        and _is_char_eligible(c, cfg)
        and any(t and t.lower() in scan_lower for t in c.get("triggers", []))
    ]
    for c in present:
        update_one_character(c, cfg)


def update_one_character(c, cfg=None):
    if cfg is None:
        cfg = _get_inner_self_config()
    name = c["name"]

    # Context window sized by context_percent of available recent history
    all_recent = state["recent"]
    n = max(2, int(len(all_recent) * cfg["context_percent"] / 100))
    block = "\n".join(all_recent[-n:])

    prior = {f: c.get(f, [] if f in INNER_FIELDS else "") for f in INNER_FIELDS + INNER_TEXT_FIELDS}
    if cfg["indicator"]:
        print(f"{cfg['indicator']} [Inner Self: {name}]")
    prompt = f"""You are tracking the private inner state of ONE character: "{name}".
Update their mind based on the recent exchanges below.
Write all thoughts in {_pov_note(cfg['pov'])}.

CRITICAL: {name} only knows what they personally witnessed, said, or experienced.
If something happened off-stage (when {name} was not present), do NOT add it to their memory.
Be conservative — only record genuinely meaningful changes.

Character description: {c.get('entry', '')}
Current visible state: {c.get('state', '')}

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
    raw = util_call(prompt, f"Inner self: {name}", temperature=0.3, max_tokens=500, as_json=True)
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
    if cfg["debug_mode"]:
        print(f"[IS debug] {name}: thoughts={c.get('thoughts', '')}")


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


_bg_lock = threading.Lock()


def _run_bg(player_action, story):
    if not _bg_lock.acquire(blocking=False):
        print("[bg] skipped — previous bookkeeping still running")
        return
    try:
        run_bookkeeping()
        save_trunk()
    except Exception as e:
        print(f"[bg error] {e}")
    finally:
        _bg_lock.release()


def _start_bg(player_action, story):
    threading.Thread(target=_run_bg, args=(player_action, story), daemon=True).start()


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


def take_turn_stream(player_action):
    """Generator yielding SSE event dicts for a single turn. For web API use."""
    print(f"\n{'='*60}\n[PLAYER] {player_action}\n{'='*60}")
    snapshot_state(player_action)
    state["recent"].append(player_action)
    card_block, open_points, recent = retrieve(player_action)
    yield {"type": "status", "text": "Thinking..."}
    reasoning = think(player_action, card_block, open_points, recent)
    yield {"type": "status", "text": "Writing..."}
    story_prompt = _build_story_prompt(player_action, card_block, recent, reasoning)
    parts = []
    for tok in story_stream_gen(story_prompt):
        parts.append(tok)
        yield {"type": "token", "text": tok}
    story = "".join(parts).strip()
    print(f"\n[STORY] {story}\n{'='*60}")
    state["recent"].append(story)
    state["meta"]["turn_counter"] += 1
    save_trunk()
    yield {"type": "done"}
    _start_bg(player_action, story)
