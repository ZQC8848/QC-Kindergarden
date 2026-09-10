#!/usr/bin/env python3
"""Keep .claude/skills/ in sync with the canonical skills in .agents/skills/.

Two agents work on this repo and they read different directories:
Codex reads `.agents/skills/`, Claude Code reads `.claude/skills/`. Keeping two
full copies means silent drift (it already happened once with fieldnotes), so
`.agents/skills/` holds the only implementation and `.claude/skills/<name>/SKILL.md`
is a three-line stub: the same frontmatter, plus a line telling the agent where the
real instructions are. Only `name` and `description` are duplicated, and this script
is what keeps those two fields honest.

Run from the repository root:
    python tools/skill_stubs.py            # verify, exit 1 on any drift
    python tools/skill_stubs.py --write    # regenerate the stubs
"""
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
CANON = ROOT / ".agents" / "skills"
STUBS = ROOT / ".claude" / "skills"


def frontmatter(path: Path) -> dict[str, str]:
    """Parse the leading --- block. Values may span lines; keys are top level only."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.index("\n---", 3)
    fields: dict[str, str] = {}
    key = None
    for line in text[3:end].split("\n"):
        if not line.strip():
            continue
        if not line.startswith((" ", "\t")) and ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            fields[key] = value.strip()
        elif key:
            fields[key] += " " + line.strip()
    return fields


def unquote(value: str) -> str:
    """Undo one layer of YAML quoting so a value is stored plain in memory."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        inner = value[1:-1]
        if value[0] == '"':
            return inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner.replace("''", "'")
    return value


# A bare ": " inside an unquoted description makes the frontmatter invalid YAML, which
# silently breaks skill discovery. It already did, for translate-en. Quote only when the
# value needs it, so the common case stays readable in the agent's skill listing.
_YAML_INDICATORS = ("#", "&", "*", "!", "|", ">", "'", '"', "%", "@", "`", "[", "]", "{", "}", ",")


def needs_quote(value: str) -> bool:
    if not value or value != value.strip():
        return True
    if value[0] in _YAML_INDICATORS or value.startswith("- "):
        return True
    return ": " in value or value.endswith(":") or " #" in value


def yaml_quote(value: str) -> str:
    if not needs_quote(value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def stub_text(name: str, description: str) -> str:
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {yaml_quote(description)}\n"
        "---\n"
        "\n"
        f"正本在 `.agents/skills/{name}/SKILL.md`，先读它再执行。\n"
        f"参考文件、脚本和示例都在 `.agents/skills/{name}/` 下。\n"
        "\n"
        "这个文件是转发桩，由 `tools/skill_stubs.py` 生成，不要在这里写内容。\n"
    )


def main() -> int:
    write = "--write" in sys.argv
    if not CANON.is_dir():
        print(f"canonical skills not found: {CANON}", file=sys.stderr)
        return 1

    canonical = {d.name: d / "SKILL.md" for d in sorted(CANON.iterdir()) if (d / "SKILL.md").is_file()}
    problems: list[str] = []

    for name, path in canonical.items():
        fm = frontmatter(path)
        if fm.get("name") != name:
            problems.append(f"{name}: frontmatter name is {fm.get('name')!r}, expected {name!r}")
            continue
        if not fm.get("description"):
            problems.append(f"{name}: canonical SKILL.md has no description")
            continue
        raw = fm["description"]
        if not raw.startswith(('"', "'")) and ": " in raw:
            problems.append(
                f"{name}: canonical description has a bare ': ' and is invalid YAML; "
                "reword it or wrap the value in double quotes in .agents/skills/"
            )
            continue
        want = stub_text(name, unquote(raw))
        stub = STUBS / name / "SKILL.md"
        have = stub.read_text(encoding="utf-8") if stub.is_file() else None
        if have == want:
            continue
        if write:
            stub.parent.mkdir(parents=True, exist_ok=True)
            stub.write_text(want, encoding="utf-8")
            print(f"wrote {stub.relative_to(ROOT)}")
        else:
            problems.append(f"{name}: stub is {'missing' if have is None else 'out of date'}")

    # stubs with no canonical skill behind them
    if STUBS.is_dir():
        for d in sorted(STUBS.iterdir()):
            if not d.is_dir() or d.name in canonical:
                continue
            if write:
                for f in sorted(d.rglob("*"), reverse=True):
                    f.unlink() if f.is_file() else f.rmdir()
                d.rmdir()
                print(f"removed orphan stub {d.relative_to(ROOT)}")
            else:
                problems.append(f"{d.name}: stub has no skill in .agents/skills/")

    if problems:
        print("skill stubs out of sync:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print("run: python tools/skill_stubs.py --write", file=sys.stderr)
        return 1
    print(f"skill stubs in sync ({len(canonical)} skills).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
