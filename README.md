# AI Text Adventure

A local, private AI Dungeon-style text adventure that runs entirely on your own
machine through [Ollama](https://ollama.com). The model maintains its own memory —
a rolling plot summary, append-only plot points, and per-character inner state — and
reasons privately before writing, so a mid-sized local model holds a coherent story
well above its weight class. You just play; the bookkeeping runs itself.

No subscription, no cloud, no data leaving your machine.

## How it works

Each turn the player sees a single prose response, but several model calls happen
under the hood. The core idea is to **separate the storyteller from the bookkeeper** —
one model writes, another keeps the records straight.

```
Player action
   │
   ▼
RETRIEVE  ─ pull relevant context: plot summary, open plot points,
            keyword-triggered cards (characters, locations, items, lore...)
   │
   ▼
THINK     ─ hidden reasoning pass: motivations, consequences, who knows what
   │
   ▼
WRITE     ─ visible prose, streamed token-by-token, fed by the planning notes
   │
   ▼
UPDATE    ─ hidden "librarian" pass (every few turns): updates cards and plot
            points as JSON, plus a private inner-state pass per character
   │
   ▼
SUMMARIZE ─ periodically fold the oldest turns into the rolling summary
```

### Key features

- **Self-managing memory.** A librarian pass reads recent turns and updates structured
  records on its own — you never hand-edit them during play.
- **Per-character inner state.** Each character carries private `memory`, `goals`,
  `plans`, `secrets`, and `thoughts`. They only learn what they personally witnessed,
  so they never act on information they couldn't have.
- **Hidden reasoning step.** A planning pass runs before the prose, externalizing the
  consequence/consistency reasoning a small model would otherwise do unreliably.
- **Append-only plot points.** Hard facts are added and flagged resolved, never silently
  overwritten, so a bad summary can't erase a true event.
- **Keyword-triggered cards.** Cards are injected into context only when relevant —
  characters, classes, races, locations, factions, items, lore, and more.
- **Two model roles.** A creative story-tuned model writes the prose; a small obedient
  instruct model handles the structured bookkeeping (kept on CPU so both fit in VRAM).
- **Snapshots and retry.** Every turn is snapshotted, so `/retry` rerolls the last beat
  cleanly without corrupting the store.
- **JSON-constrained bookkeeping with fail-safe.** If a bookkeeping call returns invalid
  JSON, that update is skipped rather than corrupting the records.

## Requirements

- Python 3.9+
- [Ollama](https://ollama.com) running locally (`http://localhost:11434`)
- The models you want to use, pulled in Ollama. Defaults:
  - Story (prose): `nchapman/mn-12b-mag-mell-r1`
  - Utility (reasoning/bookkeeping): `phi4-mini`

```sh
ollama pull nchapman/mn-12b-mag-mell-r1
ollama pull phi4-mini
```

You can swap the story model from the menu at runtime; see `engine.py` for the
built-in list and add your own.

## Setup

```sh
pip install -r requirements.txt
python engine.py
```

Optionally copy `config.example.json` to `config.json` to pin a default story model
and sampler settings (the menu can also write this for you).

## Playing

The main menu lets you create, load, or delete adventures, change the story model, and
tune sampler parameters. Inside an adventure:

| Input | Meaning |
|---|---|
| `bare text` | An action — "You ..." |
| `"text"` | Speech — `You say, "..."` |
| `> text` | Narrator / scene direction |
| *(empty Enter)* | Advance the scene by one beat |

In-play commands:

| Command | Effect |
|---|---|
| `/retry` | Reroll the last turn |
| `/model` | Switch story model |
| `/params` | Tune temperature, length, top-p, repeat penalty |
| `/records` | Dump the full store (summary, plot points, recent) |
| `/cards` | List all cards and character inner state |
| `/save` | Update memory and save |
| `quit` | Save and return to the menu |

## Project layout

```
engine.py            the whole engine — model calls, memory, play loop
adventures/          per-adventure saves (gitignored)
  <name>/
    meta.json        name, turn counter, timestamps
    premise.md       pinned setting, set once
    summary.md       rolling prose recap of older events
    recent.json      last N turns, verbatim
    plot_points.json append-only crucial events
    cards/           triggered cards by category
config.json          local model + sampler config (gitignored)
```

## Configuration

`config.json` is read live, so changes apply immediately:

```json
{
  "story_model": "nchapman/mn-12b-mag-mell-r1",
  "story_params": {
    "temperature": 0.85,
    "num_predict": 300,
    "top_p": 0.95,
    "repeat_penalty": 1.1
  }
}
```

## License

MIT — see [LICENSE](LICENSE).
