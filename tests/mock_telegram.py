"""A small stand-in for the Telegram Bot API, so tests never reach Telegram or a real person.

It knows several bots (by token) and keeps sticker sets in memory. Like the real API, every bot
gets its OWN file_id for the same sticker, and sendSticker refuses a file_id that belongs to a
different bot. That is the rule this repository is built around, so the tests check it.

Besides the sticker methods it answers just enough of the rest (getUpdates, sendMessage, ...) for
a real Hermes gateway to run against it. Every call is recorded in `calls`.

Run it on its own to poke at it by hand:  python tests/mock_telegram.py
"""
from __future__ import annotations

import email.parser
import email.policy
import json
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _bot_id(token: str) -> str:
    return token.split(':', 1)[0]


class MockTelegram:
    def __init__(self, bots: dict[str, str] | None = None):
        # token -> bot username
        self.bots = dict(bots or {'111111:test-operator-token': 'OperatorTestBot'})
        self.sets: dict[str, dict] = {}
        self.calls: list[dict] = []
        self.errors: list[str] = []
        self.updates: list[dict] = []
        self._update_id = 1000
        self._message_id = 1
        self._lock = threading.Lock()
        self._server = None
        self._thread = None
        self.base_url = ''

    # -- set-up helpers -------------------------------------------------------------------------
    def add_set(self, name: str, title: str, emojis: list, creator: str | None = None) -> None:
        """`emojis`: one entry per sticker, a primary emoji or a full emoji list. `creator`: the bot
        token that made the set (only that bot may change it); None lets any bot change it."""
        lists = [list(e) if isinstance(e, (list, tuple)) else [e] for e in emojis]
        self.sets[name] = {'title': title, 'creator': _bot_id(creator) if creator else None,
                           'stickers': [{'emoji_list': l, 'index': i} for i, l in enumerate(lists)]}

    def file_id(self, token: str, set_name: str, index: int) -> str:
        """The file_id this bot sees for sticker `index` of `set_name`."""
        return 'FILE-%s-%s-%d' % (_bot_id(token), set_name, index)

    def queue_message(self, chat_id: int, text: str, first_name: str = 'Tester') -> None:
        with self._lock:
            self._update_id += 1
            self._message_id += 1
            self.updates.append({
                'update_id': self._update_id,
                'message': {
                    'message_id': self._message_id, 'date': int(time.time()), 'text': text,
                    'chat': {'id': chat_id, 'type': 'private', 'first_name': first_name},
                    'from': {'id': chat_id, 'is_bot': False, 'first_name': first_name},
                },
            })

    def calls_to(self, method: str) -> list[dict]:
        return [c for c in self.calls if c['method'] == method]

    # -- server ---------------------------------------------------------------------------------
    def start(self) -> str:
        mock = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # keep test output clean
                pass

            def do_GET(self):
                self._handle(b'')

            def do_POST(self):
                length = int(self.headers.get('Content-Length') or 0)
                self._handle(self.rfile.read(length) if length else b'')

            def _handle(self, body: bytes):
                parsed = urllib.parse.urlsplit(self.path)
                parts = parsed.path.strip('/').split('/')
                if len(parts) < 2 or not parts[0].startswith('bot'):
                    return self._send(404, {'ok': False, 'error_code': 404, 'description': 'Not Found'})
                token, method = parts[0][3:], parts[1]
                try:
                    params, files = _parse(self.headers.get('Content-Type', ''), body, parsed.query)
                    status, payload = mock._dispatch(token, method, params, files)
                except Exception as exc:  # report a mock bug as an answer, not a dropped line
                    import traceback
                    mock.errors.append(traceback.format_exc())
                    status, payload = 500, {'ok': False, 'error_code': 500,
                                            'description': 'mock error: %r' % exc}
                self._send(status, payload)

            def _send(self, status, payload):
                data = json.dumps(payload).encode('utf-8')
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # the client hung up (a gateway stopping mid long-poll)

        self._server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self.base_url = 'http://127.0.0.1:%d' % self._server.server_address[1]
        return self.base_url

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    # -- the API --------------------------------------------------------------------------------
    def _dispatch(self, token, method, params, files):
        with self._lock:
            self.calls.append({'method': method, 'bot': _bot_id(token), 'params': params,
                               'files': sorted(files)})
        if token not in self.bots:
            return 401, {'ok': False, 'error_code': 401, 'description': 'Unauthorized'}
        handler = getattr(self, '_m_' + method, None)
        if handler is None:
            return 200, {'ok': True, 'result': True}
        try:
            return handler(token, params, files)
        except _BadRequest as exc:
            return 400, {'ok': False, 'error_code': 400, 'description': 'Bad Request: %s' % exc}

    def _me(self, token):
        return {'id': int(_bot_id(token)), 'is_bot': True, 'first_name': self.bots[token],
                'username': self.bots[token], 'can_join_groups': True,
                'can_read_all_group_messages': False, 'supports_inline_queries': False}

    def _m_getMe(self, token, params, files):
        return 200, {'ok': True, 'result': self._me(token)}

    def _m_getStickerSet(self, token, params, files):
        name = params.get('name', '')
        if name not in self.sets:
            raise _BadRequest('STICKERSET_INVALID')
        s = self.sets[name]
        stickers = [{'file_id': self.file_id(token, name, st['index']),
                     'file_unique_id': 'U-%s-%d' % (name, st['index']), 'type': 'regular',
                     'width': 512, 'height': 512, 'is_animated': False, 'is_video': False,
                     'emoji': st['emoji_list'][0], 'set_name': name} for st in s['stickers']]
        return 200, {'ok': True, 'result': {'name': name, 'title': s['title'],
                                            'sticker_type': 'regular', 'stickers': stickers}}

    def _check_new_name(self, token, name):
        suffix = '_by_' + self.bots[token].lower()
        if not name.lower().endswith(suffix) or '__' in name or not name[:1].isalpha():
            raise _BadRequest('invalid sticker set name is specified')

    def _input_stickers(self, raw, files):
        stickers = json.loads(raw) if isinstance(raw, str) else raw
        for st in stickers:
            ref = st['sticker']
            if ref.startswith('attach://') and ref[len('attach://'):] not in files:
                raise _BadRequest('file %s not attached' % ref)
            if not st.get('emoji_list'):
                raise _BadRequest('emoji_list is empty')
        return stickers

    def _m_createNewStickerSet(self, token, params, files):
        name = params.get('name', '')
        self._check_new_name(token, name)
        if name in self.sets:
            raise _BadRequest('sticker set name is already occupied')
        if not params.get('user_id'):
            raise _BadRequest('user_id is empty')
        stickers = self._input_stickers(params.get('stickers', '[]'), files)
        if not 1 <= len(stickers) <= 50:
            raise _BadRequest('wrong number of stickers')
        self.add_set(name, params.get('title', ''), [st['emoji_list'] for st in stickers], creator=token)
        return 200, {'ok': True, 'result': True}

    def _own_set(self, token, name):
        if name not in self.sets:
            raise _BadRequest('STICKERSET_INVALID')
        creator = self.sets[name]['creator']
        if creator and creator != _bot_id(token):
            raise _BadRequest('STICKERSET_NOT_MODIFIED')  # only the bot that made a set may change it
        return self.sets[name]

    def _m_addStickerToSet(self, token, params, files):
        stickers = self._own_set(token, params.get('name', ''))['stickers']
        st = self._input_stickers('[%s]' % params.get('sticker', '{}'), files)[0]
        stickers.append({'emoji_list': st['emoji_list'], 'index': len(stickers)})
        return 200, {'ok': True, 'result': True}

    def _m_setStickerEmojiList(self, token, params, files):
        file_id = params.get('sticker', '')
        prefix = 'FILE-%s-' % _bot_id(token)
        if not file_id.startswith(prefix):
            raise _BadRequest('wrong file identifier/HTTP URL specified')
        set_name, _, index = file_id[len(prefix):].rpartition('-')
        stickers = self._own_set(token, set_name)['stickers']
        emoji_list = json.loads(params.get('emoji_list', '[]'))
        if not 1 <= len(emoji_list) <= 20:
            raise _BadRequest('emoji_list must have 1 to 20 emoji')
        stickers[int(index)]['emoji_list'] = emoji_list
        return 200, {'ok': True, 'result': True}

    def _m_setStickerSetTitle(self, token, params, files):
        self._own_set(token, params.get('name', ''))['title'] = params.get('title', '')
        return 200, {'ok': True, 'result': True}

    def emoji_lists(self, name: str) -> list:
        """The full emoji list of every sticker in a set, in order (what Telegram keeps)."""
        return [st['emoji_list'] for st in self.sets[name]['stickers']]

    def _message(self, chat_id, extra):
        with self._lock:
            self._message_id += 1
            mid = self._message_id
        msg = {'message_id': mid, 'date': int(time.time()),
               'chat': {'id': int(chat_id) if str(chat_id).lstrip('-').isdigit() else chat_id,
                        'type': 'private'}}
        msg.update(extra)
        return 200, {'ok': True, 'result': msg}

    def _m_sendSticker(self, token, params, files):
        file_id = params.get('sticker', '')
        if not file_id.startswith('FILE-%s-' % _bot_id(token)):
            raise _BadRequest('wrong file identifier/HTTP URL specified')
        if not params.get('chat_id'):
            raise _BadRequest('chat_id is empty')
        return self._message(params['chat_id'], {'sticker': {'file_id': file_id}})

    def _m_sendMessage(self, token, params, files):
        return self._message(params.get('chat_id'), {'text': params.get('text', '')})

    def _m_editMessageText(self, token, params, files):
        return self._message(params.get('chat_id'), {'text': params.get('text', '')})

    def _m_getUpdates(self, token, params, files):
        offset = int(params.get('offset') or 0)
        deadline = time.time() + min(float(params.get('timeout') or 0), 1.0)
        while True:
            with self._lock:
                ready = [u for u in self.updates if u['update_id'] >= offset]
            if ready or time.time() >= deadline:
                return 200, {'ok': True, 'result': ready}
            time.sleep(0.05)

    def _m_getMyCommands(self, token, params, files):
        return 200, {'ok': True, 'result': []}

    def _m_getChat(self, token, params, files):
        return 200, {'ok': True, 'result': {'id': int(params.get('chat_id') or 0), 'type': 'private'}}

    def _m_getWebhookInfo(self, token, params, files):
        return 200, {'ok': True, 'result': {'url': '', 'has_custom_certificate': False,
                                            'pending_update_count': 0}}


