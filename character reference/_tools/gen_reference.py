"""Generate character reference sheets (turnaround / expressions) via OpenRouter GPT Image 2.

Usage:
  python gen_reference.py --write-prompts            # write prompts.md into every character folder
  python gen_reference.py FUFU-enfp turnaround       # generate one sheet
  python gen_reference.py FUFU-enfp expressions
  python gen_reference.py FUFU-enfp all

Env: OPENROUTER_API_KEY must be set. Never hard-code the key in this file.
"""
import argparse
import base64
import json
import mimetypes
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent          # .../character reference
CFG = json.loads((Path(__file__).parent / "characters.json").read_text(encoding="utf-8"))
MODEL = "openai/gpt-5.4-image-2"
URL = "https://openrouter.ai/api/v1/chat/completions"

SHEETS = {
    "turnaround": {"key": "turnaround", "aspect": "16:9", "note_key": "turnaround_note"},
    "expressions": {"key": "expressions", "aspect": "1:1", "note_key": None},
}


def build_prompt(char_key: str, sheet: str) -> str:
    c = CFG["characters"][char_key]
    spec = SHEETS[sheet]
    parts = [
        CFG[spec["key"]],
        "",
        "CHARACTER: " + c["name"] + " (" + c["mbti"] + "). " + c["description"],
    ]
    if spec["note_key"] and c.get(spec["note_key"]):
        parts += ["", "SPECIAL NOTE: " + c[spec["note_key"]]]
    parts += ["", "STYLE: " + CFG["style"]]
    return "\n".join(parts)


def write_prompts() -> None:
    for key, c in CFG["characters"].items():
        folder = ROOT / key
        if not folder.is_dir():
            print("skip (no folder):", key)
            continue
        md = [
            f"# {c['name']} ({c['mbti']}) — reference prompts",
            "",
            f"Model: `{MODEL}` via OpenRouter. Attach `{key}.png` as the reference image with every prompt.",
            "",
            "## Props to keep consistent",
            "",
            c["props"],
            "",
            "## Turnaround prompt",
            "",
            "```",
            build_prompt(key, "turnaround"),
            "```",
            "",
            "## Expression sheet prompt",
            "",
            "```",
            build_prompt(key, "expressions"),
            "```",
            "",
        ]
        (folder / "prompts.md").write_text("\n".join(md), encoding="utf-8")
        print("wrote", folder / "prompts.md")


def ref_image_data_url(char_key: str) -> str:
    p = ROOT / char_key / f"{char_key}.png"
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def next_out_path(char_key: str, sheet: str) -> Path:
    d = ROOT / char_key / sheet
    d.mkdir(parents=True, exist_ok=True)
    n = 1
    while (d / f"{char_key}_{sheet}_v{n}.png").exists():
        n += 1
    return d / f"{char_key}_{sheet}_v{n}.png"


def load_dotenv() -> None:
    """Load KEY=VALUE lines from a .env file (repo root or _tools) into os.environ.

    Existing environment variables take precedence. No third-party dependency needed.
    """
    for env_path in (ROOT.parent / ".env", Path(__file__).parent / ".env"):
        if not env_path.is_file():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
        return


def generate(char_key: str, sheet: str) -> Path:
    load_dotenv()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("OPENROUTER_API_KEY not set")
    prompt = build_prompt(char_key, sheet)
    body = {
        "model": MODEL,
        "modalities": ["image", "text"],
        "image_config": {"aspect_ratio": SHEETS[sheet]["aspect"], "image_size": "2K"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": ref_image_data_url(char_key)}},
                ],
            }
        ],
    }
    t0 = time.time()
    r = requests.post(
        URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=body,
        timeout=600,
    )
    if r.status_code != 200:
        sys.exit(f"HTTP {r.status_code}: {r.text[:2000]}")
    data = r.json()
    msg = data["choices"][0]["message"]
    images = msg.get("images") or []
    if not images:
        sys.exit("no image returned. text: " + str(msg.get("content"))[:1000] + "\nraw: " + json.dumps(data)[:1500])
    url = images[0]["image_url"]["url"]
    if url.startswith("data:"):
        raw = base64.b64decode(url.split(",", 1)[1])
    else:
        raw = requests.get(url, timeout=120).content
    out = next_out_path(char_key, sheet)
    out.write_bytes(raw)
    usage = data.get("usage", {})
    print(f"saved {out}  ({len(raw)//1024} KB, {time.time()-t0:.0f}s, usage={usage})")
    if msg.get("content"):
        print("model text:", str(msg["content"])[:500])
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("character", nargs="?")
    ap.add_argument("sheet", nargs="?", choices=["turnaround", "expressions", "all"])
    ap.add_argument("--write-prompts", action="store_true")
    a = ap.parse_args()
    if a.write_prompts:
        write_prompts()
    if a.character:
        if a.character not in CFG["characters"]:
            sys.exit("unknown character: " + a.character)
        sheets = ["turnaround", "expressions"] if a.sheet in (None, "all") else [a.sheet]
        for s in sheets:
            generate(a.character, s)
