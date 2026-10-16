#!/usr/bin/env python3
"""Pack helpers shared by the scripts in this folder. Standard library only.

    python3 scripts/pack.py check <pack>            check a pack against Telegram's sticker rules
    python3 scripts/pack.py check --all             check every pack
    python3 scripts/pack.py set-name <pack> <bot>   the set name Telegram will give it under <bot>

publish-set.sh also uses `input-stickers`, `files` and `record`.
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKS = os.path.join(ROOT, 'packs')
MAX_BYTES = 512 * 1024
PLACEHOLDER_FILES = ('README.md', 'INTEGRATIONS.md', 'CONTRIBUTING.md',
                     os.path.join('hermes-plugin', 'README.md'),
                     os.path.join('hermes-plugin', '__init__.py'))


def manifest_path(pack: str) -> str:
    return os.path.join(PACKS, pack, 'manifest.json')


def load(pack: str) -> dict:
    with open(manifest_path(pack), encoding='utf-8') as fh:
        return json.load(fh)


def save(pack: str, manifest: dict) -> None:
    """Write the manifest back in the same shape it is kept in: one line per sticker."""
    lines = ['{']
    keys = [k for k in manifest if k != 'stickers']
    for k in keys:
        lines.append('  %s: %s,' % (json.dumps(k), json.dumps(manifest[k], ensure_ascii=False)))
    lines.append('  "stickers": [')
    stickers = manifest.get('stickers', [])
    for i, s in enumerate(stickers):
        body = ', '.join('%s: %s' % (json.dumps(k), json.dumps(v, ensure_ascii=False))
                         for k, v in s.items())
        lines.append('    { %s }%s' % (body, ',' if i < len(stickers) - 1 else ''))
    lines.append('  ]')
    lines.append('}')
    tmp = manifest_path(pack) + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(lines) + '\n')
    os.replace(tmp, manifest_path(pack))


def base_name(manifest: dict) -> str:
    """The pack name as Telegram allows it in a set name: letters, digits, single underscores."""
    return re.sub(r'_+', '_', re.sub(r'[^A-Za-z0-9_]', '_', manifest['name'])).strip('_')


def set_name(manifest: dict, bot_username: str) -> str:
    return '%s_by_%s' % (base_name(manifest), bot_username.lstrip('@'))


def png_size(path: str):
    with open(path, 'rb') as fh:
        head = fh.read(24)
    if head[:8] != b'\x89PNG\r\n\x1a\n' or head[12:16] != b'IHDR':
        return None
    return int.from_bytes(head[16:20], 'big'), int.from_bytes(head[20:24], 'big')


def problems(pack: str) -> list[str]:
    """Everything that would stop Telegram (or this repo) from taking the pack. Empty means fine."""
    out = []
    try:
        m = load(pack)
    except (OSError, ValueError) as exc:
        return ['manifest.json: %s' % exc]
    name = m.get('name', '')
    if name != pack:
        out.append('manifest name %r should match the folder name %r' % (name, pack))
    base = base_name(m) if name else ''
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', base or '-'):
        out.append('pack name %r must start with a letter and use letters, digits, - or _' % name)
    if len(base) > 30:
        out.append('pack name %r is too long (keep it to 30 characters or fewer)' % name)
    title = m.get('title', '')
    if not 1 <= len(title) <= 64:
        out.append('title must be 1 to 64 characters')
    stickers = m.get('stickers') or []
    if not 1 <= len(stickers) <= 50:
        out.append('a pack needs 1 to 50 stickers to be published in one go')
    poses = [s.get('pose') for s in stickers]
    if any(not p or not re.fullmatch(r'[a-z0-9_-]+', p) for p in poses):
        out.append('every sticker needs a "pose": lowercase letters, digits, - or _')
    if len(set(poses)) != len(poses):
        out.append('pose names must be unique')
    firsts = [(s.get('emoji') or [''])[0] for s in stickers]
    if len(set(firsts)) != len(firsts):
        out.append('the first emoji of every sticker must be unique (it is how a bot finds it)')
    for s in stickers:
        label = s.get('file', '?')
        emoji = s.get('emoji')
        if not isinstance(emoji, list) or not 1 <= len(emoji) <= 20:
            out.append('%s: "emoji" must be a list of 1 to 20 emoji' % label)
        if 'file_id' in s:
            out.append('%s: no file_id in a manifest; every bot gets its own (see scripts/file-ids.py)'
                       % label)
        path = os.path.join(PACKS, pack, s.get('file', ''))
        if not s.get('file') or not os.path.isfile(path):
            out.append('%s: file missing' % label)
            continue
        size = png_size(path)
        if size is None:
            out.append('%s: not a PNG' % label)
            continue
        w, h = size
        if max(w, h) != 512 or min(w, h) < 1:
            out.append('%s: is %dx%d; one side must be exactly 512 px and the other 512 or less'
                       % (label, w, h))
        if os.path.getsize(path) > MAX_BYTES:
            out.append('%s: %d KB, over Telegram\'s 512 KB limit'
                       % (label, os.path.getsize(path) // 1024))
    return out


def all_packs() -> list[str]:
    return sorted(d for d in os.listdir(PACKS) if os.path.isfile(manifest_path(d)))


def record(pack: str, name: str) -> list[str]:
    """After publishing: store the set in the manifest and fill in the `<pack>_by_<BOT>`
    placeholders in the docs and the Hermes plugin. Returns the files changed."""
    m = load(pack)
    m['telegram_set_name'] = name
    m['telegram_set'] = 'https://t.me/addstickers/' + name
    save(pack, m)
    changed = [os.path.join('packs', pack, 'manifest.json')]
    placeholder = '%s_by_<BOT>' % base_name(m)
    for rel in PLACEHOLDER_FILES:
        path = os.path.join(ROOT, rel)
        try:
            with open(path, encoding='utf-8', newline='') as fh:
                text = fh.read()
        except OSError:
            continue
        if placeholder in text:
            with open(path, 'w', encoding='utf-8', newline='') as fh:
                fh.write(text.replace(placeholder, name))
            changed.append(rel)
    return changed


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        # emoji even on a Windows console, and plain \n so bash reads clean lines everywhere
        sys.stdout.reconfigure(encoding='utf-8', newline='\n')
    if len(argv) < 2:
        print(__doc__.strip())
        return 2
    cmd, args = argv[1], argv[2:]
    if cmd == 'check':
        packs = all_packs() if args == ['--all'] else args[:1]
        if not packs:
            print('usage: pack.py check <pack> | --all')
            return 2
        bad = 0
        for p in packs:
            found = problems(p)
            if found:
                bad += 1
                print('%s: %d problem(s)' % (p, len(found)))
                for line in found:
                    print('  - ' + line)
            else:
                print('%s: ok (%d stickers)' % (p, len(load(p)['stickers'])))
        return 1 if bad else 0
    if cmd == 'set-name' and len(args) == 2:
        print(set_name(load(args[0]), args[1]))
        return 0
    if cmd == 'title' and len(args) == 1:
        print(load(args[0])['title'])
        return 0
    if cmd == 'files' and len(args) == 1:
        for s in load(args[0])['stickers']:
            print(os.path.join(PACKS, args[0], s['file']))
        return 0
    if cmd == 'input-stickers' and len(args) in (1, 2):
        # JSON InputSticker list for createNewStickerSet; with a start index, one per line from
        # there on (for addStickerToSet). Files are attached as s0, s1, ...
        stickers = load(args[0])['stickers']
        start = int(args[1]) if len(args) == 2 else None
        items = [{'sticker': 'attach://s%d' % i, 'format': 'static', 'emoji_list': s['emoji']}
                 for i, s in enumerate(stickers)]
        if start is None:
            print(json.dumps(items))  # ASCII only: it travels as a command-line argument
        else:
            for item in items[start:]:
                print(json.dumps(item))
        return 0
    if cmd == 'count' and len(args) == 1:
        print(len(load(args[0])['stickers']))
        return 0
    if cmd == 'record' and len(args) == 2:
        for path in record(args[0], args[1]):
            print('  updated ' + path.replace(os.sep, '/'))
        return 0
    print(__doc__.strip())
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
