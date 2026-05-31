import json, sys
from config import current_story_model, tune_story_params, pick_story_model, CARD_CATEGORIES, ADVENTURES_DIR, INNER_FIELDS
from llm import ensure_models_loaded
from storage import state, load_adventure, save_trunk, load_cards, delete_adventure, list_adventures, load_snapshot, restore_snapshot, create_adventure
from game import take_turn, librarian_batch

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
            ensure_models_loaded()
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

def main_menu():
    ADVENTURES_DIR.mkdir(exist_ok=True)
    ensure_models_loaded()
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
            pick_story_model()
            ensure_models_loaded()
            continue
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
