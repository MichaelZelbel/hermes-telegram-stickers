"""godspeed-stickers: lets a Hermes Agent bot send a sticker to the person it is talking to.

The agent ends a reply with a tag such as [[sticker:done]]. Just before the reply goes out, this
plugin sends the matching sticker through your Telegram bot and removes the tag, so the person
sees the sticker and the words, never the tag.

Install and setup: README.md next to this file. Settings, all optional, read from the
environment or from ~/.hermes/.env:

  GODSPEED_STICKER_SET        Telegram sticker set name (the part after t.me/addstickers/).
                              Default: the free Speedy set.
  GODSPEED_STICKER_TAGS       Your own tags for your own set: "done=✅,ask=❓". Replaces the
                              Speedy tags below.
  GODSPEED_STICKER_PLATFORMS  Where a tag sends a sticker. Default "telegram". On every other
                              platform the tag is only removed.
  GODSPEED_STICKER_CHAT       Always send to this chat id instead of the chat being answered.
  GODSPEED_STICKER_API_BASE   Bot API address. Default https://api.telegram.org (change it for a
                              self-hosted Bot API server, or for testing).
"""
from __future__ import annotations

import importlib.util
import logging
import os
import re

logger = logging.getLogger(__name__)

HERE = os.path.dirname(os.path.abspath(__file__))

# Filled in by scripts/publish-set.sh when the Speedy set is published.
DEFAULT_SET = 'speedy_by_<BOT>'

# Speedy's seven poses: tag -> the emoji Telegram lists for that sticker in the set.
SPEEDY_TAGS = {
    'today': '\U0001F3A7',  # headphones: listening, here for the day
    'onit': '\U0001F4BB',   # laptop: on it
    'note': '\U0001F4DD',   # memo: a note for you
    'copy': '\U0001F4E1',   # satellite antenna: do you copy? (needs your yes)
    'fix': '\U0001F527',    # wrench: fixing it
    'done': '\U0001FAE1',   # saluting face: done
    'quiet': '\U0001F634',  # sleeping face: quiet watch
}

TAG_RE = re.compile(r'[ \t]*`?\[\[\s*sticker\s*:\s*([A-Za-z0-9_-]+)\s*\]\]`?', re.IGNORECASE)

_spec = importlib.util.spec_from_file_location('godspeed_stickers_sender',
                                               os.path.join(HERE, 'sticker_sender.py'))
sender = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sender)

_warned: set[str] = set()


def _warn_once(key: str, message: str, *args) -> None:
    if key not in _warned:
        _warned.add(key)
        logger.warning(message, *args)


def sticker_set() -> str:
    return sender.setting('GODSPEED_STICKER_SET', DEFAULT_SET)


def tags() -> dict:
    custom = sender.setting('GODSPEED_STICKER_TAGS')
    if not custom:
        return dict(SPEEDY_TAGS)
    out = {}
    for pair in custom.split(','):
        name, sep, emoji = pair.partition('=')
        if sep and name.strip() and emoji.strip():
            out[name.strip().lower()] = emoji.strip()
    return out


def send_platforms() -> set:
    raw = sender.setting('GODSPEED_STICKER_PLATFORMS', 'telegram')
    return {p.strip().lower() for p in raw.split(',') if p.strip()}


def strip_tags(text: str) -> str:
    cleaned = TAG_RE.sub('', text)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def explain(outcome: str, name: str) -> str | None:
    """A plain sentence for every outcome that needs the operator's attention."""
    if outcome == 'no-token':
        return ('godspeed-stickers: no Telegram bot token, so no sticker was sent. Put '
                'TELEGRAM_BOT_TOKEN (the token your Hermes Telegram gateway already uses) in '
                '~/.hermes/.env.')
    if outcome == 'no-chat':
        return ('godspeed-stickers: no chat to send the sticker to. Set TELEGRAM_HOME_CHANNEL or '
                'TELEGRAM_ALLOWED_USERS in ~/.hermes/.env (or GODSPEED_STICKER_CHAT).')
    if outcome.startswith('no-such-set'):
        return ('godspeed-stickers: %s. Check GODSPEED_STICKER_SET (the part after '
                't.me/addstickers/).' % outcome.partition(': ')[2])
    if outcome == 'no-such-sticker':
        return ('godspeed-stickers: set %r has no sticker with the emoji for tag %r. Check '
                'GODSPEED_STICKER_TAGS.' % (sticker_set(), name))
    if outcome.startswith(('refused', 'failed')):
        return 'godspeed-stickers: sticker %r not sent (%s).' % (name, outcome)
    return None


def register(ctx):
    ctx.register_hook('transform_llm_output', on_transform_llm_output)
    problems = []
    if not sender.setting('TELEGRAM_BOT_TOKEN'):
        problems.append('no TELEGRAM_BOT_TOKEN')
    if '<' in sticker_set():
        problems.append('no sticker set configured (set GODSPEED_STICKER_SET)')
    if problems:
        logger.warning('godspeed-stickers: loaded, but stickers will not send yet: %s.',
                       '; '.join(problems))
    else:
        logger.info('godspeed-stickers: ready (set %s, tags %s)', sticker_set(),
                    ', '.join(sorted(tags())))


def on_transform_llm_output(response_text: str = '', platform: str = '', **_):
    """Send the first known sticker tag's sticker, and return the reply with every tag removed."""
    text = response_text or ''
    found = [m.lower() for m in TAG_RE.findall(text)]
    if not found:
        return None
    try:
        known = tags()
        for name in found:
            if name not in known:
                logger.warning('godspeed-stickers: unknown tag [[sticker:%s]] removed (known: %s)',
                               name, ', '.join(sorted(known)))
        wanted = next((n for n in found if n in known), None)
        if wanted:
            platforms = send_platforms()
            if '*' in platforms or (platform or '').lower() in platforms:
                if '<' in sticker_set():
                    _warn_once('no-set', 'godspeed-stickers: no sticker set configured, so no '
                               'sticker was sent. Set GODSPEED_STICKER_SET in ~/.hermes/.env.')
                else:
                    outcome = sender.send(sticker_set(), known[wanted])
                    message = explain(outcome, wanted)
                    if message:
                        logger.warning(message)
                    else:
                        logger.info('godspeed-stickers: %s -> %s', wanted, outcome)
        cleaned = strip_tags(text)
        # A reply that was nothing but a tag must not come back empty (Hermes would then show
        # the original text, tag included), so it becomes the sticker's emoji.
        return cleaned or (known.get(wanted) if wanted else '') or '✅'
    except Exception as exc:  # noqa: BLE001 - never break the chat over a sticker
        logger.warning('godspeed-stickers: %s', exc)
        return strip_tags(text) or None