class _BadRequest(Exception):
    pass


def _parse(content_type: str, body: bytes, query: str):
    params = {k: v[-1] for k, v in urllib.parse.parse_qs(query).items()}
    files = {}
    ctype = content_type.split(';')[0].strip().lower()
    if ctype == 'application/json' and body:
        for k, v in json.loads(body.decode('utf-8')).items():
            params[k] = v if isinstance(v, (str, int, float, bool)) or v is None else json.dumps(v)
    elif ctype == 'application/x-www-form-urlencoded' and body:
        params.update({k: v[-1] for k, v in urllib.parse.parse_qs(body.decode('utf-8')).items()})
    elif ctype == 'multipart/form-data' and body:
        msg = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
            b'Content-Type: ' + content_type.encode('latin-1') + b'\r\n\r\n' + body)
        for part in msg.iter_parts():
            name = part.get_param('name', header='content-disposition')
            if part.get_filename():
                files[name] = part.get_content()
            else:
                payload = part.get_payload(decode=True) or b''
                params[name] = payload.decode('utf-8')
    for k, v in list(params.items()):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            params[k] = str(v)
    return params, files


if __name__ == '__main__':
    m = MockTelegram()
    m.add_set('speedy_by_OperatorTestBot', 'Speedy', ['\U0001F3A7', '\U0001FAE1'])
    print('mock Telegram Bot API at', m.start(), '(token 111111:test-operator-token)')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        m.stop()
