#!/usr/bin/env python3
"""Print the file_id of every sticker in a set, as YOUR bot sees it.

Telegram gives every bot its own file_id for the same sticker, and a file_id from one bot does
not work for another. So nobody can hand you working ids: your bot has to ask for them. This
script asks Telegram once (getStickerSet, with your bot's token) and prints them.

    BOT_TOKEN=<your bot token> python3 scripts/file-ids.py [set name or t.me link] [--json | --prompt]

Without a set name it uses the Speedy set from packs/speedy/manifest.json.
  (default)  one line per sticker: pose, emoji, file_id
  --json     {"done": "<file_id>", ...}, for a config file
  --prompt   ready-made instructions for an OpenCLAW agent, ids filled in

Reads the token from BOT_TOKEN (or TELEGRAM_BOT_TOKEN); never prints it.
TELEGRAM_API_BASE points it at another Bot API server (default https://api.telegram.org).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pack  # noqa: E402


def plain(emoji: str) -> str:
    return (emoji or '').replace('️', '').strip()


def get_set(token: str, name: str) -> dict:
    api = os.environ.get('TELEGRAM_API_BASE', 'https://api.telegram.org').rstrip('/')
    req = urllib.request.Request('%s/bot%s/getStickerSet' % (api, token),
                                 data=json.dumps({'name': name}).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            got = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as err:
        try:
            got = json.loads(err.read().decode('utf-8'))
        except ValueError:
            got = {'ok': False, 'description': 'HTTP %s' % err.code}
    except (urllib.error.URLError, OSError) as err:
        raise SystemExit('Could not reach Telegram: %s' % str(err).replace(token, '<token>'))
    if not got.get('ok'):
        raise SystemExit('Telegram says: %s (set %r)' % (got.get('description', 'no reason given'), name))
    return got['result']


def find_manifest(name: str):
    """The pack this set was made from: by its recorded set name, else by its pack name."""
    for p in pack.all_packs():
        m = pack.load(p)
        if m.get('telegram_set_name') and m['telegram_set_name'].lower() == name.lower():
            return m
    for p in pack.all_packs():
        m = pack.load(p)
        if name.lower().startswith(pack.base_name(m).lower() + '_by_'):
            return m
    return None


def label(stickers: list, manifest) -> list:
    """[(pose, emoji, file_id, when)] in set order. Poses come from the manifest by emoji."""
    by_emoji = {}
    if manifest:
        for s in manifest['stickers']:
            by_emoji.setdefault(plain(s['emoji'][0]), s)
    rows = []
    for i, st in enumerate(stickers):
        info = by_emoji.get(plain(st.get('emoji', '')))
        if info is None and manifest and len(manifest['stickers']) == len(stickers):
            info = manifest['stickers'][i]
        pose = info['pose'] if info else 'sticker%d' % (i + 1)
        rows.append((pose, st.get('emoji', ''), st['file_id'], info.get('when', '') if info else ''))
    return rows


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    args = [a for a in argv[1:] if not a.startswith('--')]
    flags = {a for a in argv[1:] if a.startswith('--')}
    if flags - {'--json', '--prompt', '--help'} or '--help' in flags or len(args) > 1:
        print(__doc__.strip())
        return 2 if '--help' not in flags else 0
    token = os.environ.get('BOT_TOKEN') or os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        print('Set BOT_TOKEN to your bot\'s token first (the one @BotFather gave you).')
        return 2
    if args:
        name = args[0].rstrip('/').split('/')[-1]
    else:
        name = pack.load('speedy').get('telegram_set_name') or ''
        if not name:
            print('The Speedy set has not been published yet; pass a set name.')
            return 2
    result = get_set(token, name)
    rows = label(result['stickers'], find_manifest(result.get('name', name)))
    if '--json' in flags:
        print(json.dumps({pose: fid for pose, _, fid, _ in rows}, ensure_ascii=False, indent=2))
    elif '--prompt' in flags:
        print('Stickers you can send on Telegram (use the "sticker" action with the fileId):')
        for pose, emoji, fid, when in rows:
            if when:
                print('- When %s, send sticker %s (%s %s).' % (when, fid, emoji, pose))
            else:
                print('- Sticker %s (%s %s).' % (fid, emoji, pose))
        print('Send at most one sticker per reply, and only when one of these moments fits.')
    else:
        print('# %s (%s), file_ids for this bot only' % (result.get('title', ''), result.get('name', name)))
        width = max(len(r[0]) for r in rows) if rows else 0
        for pose, emoji, fid, _ in rows:
            print('%s  %s  %s' % (pose.ljust(width), emoji, fid))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
