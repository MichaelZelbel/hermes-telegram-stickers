"""Telegram side of the godspeed-stickers Hermes plugin.

Finds a sticker in a Telegram sticker set by its emoji and sends it through YOUR bot.

Why it looks the sticker up instead of shipping a fixed id: Telegram gives every bot its own
file_id for the same sticker, and a file_id from one bot does not work for another. So the plugin
asks Telegram (getStickerSet, with your bot's own token) for the set once, keeps the ids it gets
back in memory, and sends with those.

Standard library only, so dropping the folder into ~/.hermes/plugins/ is the whole install.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_API = 'https://api.telegram.org'
TIMEOUT = 5  # seconds per Telegram call; a sticker must never hold up a reply for long

_sets: dict[tuple[str, str], dict[str, str]] = {}  # (bot token tail, set name) -> {emoji: file_id}


def _plain(emoji: str) -> str:
    """Compare emoji without the invisible variation selector some clients add."""
    return (emoji or '').replace('️', '').strip()


def hermes_home() -> str:
    home = os.environ.get('HERMES_HOME', '').strip()
    if home:
        return home
    # <HERMES_HOME>/plugins/<this plugin>/sticker_sender.py
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _from_dotenv(names):
    """Values from <HERMES_HOME>/.env, for the rare host that did not load it into the env."""
    found = {}
    try:
        with open(os.path.join(hermes_home(), '.env'), encoding='utf-8') as fh:
            for line in fh:
                key, sep, value = line.strip().partition('=')
                key = key.strip()
                if key.startswith('export '):
                    key = key[len('export '):].strip()
                if sep and key in names and key not in found:
                    found[key] = value.strip().strip('"\'')
    except OSError:
        pass
    return found


def setting(name: str, default: str = '') -> str:
    value = os.environ.get(name, '').strip()
    if value:
        return value
    return _from_dotenv({name}).get(name, default) or default


def _session_chat():
    """The Telegram chat this reply is going to, when the Hermes gateway says so."""
    try:
        from gateway.session_context import get_session_env  # part of hermes-agent
    except Exception:  # noqa: BLE001 - running outside the gateway
        return '', ''
    try:
        if get_session_env('HERMES_SESSION_PLATFORM', '').lower() != 'telegram':
            return '', ''
        return (get_session_env('HERMES_SESSION_CHAT_ID', '').strip(),
                get_session_env('HERMES_SESSION_THREAD_ID', '').strip())
    except Exception:  # noqa: BLE001
        return '', ''


def target_chat():
    """Where the sticker goes: GODSPEED_STICKER_CHAT if set, else the chat being answered,
    else the gateway's home channel, else the first allowed user. Returns (chat_id, thread_id)."""
    fixed = setting('GODSPEED_STICKER_CHAT')
    if fixed:
        return fixed, ''
    chat, thread = _session_chat()
    if chat:
        return chat, thread
    home = setting('TELEGRAM_HOME_CHANNEL')
    if home:
        return home, setting('TELEGRAM_HOME_CHANNEL_THREAD_ID')
    # The first entry that is a chat id (the list may also hold "*" or usernames).
    allowed = [a.strip() for a in setting('TELEGRAM_ALLOWED_USERS').split(',')]
    first = next((a for a in allowed if a.lstrip('-').isdigit()), '')
    return first, ''


def _scrub(text, token):
    text = str(text)
    return text.replace(token, '<token>') if token else text


def _call(token: str, method: str, payload: dict) -> dict:
    api = setting('GODSPEED_STICKER_API_BASE', DEFAULT_API).rstrip('/')
    req = urllib.request.Request('%s/bot%s/%s' % (api, token, method),
                                 data=json.dumps(payload).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as err:  # Telegram answers 400/401/404 with a JSON body
        try:
            return json.loads(err.read().decode('utf-8'))
        except Exception:  # noqa: BLE001
            return {'ok': False, 'description': 'HTTP %s' % err.code}


def _set_ids(token: str, set_name: str, refresh: bool = False) -> dict:
    key = (token[-12:], set_name)
    if refresh or key not in _sets:
        got = _call(token, 'getStickerSet', {'name': set_name})
        if not got.get('ok'):
            raise LookupError('Telegram has no sticker set %r for this bot (%s)'
                              % (set_name, got.get('description', 'no reason given')))
        ids = {}
        for sticker in got.get('result', {}).get('stickers', []):
            ids.setdefault(_plain(sticker.get('emoji', '')), sticker['file_id'])
        _sets[key] = ids
    return _sets[key]


def send(set_name: str, emoji: str) -> str:
    """Send the sticker carrying `emoji` from `set_name`, silently. Returns a short outcome
    ('sent', 'no-token', 'no-chat', 'no-such-set: ...', 'no-such-sticker', 'refused: ...',
    'failed: ...'); never raises and never includes the bot token."""
    token = setting('TELEGRAM_BOT_TOKEN')
    if not token:
        return 'no-token'
    chat, thread = target_chat()
    if not chat:
        return 'no-chat'
    try:
        try:
            ids = _set_ids(token, set_name)
        except LookupError as exc:
            return 'no-such-set: %s' % _scrub(exc, token)
        file_id = ids.get(_plain(emoji))
        if file_id is None:
            return 'no-such-sticker'
        payload = {'chat_id': chat, 'sticker': file_id, 'disable_notification': True}
        if thread:
            payload['message_thread_id'] = int(thread) if thread.isdigit() else thread
        sent = _call(token, 'sendSticker', payload)
        if sent.get('ok'):
            return 'sent'
        _sets.pop((token[-12:], set_name), None)  # a stale id: look the set up again next time
        return 'refused: %s' % _scrub(sent.get('description', sent), token)[:160]
    except Exception as exc:  # noqa: BLE001 - a sticker must never break the agent's reply
        return 'failed: %s' % _scrub(exc, token)[:160]


def reset_cache() -> None:
    _sets.clear()
