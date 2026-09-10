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

REQUEST_TIMEOUT = 180      # HTTP
CLI_TIMEOUT = 600          # agent CLIs start a whole loop; they are slow


def load_env() -> dict:
    """Read .env without a dependency. Values are never logged."""
    env = dict(os.environ)
    path = ROOT / '.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, _, v = line.partition('=')
            env.setdefault(k.strip(), v.strip().strip('"\''))
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
    """Run a subscription CLI in a scratch directory.

    The scratch directory is the whole point. Claude Code and Codex read AGENTS.md /
    CLAUDE.md from their working directory, so running either inside the repo would hand
    it the entire project on top of the brief — while Kimi and DeepSeek only ever see the
    brief. The four inputs would stop being comparable and nothing would say so.
    """
    with tempfile.TemporaryDirectory(prefix='qck-brief-') as tmp:
        proc = subprocess.run(
            argv + [brief],
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


# The two CLI invocations are the ones most likely to drift: both tools iterate fast.
# If a round starts failing on them, check `claude --help` / `codex --help` first.
ADAPTERS = {
    'kimi': _http_adapter('kimi', 'MOONSHOT_API_KEY', 'https://api.moonshot.cn/v1', 'kimi-k2-0905-preview'),
    'deepseek': _http_adapter('deepseek', 'DEEPSEEK_API_KEY', 'https://api.deepseek.com/v1', 'deepseek-chat'),
    'claude': _cli_adapter('claude', 'claude', ['claude', '-p', '--allowed-tools', '']),
    'codex': _cli_adapter('codex', 'codex', ['codex', 'exec', '--skip-git-repo-check']),
}


# --------------------------------------------------------------------------- parsing

def parse_outlines(text: str) -> list[dict]:
    """Pull the outline array out of whatever the model actually returned.

    Tolerant on purpose. The HTTP models are pinned to json_object, but the CLIs are
    agents: they may open with "好的，这是三条大纲" or wrap the JSON in a fence. One
    formatting wobble must not cost the whole round, so anything unparseable is kept as
    raw text and flagged rather than dropped.
    """
    if not text or not text.strip():
        return []
    fenced = re.search(r'```(?:json)?\s*(.*?)```', text, re.S)
    body = fenced.group(1) if fenced else text

    for opener, closer in (('[', ']'), ('{', '}')):
        start, end = body.find(opener), body.rfind(closer)
        if start == -1 or end <= start:
            continue
        try:
            data = json.loads(body[start:end + 1])
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
        if isinstance(data, dict):
            # json_object mode cannot return a bare array, so a wrapper key is expected.
            for value in data.values():
                if isinstance(value, list) and all(isinstance(v, dict) for v in value):
                    return value
            return [data]
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
