#!/usr/bin/env python3
"""Print the file_id of every sticker in a set, as YOUR bot sees it.

Telegram gives every bot its own file_id for the same sticker, and a file_id from one bot does
not work for another. The Hermes plugin therefore looks the ids up itself; this script does the
same lookup by hand, to check that your bot can see a set or to use the ids in your own code.

    BOT_TOKEN=<your bot token> python3 scripts/file-ids.py [set] [--json]

[set] is one of this repository's packs (speedy, bit, mochi), a Telegram set name or a
t.me/addstickers/ link; without it, Speedy.
  (default)  one line per sticker: tag, first emoji, file_id
  --json     {"done": "<file_id>", ...}

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


def set_name_for(arg: str) -> str:
    """A pack name becomes its recorded set name; anything else is taken as a set name or link."""
    name = arg.rstrip('/').split('/')[-1]
    if name in pack.all_packs():
        recorded = pack.load(name).get('telegram_set_name')
        if not recorded:
            raise SystemExit('The %s set has not been published yet.' % name)
        return recorded
    return name


def labels(stickers: list) -> list:
    """[(tag, first emoji, file_id)] in set order; the tag comes from the sticker's first emoji."""
    by_emoji = {pack.plain(emoji): tag for tag, emoji, _ in pack.TAGS}
    return [(by_emoji.get(pack.plain(st.get('emoji', '')), 'sticker%d' % (i + 1)),
             st.get('emoji', ''), st['file_id']) for i, st in enumerate(stickers)]


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    args = [a for a in argv[1:] if not a.startswith('--')]
    flags = {a for a in argv[1:] if a.startswith('--')}
    if '--help' in flags:
        print(__doc__.strip())
        return 0
    if flags - {'--json'} or len(args) > 1:
        print(__doc__.strip())
        return 2
    token = os.environ.get('BOT_TOKEN') or os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        print('Set BOT_TOKEN to your bot\'s token first (the one @BotFather gave you).')
        return 2
    name = set_name_for(args[0] if args else 'speedy')
    result = get_set(token, name)
    rows = labels(result['stickers'])
    if '--json' in flags:
        print(json.dumps({tag: fid for tag, _, fid in rows}, ensure_ascii=False, indent=2))
    else:
        print('# %s (%s), file_ids for this bot only' % (result.get('title', ''), result.get('name', name)))
        width = max(len(r[0]) for r in rows) if rows else 0
        for tag, emoji, fid in rows:
            print('%s  %s  %s' % (tag.ljust(width), emoji, fid))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
