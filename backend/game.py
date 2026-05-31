import json

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


def _build_story_prompt(player_action, card_block, recent, reasoning):
    return f"""You are the narrator of an interactive text adventure. Write in second person
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


def take_turn_stream(player_action):
    """Generator yielding SSE event dicts for a single turn. For web API use."""
    snapshot_state(player_action)
    tc = state["meta"]["turn_counter"]
    if tc > 0 and tc % LIBRARIAN_EVERY == 0:
        yield {"type": "status", "text": "Updating memory..."}
        run_bookkeeping()
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
    state["recent"].append(story)
    state["meta"]["turn_counter"] += 1
    save_trunk()
    yield {"type": "done"}
