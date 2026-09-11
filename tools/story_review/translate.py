#!/usr/bin/env python3
"""Chinese to English for the review site's English mode, through Google Cloud Translation.

The page never holds the key. It posts text to /api/translate and server.py calls this
module, which calls Google (Translation Basic, v2) with GOOGLE_TRANSLATE_API_KEY. The key
is looked up like the model keys: environment, repo-root .env, then the private
ResearchAssets/config/story-pipeline.env.

Three things this gets right:

- Names. A character's Chinese name goes to Google fenced in <span translate="no"> with the
  website's English name already inside, so 陆姚 always comes back as Luyao and 牧师 as
  Mushi instead of "Lu Yao" one time and "Pastor" the next.
- Cost. Only text containing Chinese is sent, each distinct text once. Results are cached
  on disk, keyed by a hash of the text, so reopening the page or switching languages again
  costs nothing.
- Privacy. The cache holds translations of private candidates, so it lives in the private
  submodule under a gitignored .cache/. Note that the text itself does leave this machine
  for Google whenever something is translated for the first time.

    python tools/story_review/translate.py "陆姚今天又炸了"     # one live call, for checking the key
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINT = 'https://translation.googleapis.com/language/translate/v2'
KEY_NAME = 'GOOGLE_TRANSLATE_API_KEY'
CJK_RE = re.compile(r'[㐀-鿿豈-﫿]')
# Google accepts up to 128 segments per request and recommends keeping a request under
# about 5000 characters; staying below both avoids 400s on a long outline batch.
MAX_SEGMENTS = 100
MAX_CHARS = 4500
TIMEOUT = 30
# Bump when protect() or restore() change what a finished translation looks like; a cache
# written under another version is dropped rather than served.
CACHE_VERSION = 2


class TranslateError(Exception):
    """Google could not be reached or refused the request. Messages never include the key."""


class MissingKey(TranslateError):
    pass


def needs_translation(text) -> bool:
    return isinstance(text, str) and bool(CJK_RE.search(text))


def protect(text: str, names: dict[str, str]) -> str:
    """Prepare text for format=html: escape it, keep line breaks, fence off character names."""
    out = html.escape(text, quote=False)
    if names:
        pattern = re.compile('|'.join(re.escape(zh) for zh in sorted(names, key=len, reverse=True)))
        out = pattern.sub(lambda m: f'<span translate="no">{html.escape(names[m.group(0)], quote=False)}</span>', out)
    return out.replace('\n', '<br>')


def restore(translated: str) -> str:
    """Undo protect() on what Google sends back, including the spacing it adds around tags."""
    out = re.sub(r'\s*<br\s*/?>\s*', '\n', translated, flags=re.IGNORECASE)
    # Google leaves a space between a fenced name and punctuation after it: "Luyao 's", "Ruanruan ,".
    out = re.sub(r'(</span>)\s+(?=[\'’,.;:!?)\]]|&#39;)', r'\1', out, flags=re.IGNORECASE)
    out = re.sub(r'</?span\b[^>]*>', '', out, flags=re.IGNORECASE)
    return html.unescape(out).strip()


def batches(items: list, *, size=len, max_segments: int = MAX_SEGMENTS, max_chars: int = MAX_CHARS) -> list[list]:
    out, current, total = [], [], 0
    for item in items:
        n = size(item)
        if current and (len(current) >= max_segments or total + n > max_chars):
            out.append(current)
            current, total = [], 0
        current.append(item)
        total += n
    if current:
        out.append(current)
    return out


def google_translate(texts: list[str], *, key: str, source: str = 'zh-CN', target: str = 'en') -> list[str]:
    body = json.dumps({'q': texts, 'source': source, 'target': target, 'format': 'html'},
                      ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        method='POST',
        # The key goes in a header rather than the URL, so it cannot end up in a logged URL.
        headers={'Content-Type': 'application/json; charset=utf-8', 'X-Goog-Api-Key': key,
                 'User-Agent': 'qc-kindergarten-story-review/1'},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', 'replace')
        try:
            detail = json.loads(detail)['error']['message']
        except (ValueError, KeyError, TypeError):
            detail = detail[:300]
        raise TranslateError(f'Google Translate returned {exc.code}: {detail}') from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise TranslateError(f'could not reach Google Translate: {exc}') from None
    rows = (payload.get('data') or {}).get('translations') or []
    if len(rows) != len(texts):
        raise TranslateError(f'Google Translate returned {len(rows)} translations for {len(texts)} texts')
    return [str(row.get('translatedText', '')) for row in rows]


class Translator:
    def __init__(self, *, cache_path: Path | None, key_source, names: dict[str, str] | None = None,
                 backend=google_translate):
        self.cache_path = cache_path
        self.key_source = key_source            # () -> str | None, read on every call
        self.names = {zh: en for zh, en in (names or {}).items() if needs_translation(zh) and en}
        self.backend = backend
        self.lock = threading.Lock()
        # A different name list gives different translations, so it is part of the cache key.
        self.names_sig = hashlib.sha256(
            json.dumps(sorted(self.names.items()), ensure_ascii=False).encode('utf-8')).hexdigest()[:12]
        self.cache = self._load()

    def available(self) -> bool:
        return bool(self.key_source())

    def _cache_key(self, text: str, target: str) -> str:
        return hashlib.sha256(f'{target}\0{self.names_sig}\0{text}'.encode('utf-8')).hexdigest()

    def _load(self) -> dict:
        if not self.cache_path or not self.cache_path.exists():
            return {}
        try:
            data = json.loads(self.cache_path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('version') != CACHE_VERSION:
                return {}
            entries = data.get('entries')
            return dict(entries) if isinstance(entries, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self) -> None:
        if not self.cache_path:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_path.with_suffix('.tmp')
        tmp.write_text(json.dumps({'version': CACHE_VERSION, 'entries': self.cache}, ensure_ascii=False),
                       encoding='utf-8', newline='\n')
        os.replace(tmp, self.cache_path)

    def translate(self, texts: list[str], target: str = 'en') -> dict[str, str]:
        """Map each text to its translation. Text without Chinese maps to itself."""
        out: dict[str, str] = {}
        todo: list[str] = []
        with self.lock:
            for text in texts:
                if not needs_translation(text):
                    out[text] = text
                    continue
                hit = self.cache.get(self._cache_key(text, target))
                if hit is not None:
                    out[text] = hit
                elif text not in todo:
                    todo.append(text)
        if not todo:
            return out
        key = self.key_source()
        if not key:
            raise MissingKey(f'{KEY_NAME} is not set')
        pairs = [(text, protect(text, self.names)) for text in todo]
        for group in batches(pairs, size=lambda pair: len(pair[1])):
            results = self.backend([p for _, p in group], key=key, target=target)
            with self.lock:
                for (text, _), translated in zip(group, results):
                    english = restore(translated)
                    self.cache[self._cache_key(text, target)] = english
                    out[text] = english
                self._save()
        return out


def main() -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    here = Path(__file__).resolve().parent
    sys.path.insert(0, str(here.parents[1] / 'tools' / 'story_pipeline'))
    import adapters

    text = ' '.join(sys.argv[1:]) or '陆姚今天又炸了，牧师说他早就知道。'
    translator = Translator(cache_path=None, key_source=lambda: adapters.load_env().get(KEY_NAME),
                            names={'陆姚': 'Luyao', '牧师': 'Mushi'})
    try:
        print(translator.translate([text])[text])
    except TranslateError as exc:
        sys.exit(f'[translate] {exc}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
