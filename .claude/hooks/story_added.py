"""PostToolUse hook: fires after Write/Edit. If the written file is a story under stories/,
tell Claude to ask the user whether the story's new settings should be merged into the
characters' 性格设定.md. Never modifies anything itself.

Input: hook JSON on stdin. Output: hook JSON on stdout (only when a story file matched)."""
import json
import re
import sys

# Windows defaults stdin/stdout to the ANSI code page; hook JSON is UTF-8.
for stream in (sys.stdin, sys.stdout):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

path = (
    (data.get("tool_input") or {}).get("file_path")
    or (data.get("tool_response") or {}).get("filePath")
    or ""
)
path = str(path).replace("\\", "/")

# stories/<anything>.md, but not the folder README
if not re.search(r"/stories/[^/]+\.md$", path) or path.endswith("/README.md"):
    sys.exit(0)

name = path.rsplit("/", 1)[-1]
out = {
    "systemMessage": f"故事集新增/修改：{name}。Claude 会向你确认是否回写角色 性格设定.md。",
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": (
            f"A story file was just written: {path}. Project rule: story files never auto-update "
            "character bibles. Before you end this turn, use AskUserQuestion to ask the user whether "
            "the new settings in this story should be merged into the relevant characters' "
            "`character reference/<角色>/性格设定.md` (list which characters and what would change). "
            "Only edit the bibles if the user answers yes."
        ),
    },
}
sys.stdout.write(json.dumps(out, ensure_ascii=False))
