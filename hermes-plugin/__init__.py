"""hermes-telegram-stickers: lets a Hermes Agent bot send a Telegram sticker to the person it is
talking to.

The agent ends a reply with a tag such as [[sticker:done]]. Just before the reply goes out, this
plugin sends the matching sticker through your Telegram bot and removes the tag, so the person
sees the sticker and the words, never the tag.

Install and setup: README.md next to this file. Settings, all optional, read from the
environment or from ~/.hermes/.env:

  STICKERS_SET        Which stickers: speedy (the default), bit, mochi, or the name of any
                      Telegram sticker set (the part after t.me/addstickers/).
  STICKERS_TAGS       Your own tags for your own set: "yay=🎉,hmm=🤔". Replaces the built-in
                      tags below.
  STICKERS_PLATFORMS  Where a tag sends a sticker. Default "telegram". On every other platform
                      the tag is only removed.
  STICKERS_CHAT       Always send to this chat id instead of the chat being answered.
  STICKERS_API_BASE   Bot API address. Default https://api.telegram.org (change it for a
                      self-hosted Bot API server, or for testing).
"""
from __future__ import annotations

import importlib.util
import logging
import os
import re

logger = logging.getLogger(__name__)

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = 'hermes-telegram-stickers'

# The sets this repository publishes. scripts/publish-set.sh fills in each set's Telegram name.
SETS = {
    'speedy': 'speedy_by_GodspeedStickersBot',
    'bit': 'bit_by_<BOT>',
    'mochi': 'mochi_by_<BOT>',
}
DEFAULT = 'speedy'

# The moments every set has: tag -> the PRIMARY emoji of that tag's sticker in each set.
# A set may carry more emoji per sticker; only the primary one is used to find it.
TAGS = {
    'today': '\U0001F3A7',    # headphones: here and listening
    'onit': '\U0001F4BB',     # laptop: on it
    'note': '\U0001F4DD',     # memo: a note for you
    'copy': '\U0001F4E1',     # satellite antenna: do you copy? I need your yes
    'fix': '\U0001F527',      # wrench: fixing it
    'done': '\U0001FAE1',     # saluting face: done
    'quiet': '\U0001F634',    # sleeping face: keeping quiet watch
    'ok': '\U0001F44D',       # thumbs up: got it
    'think': '\U0001F914',    # thinking face: thinking it over
    'found': '\U0001F50D',    # magnifying glass: found it
    'oops': '\U0001F605',     # sweat smile: my mistake
    'party': '\U0001F389',    # party popper: good news
    'thanks': '\U0001F64F',   # folded hands: thank you
    'morning': '☕',      # hot beverage: good morning
    'night': '\U0001F319',    # crescent moon: good night
}

TAG_RE = re.compile(r'[ \t]*`?\[\[\s*sticker\s*:\s*([A-Za-z0-9_-]+)\s*\]\]`?', re.IGNORECASE)

_spec = importlib.util.spec_from_file_location('hermes_telegram_stickers_sender',
                                               os.path.join(HERE, 'sticker_sender.py'))
sender = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sender)

_warned: set[str] = set()
# session id -> the Telegram user that session is answering, from pre_llm_call. Used when the
# gateway's own record of the chat is out of reach (Hermes's plugins.isolation: host).
_people: dict[str, str] = {}


def _warn_once(key: str, message: str, *args) -> None:
    if key not in _warned:
        _warned.add(key)
        logger.warning(message, *args)


def chosen() -> str:
    return sender.setting('STICKERS_SET', DEFAULT).strip()


def sticker_set() -> str:
    """The Telegram set name: one of ours by its short name, or any set name as given."""
    return SETS.get(chosen().lower(), chosen())


def unpublished() -> bool:
    return '<' in sticker_set()


def tags() -> dict:
    custom = sender.setting('STICKERS_TAGS')
    if not custom:
        return dict(TAGS)
    out = {}
    for pair in custom.split(','):
        name, sep, emoji = pair.partition('=')
        if sep and name.strip() and emoji.strip():
            out[name.strip().lower()] = emoji.strip()
    return out


def send_platforms() -> set:
    raw = sender.setting('STICKERS_PLATFORMS', 'telegram')
    return {p.strip().lower() for p in raw.split(',') if p.strip()}


