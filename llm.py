import json
import sys
import time
import re
import shutil
import threading
import subprocess
import requests

from config import LMSTUDIO_URL, UTILITY_MODEL, current_story_model, current_story_params


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
def _strip_fences(text):
    """Some models wrap JSON in ```json ... ``` fences; peel them off."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t).strip()
    return t


def call(model, prompt, temperature=0.8, max_tokens=300, as_json=False,
         top_p=None, repeat_penalty=None, **_ignored):
    payload = {"model": model,
               "messages": [{"role": "user", "content": prompt}],
               "temperature": temperature, "max_tokens": max_tokens,
               "stream": False}
    if top_p is not None:
        payload["top_p"] = top_p
    if repeat_penalty is not None:
        payload["repeat_penalty"] = repeat_penalty
    # NOTE: LM Studio wants response_format json_schema (not OpenAI's json_object),
    # and our JSON shapes vary. The prompts already enforce "Output JSON only" and
    # callers tolerate parse failures, so we rely on that instead. as_json kept for
    # signature compatibility.
    r = requests.post(LMSTUDIO_URL, json=payload, timeout=300)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"].strip()
    return _strip_fences(content) if as_json else content


def util_call(prompt, label, **kw):
    with Spinner(label):
        return call(UTILITY_MODEL, prompt, **kw)


def story_stream(prompt, **_ignored):
    p = current_story_params()
    payload = {"model": current_story_model(),
               "messages": [{"role": "user", "content": prompt}],
               "temperature": p["temperature"], "max_tokens": p["num_predict"],
               "top_p": p["top_p"], "repeat_penalty": p["repeat_penalty"],
               "stream": True}
    sys.stdout.write("\n"); sys.stdout.flush()
    parts = []
    with requests.post(LMSTUDIO_URL, json=payload, stream=True, timeout=300) as r:
        r.raise_for_status()
        for raw in r.iter_lines():
            if not raw:
                continue
            line = raw.decode("utf-8")
            if line.startswith("data: "):
                line = line[6:]
            if line.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            tok = chunk["choices"][0].get("delta", {}).get("content", "")
            if tok:
                sys.stdout.write(tok); sys.stdout.flush()
                parts.append(tok)
    sys.stdout.write("\n")
    return "".join(parts).strip()


# ---------------- model loading ----------------
def ensure_models_loaded():
    lms = shutil.which("lms")
    if not lms:
        print("[lms not found in PATH — load models in LM Studio manually]")
        return
    for mid in [current_story_model(), UTILITY_MODEL]:
        with Spinner(f"Loading {mid}"):
            try:
                r = subprocess.run(
                    [lms, "load", mid, "--yes"],
                    capture_output=True, timeout=120,
                )
                ok = r.returncode == 0
            except (subprocess.TimeoutExpired, OSError):
                ok = False
        print(f"[{mid}] {'ready' if ok else 'failed — load it in LM Studio manually'}")
