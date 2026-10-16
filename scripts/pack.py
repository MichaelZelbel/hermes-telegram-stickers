#!/usr/bin/env python3
"""Pack helpers shared by the scripts in this folder. Standard library only.

    python3 scripts/pack.py check <pack>            check a pack against Telegram's sticker rules
    python3 scripts/pack.py check --all             check every pack, and that they share the tags
    python3 scripts/pack.py set-name <pack> <bot>   the set name Telegram will give it under <bot>
    python3 scripts/pack.py tags                    the tags every set has, with their first emoji

publish-set.sh also uses `list`, `title`, `count`, `files`, `input-stickers`, `plan` and `record`.
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKS = os.path.join(ROOT, 'packs')
MAX_BYTES = 512 * 1024
PLACEHOLDER_FILES = ('README.md', 'CONTRIBUTING.md',
                     os.path.join('hermes-plugin', 'README.md'),
                     os.path.join('hermes-plugin', '__init__.py'))

# The moments every set has, in set order: (tag, the sticker's FIRST emoji, what it means).
# The Hermes plugin finds a sticker by that first emoji, so it is the same in every set, and
# hermes-plugin/__init__.py carries the same list (a test keeps the two equal).
TAGS = [
    ('today', '\U0001F3A7', 'here and listening'),
    ('onit', '\U0001F4BB', 'on it'),
    ('note', '\U0001F4DD', 'a note for you'),
    ('copy', '\U0001F4E1', 'do you copy? I need your yes'),
    ('fix', '\U0001F527', 'fixing it'),
    ('done', '\U0001FAE1', 'done'),
    ('quiet', '\U0001F634', 'keeping quiet watch'),
    ('ok', '\U0001F44D', 'got it'),
    ('think', '\U0001F914', 'thinking it over'),
    ('found', '\U0001F50D', 'found it'),
    ('oops', '\U0001F605', 'my mistake'),
    ('party', '\U0001F389', 'good news'),
    ('thanks', '\U0001F64F', 'thank you'),
    ('morning', '\u2615', 'good morning'),
    ('night', '\U0001F319', 'good night'),
]
TAG_EMOJI = {tag: emoji for tag, emoji, _ in TAGS}
TAG_ORDER = [tag for tag, _, _ in TAGS]


def plain(emoji: str) -> str:
    """The emoji itself, without the invisible variation selector (U+FE0F)."""
    return (emoji or '').replace('\ufe0f', '').strip()


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
    unknown = [p for p in poses if p not in TAG_EMOJI]
    if unknown:
        out.append('unknown tag(s) %s; every sticker is one of: %s'
                   % (', '.join(map(repr, unknown)), ', '.join(TAG_ORDER)))
    if len(set(poses)) != len(poses):
        out.append('every tag may appear only once')
    order = [TAG_ORDER.index(p) for p in poses if p in TAG_EMOJI]
    if order != sorted(order):
        out.append('stickers must follow the tag order: %s' % ', '.join(TAG_ORDER))
    owners = {}  # emoji -> the stickers that carry it
    for s in stickers:
        for e in s.get('emoji') or []:
            owners.setdefault(plain(e), []).append(s.get('pose') or s.get('file', '?'))
    for e, who in owners.items():
        if len(who) > 1:
            out.append('emoji %s is on more than one sticker (%s); each emoji may belong to one '
                       'sticker only' % (e, ', '.join(who)))
    for s in stickers:
        label = s.get('file', '?')
        emoji = s.get('emoji')
        if not isinstance(emoji, list) or not 1 <= len(emoji) <= 20:
            out.append('%s: "emoji" must be a list of 1 to 20 emoji' % label)
        elif s.get('pose') in TAG_EMOJI and plain(emoji[0]) != plain(TAG_EMOJI[s['pose']]):
            out.append('%s: the first emoji of tag %r must be %s (the plugin finds it by that)'
                       % (label, s['pose'], TAG_EMOJI[s['pose']]))
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


def shared_tag_problems(packs: list[str]) -> list[str]:
    """Every set has the same tags, so switching sets in the plugin is one setting."""
    tag_lists = {}
    for p in packs:
        try:
            tag_lists[p] = [s.get('pose') for s in load(p).get('stickers', [])]
        except (OSError, ValueError):
            continue
    if len({tuple(v) for v in tag_lists.values()}) <= 1:
        return []
    return ['the packs do not all have the same tags: %s' % '; '.join(
        '%s has %s' % (p, ', '.join(v)) for p, v in tag_lists.items())]


def plan(pack: str, existing: dict) -> list[str]:
    """What publishing `pack` to the set Telegram already has (`existing`, a getStickerSet result)
    takes, as ASCII lines for publish-set.sh:
      mismatch <position> <tag>          the set's sticker there is not the manifest's (stop)
      emoji <file_id> <emoji list JSON>  give an existing sticker the manifest's emoji list
      title                              the set's title differs from the manifest's
      add <index>                        add the manifest's sticker <index> at the end
      extra <count>                      the set has stickers the manifest does not list"""
    m = load(pack)
    wanted = m['stickers']
    have = existing.get('stickers', [])
    lines = []
    for i, (st, mine) in enumerate(zip(have, wanted)):
        if plain(st.get('emoji', '')) != plain(mine['emoji'][0]):
            lines.append('mismatch %d %s' % (i + 1, mine.get('pose', '?')))
    if lines:
        return lines
    for st, mine in zip(have, wanted):
        lines.append('emoji %s %s' % (st['file_id'], json.dumps(mine['emoji'])))
    if existing.get('title') != m['title']:
        lines.append('title')
    lines += ['add %d' % i for i in range(len(have), len(wanted))]
    if len(have) > len(wanted):
        lines.append('extra %d' % (len(have) - len(wanted)))
    return lines


def record(pack: str, name: str) -> list[str]:
    """After publishing: store the set in the manifest, and put its name in the docs and the
    Hermes plugin wherever they name this pack's set: the `<pack>_by_<BOT>` placeholder, or the
    set recorded before (so a fork published under another bot links to its own set
    everywhere). Returns the files changed."""
    m = load(pack)
    previous = m.get('telegram_set_name') or ''
    m['telegram_set_name'] = name
    m['telegram_set'] = 'https://t.me/addstickers/' + name
    save(pack, m)
    changed = [os.path.join('packs', pack, 'manifest.json')]
    olds = ['%s_by_<BOT>' % base_name(m)]
    if previous and previous != name:
        olds.append(previous)
    # Whole set names only: "speedy_by_Bot" must not match inside "speedy_by_BotTwo".
    pattern = re.compile('|'.join('(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])' % re.escape(o) for o in olds))
    for rel in PLACEHOLDER_FILES:
        path = os.path.join(ROOT, rel)
        try:
            with open(path, encoding='utf-8', newline='') as fh:
                text = fh.read()
        except OSError:
            continue
        new = pattern.sub(name, text)
        if new != text:
            with open(path, 'w', encoding='utf-8', newline='') as fh:
                fh.write(new)
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
        for line in shared_tag_problems(all_packs()):
            bad += 1
            print('- ' + line)
        return 1 if bad else 0
    if cmd == 'list' and not args:
        print('\n'.join(all_packs()))
        return 0
    if cmd == 'tags' and not args:
        for tag, emoji, meaning in TAGS:
            print('%-8s %s  %s' % (tag, emoji, meaning))
        return 0
    if cmd == 'plan' and len(args) == 1:
        existing = json.loads(sys.stdin.buffer.read().decode('utf-8'))
        print('\n'.join(plan(args[0], existing.get('result', existing))))
        return 0
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
