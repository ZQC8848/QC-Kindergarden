#!/usr/bin/env python3
"""Four models behind one signature: generate(brief) -> str.

Two of them are HTTP calls to OpenAI-compatible endpoints, two are subscription CLIs run
as subprocesses. Nothing above this module knows or cares which is which.

    python tools/story_pipeline/adapters.py --list        # which are usable right now
    python tools/story_pipeline/adapters.py --test kimi   # one tiny live call
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Both were set when a call meant "write two sentences" and neither moved when the task
# became "write a whole short story". Round r02 lost 8 of 17 calls to them: every kimi
# call hit 300s and every claude call hit 600s, while deepseek finished a 6500-character
# story inside the same window. The work got an order of magnitude bigger; so do these.
REQUEST_TIMEOUT = 900      # HTTP
CLI_TIMEOUT = 1800         # agent CLIs run a whole loop before they write a word


def load_env() -> dict:
    """Keys, in precedence order: environment, repo-root .env, private submodule config.

    Same chain as .agents/skills/discord-notify. The repo-root .env is gitignored, so a
    key put there stays on one machine; ResearchAssets/config/ is the committed private
    location that survives a fresh clone. Values are never logged.
    """
    env = dict(os.environ)
    for path in (ROOT / '.env', ROOT / 'ResearchAssets' / 'config' / 'story-pipeline.env'):
        if not path.exists():
            continue
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, _, v = line.partition('=')
            v = v.strip().strip('"\'')
            if v and not v.startswith('your-'):  # skip .env.example-style placeholders
                env.setdefault(k.strip(), v)
    return env


# --------------------------------------------------------------------------- HTTP

def _post_openai_compatible(base_url: str, api_key: str, model: str, brief: str) -> str:
    import urllib.request

    body = json.dumps(
        {
            'model': model,
            'messages': [{'role': 'user', 'content': brief}],
            'temperature': 1.0,
            # Both endpoints implement OpenAI's json_object mode. The prompt already asks
            # for an array; json_object forces valid JSON around it, which removes most
            # (not all) of the parsing risk.
            'response_format': {'type': 'json_object'},
        },
        ensure_ascii=False,
    ).encode('utf-8')
    req = urllib.request.Request(
        base_url.rstrip('/') + '/chat/completions',
        data=body,
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        payload = json.loads(resp.read().decode('utf-8'))
    return payload['choices'][0]['message']['content']


# --------------------------------------------------------------------------- CLI

def _run_cli(argv: list[str], brief: str) -> str:
    """Run a subscription CLI in a scratch directory, feeding the brief over stdin.

    Two things this gets right, both learned the hard way.

    The scratch directory: Claude Code and Codex read AGENTS.md / CLAUDE.md from their
    working directory, so running either inside the repo would hand it the whole project
    on top of the brief, while Kimi and DeepSeek only ever see the brief. The four inputs
    would stop being comparable and nothing would say so.

    stdin rather than argv: Windows caps a command line at 32767 characters and the brief
    is around 36000. Passed as an argument it would fail outright, or worse, truncate.
    """
    # subprocess does not apply PATHEXT, so a bare "claude" misses claude.CMD even though
    # shutil.which finds it. Resolve to the full path before spawning.
    resolved = shutil.which(argv[0])
    if not resolved:
        raise RuntimeError(f'{argv[0]} not on PATH')
    with tempfile.TemporaryDirectory(prefix='qck-brief-') as tmp:
        proc = subprocess.run(
            [resolved, *argv[1:]],
            input=brief,
            cwd=tmp,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=CLI_TIMEOUT,
        )
    if proc.returncode != 0:
        raise RuntimeError(f'{argv[0]} exited {proc.returncode}: {(proc.stderr or proc.stdout)[-500:]}')
    return proc.stdout


@dataclass
class Adapter:
    name: str
    kind: str            # http | cli
    generate: object
    available: object    # () -> (bool, str)


def _http_adapter(name: str, env_key: str, base_url: str, model: str) -> Adapter:
    def available():
        key = load_env().get(env_key)
        return (bool(key), 'ok' if key else f'{env_key} not set in .env')

    def generate(brief: str) -> str:
        key = load_env().get(env_key)
        if not key:
            raise RuntimeError(f'{env_key} not set in .env')
        return _post_openai_compatible(base_url, key, model, brief)

    return Adapter(name, 'http', generate, available)


def _cli_adapter(name: str, exe: str, argv: list[str]) -> Adapter:
    def available():
        if not shutil.which(exe):
            return (False, f'{exe} not on PATH')
        return (True, 'ok')

    def generate(brief: str) -> str:
        if not shutil.which(exe):
            raise RuntimeError(f'{exe} not on PATH')
        return _run_cli(argv, brief)

    return Adapter(name, 'cli', generate, available)


# Every adapter is pinned to the strongest tier its account can reach, verified against
# each provider's live catalogue on 2026-09-10 rather than assumed. The CLI invocations
# are the ones most likely to drift: both tools iterate fast, so if a round starts failing
# on them check `claude --help` / `codex --help` first.
ADAPTERS = {
    # Moonshot runs two separate regions with separate keys: api.moonshot.cn (CN) and
    # api.moonshot.ai (international). A key from one returns 401 on the other; this
    # project's key is on .ai, whose catalogue is kimi-k3, kimi-k2.6 and two -code
    # variants. k3 is the newest general model; the -code ones are code-specialised and
    # wrong for prose.
    'kimi': _http_adapter('kimi', 'MOONSHOT_API_KEY', 'https://api.moonshot.ai/v1', 'kimi-k3'),
    # The catalogue lists deepseek-v4-pro and deepseek-flash. `deepseek-chat`, used until
    # now, still answers but is a legacy alias that appears in neither — so it was an
    # unknown tier. -flash is the cheap fast one; -v4-pro is the flagship.
    'deepseek': _http_adapter('deepseek', 'DEEPSEEK_API_KEY', 'https://api.deepseek.com/v1', 'deepseek-v4-pro'),
    # Both read the prompt from stdin: `claude -p` with no prompt argument, `codex exec -`.
    # Opus at max effort is the top of what the subscription reaches.
    'claude': _cli_adapter('claude', 'claude', ['claude', '-p', '--model', 'opus', '--effort', 'max']),
    # codex exec has no --effort flag; reasoning effort goes through a config override.
    # --skip-git-repo-check: the scratch directory is deliberately not a git repo.
    'codex': _cli_adapter('codex', 'codex',
                          ['codex', 'exec', '--skip-git-repo-check',
                           '-c', 'model_reasoning_effort="high"', '-']),
}


# --------------------------------------------------------------------------- parsing

def parse_outlines(text: str) -> list[dict]:
    """Pull the story object(s) out of whatever the model actually returned.

    Tolerant on purpose. The HTTP models are pinned to json_object, but the CLIs are
    agents: they may open with "好的，这是故事" or wrap the JSON in a fence, and codex
    prints its own chrome around the answer. One formatting wobble must not cost a call,
    so anything unparseable is kept as raw text and flagged rather than dropped.

    Candidates are objects now, and objects contain arrays — `cast` is one. An earlier
    version looked for the outermost `[...]` first and happily parsed `["haide"]` out of
    the cast field, yielding zero dicts and reporting every story as unparseable. So a
    parse only counts when it produces at least one dict.
    """
    if not text or not text.strip():
        return []

    def harvest(value) -> list[dict]:
        if isinstance(value, dict):
            # json_object mode cannot return a bare array, so a wrapper key is expected.
            for v in value.values():
                if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
                    return v
            return [value]
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
        return []

    candidates = [text]
    fenced = re.findall(r'```(?:json)?\s*(.*?)```', text, re.S)
    candidates = fenced + candidates
    for body in candidates:
        for opener, closer in (('{', '}'), ('[', ']')):
            start, end = body.find(opener), body.rfind(closer)
            if start == -1 or end <= start:
                continue
            try:
                found = harvest(json.loads(body[start:end + 1]))
            except json.JSONDecodeError:
                continue
            if found:
                return found
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--test', metavar='NAME', help='send one tiny prompt to that adapter')
    args = ap.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    if args.test:
        a = ADAPTERS[args.test]
        out = a.generate('Reply with exactly this JSON and nothing else: {"ok": true}')
        print(out.strip()[:400])
        print('parsed:', parse_outlines(out))
        return 0

    for name, a in ADAPTERS.items():
        ok, why = a.available()
        print(f'{name:9} {a.kind:5} {"available" if ok else "unavailable"}  {why}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
