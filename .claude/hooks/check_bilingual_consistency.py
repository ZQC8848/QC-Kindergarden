"""PostToolUse hook: audit Chinese/English website content after content edits.

The deterministic audit checks translation coverage and structure. The hook also
adds a semantic-review reminder because a script cannot prove that two literary
texts mean the same thing.
"""
import json
import os
from pathlib import Path
import subprocess
import sys


for stream in (sys.stdin, sys.stdout):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def written_path(data: dict) -> str:
    path = (
        (data.get("tool_input") or {}).get("file_path")
        or (data.get("tool_response") or {}).get("filePath")
        or ""
    )
    return str(path).replace("\\", "/")


def is_bilingual_content(path: str) -> bool:
    lower = "/" + path.lower().lstrip("/")
    if "/stories/" in lower and lower.endswith(".md") and not lower.endswith("/readme.md"):
        return True
    if "/character reference/" in lower and lower.endswith(".md") and "性格设定" in path:
        return True
    return lower.endswith("/website/src/i18n.ts") or lower.endswith(
        "/website/src/data/characters.config.mjs"
    )


try:
    event = json.load(sys.stdin)
except Exception:
    sys.exit(0)

path = written_path(event)
if not is_bilingual_content(path):
    sys.exit(0)

project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
audit = project_dir / "tools" / "audit_en.py"

try:
    result = subprocess.run(
        [sys.executable, str(audit)],
        cwd=project_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    report = (result.stdout or result.stderr or "(no audit output)").strip()
except Exception as exc:
    result = None
    report = f"audit could not run: {exc}"

passed = result is not None and result.returncode == 0
status = "通过" if passed else "发现不一致"
if len(report) > 4000:
    report = report[:4000] + "\n… (truncated)"

if passed:
    instruction = (
        "The structural bilingual audit passed. If this edit changed wording or story facts, "
        "read the complete Chinese file and its English twin and compare them for semantic, "
        "character-voice, joke-function, and illustration-caption parity before finishing. "
        "The deterministic audit cannot prove literary equivalence. Use the translate-en skill."
    )
else:
    instruction = (
        "The bilingual audit found a mismatch. Do not treat this website content update as "
        "complete until the reported issue is fixed and the audit passes. Then compare the "
        "complete Chinese and English pair for semantic, character-voice, joke-function, and "
        "illustration-caption parity. Use the translate-en skill."
    )

output = {
    "systemMessage": f"中英文一致性检查：{status}。\n{report}",
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": f"Content file changed: {path}\n\n{instruction}\n\nAudit output:\n{report}",
    },
}
sys.stdout.write(json.dumps(output, ensure_ascii=False))