def strip_tags(text: str) -> str:
    cleaned = TAG_RE.sub('', text)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def explain(outcome: str, tag: str) -> str | None:
    """A plain sentence for every outcome that needs the operator's attention."""
    if outcome == 'no-token':
        return ('%s: no Telegram bot token, so no sticker was sent. Put TELEGRAM_BOT_TOKEN (the '
                'token your Hermes Telegram gateway already uses) in ~/.hermes/.env.' % NAME)
    if outcome == 'no-chat':
        return ('%s: no chat to send the sticker to. Set TELEGRAM_HOME_CHANNEL or '
                'TELEGRAM_ALLOWED_USERS in ~/.hermes/.env (or STICKERS_CHAT).' % NAME)
    if outcome.startswith('no-such-set'):
        return ('%s: %s. Check STICKERS_SET (speedy, bit, mochi, or the part after '
                't.me/addstickers/).' % (NAME, outcome.partition(': ')[2]))
    if outcome == 'no-such-sticker':
        return ('%s: set %r has no sticker whose first emoji is the one for tag %r, so none was '
                'sent.' % (NAME, sticker_set(), tag))
    if outcome == 'ambiguous':
        return ('%s: in set %r two stickers have the first emoji of tag %r, so none was sent.'
                % (NAME, sticker_set(), tag))
    if outcome.startswith(('refused', 'failed')):
        return '%s: sticker %r not sent (%s).' % (NAME, tag, outcome)
    return None


def register(ctx):
    ctx.register_hook('pre_llm_call', on_pre_llm_call)
    ctx.register_hook('transform_llm_output', on_transform_llm_output)
    problems = []
    if not sender.setting('TELEGRAM_BOT_TOKEN'):
        problems.append('no TELEGRAM_BOT_TOKEN')
    if unpublished():
        problems.append('the %s set is not published yet (pick another with STICKERS_SET)' % chosen())
    if problems:
        logger.warning('%s: loaded, but stickers will not send yet: %s.', NAME, '; '.join(problems))
    else:
        logger.info('%s: ready (set %s, tags %s)', NAME, sticker_set(), ', '.join(tags()))


def on_pre_llm_call(session_id: str = '', platform: str = '', sender_id: str = '', **_):
    """Remember who this session is answering. Returns None: nothing is added to the prompt."""
    try:
        if session_id and sender_id and (platform or '').lower() == 'telegram':
            _people[str(session_id)] = str(sender_id)
            while len(_people) > 500:
                _people.pop(next(iter(_people)))
    except Exception:  # noqa: BLE001
        pass
    return None


def on_transform_llm_output(response_text: str = '', platform: str = '', session_id: str = '',
                            **_):
    """Send the first known sticker tag's sticker, and return the reply with every tag removed."""
    text = response_text or ''
    found = [m.lower() for m in TAG_RE.findall(text)]
    if not found:
        return None
    try:
        known = tags()
        for tag in found:
            if tag not in known:
                logger.warning('%s: unknown tag [[sticker:%s]] removed (known: %s)',
                               NAME, tag, ', '.join(known))
        wanted = next((t for t in found if t in known), None)
        if wanted:
            platforms = send_platforms()
            if '*' in platforms or (platform or '').lower() in platforms:
                if unpublished():
                    _warn_once('unpublished', '%s: the %s set is not published yet, so no sticker '
                               'was sent. Pick another with STICKERS_SET in ~/.hermes/.env.',
                               NAME, chosen())
                else:
                    outcome = sender.send(sticker_set(), known[wanted],
                                          person=_people.get(str(session_id), ''))
                    message = explain(outcome, wanted)
                    if message:
                        logger.warning(message)
                    else:
                        logger.info('%s: %s -> %s', NAME, wanted, outcome)
        cleaned = strip_tags(text)
        # A reply that was nothing but a tag must not come back empty (Hermes would then show
        # the original text, tag included), so it becomes the sticker's emoji.
        return cleaned or (known.get(wanted) if wanted else '') or '✅'
    except Exception as exc:  # noqa: BLE001 - never break the chat over a sticker
        logger.warning('%s: %s', NAME, exc)
        return strip_tags(text) or None
