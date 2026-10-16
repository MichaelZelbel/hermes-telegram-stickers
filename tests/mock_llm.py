"""A stand-in for an OpenAI-compatible model API that always gives the same answer.

The Hermes gateway test points a fresh Hermes at it, so the agent's "reply" is known in advance
(for example one that ends in [[sticker:done]]) and no real model or API key is needed. Answers
both plain and streamed chat completions, and lists one model.
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class MockLLM:
    def __init__(self, reply: str, model: str = 'mock-model'):
        self.reply = reply
        self.model = model
        self.requests: list[dict] = []
        self._server = None
        self.base_url = ''

    def start(self) -> str:
        mock = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path.rstrip('/').endswith('/models'):
                    return self._json({'object': 'list', 'data': [
                        {'id': mock.model, 'object': 'model', 'created': 0, 'owned_by': 'test',
                         'context_length': 128000}]})
                self._json({'error': {'message': 'not found'}}, 404)

            def do_POST(self):
                length = int(self.headers.get('Content-Length') or 0)
                body = json.loads(self.rfile.read(length) or b'{}')
                mock.requests.append({'path': self.path, 'body': body})
                if not self.path.rstrip('/').endswith('/chat/completions'):
                    return self._json({'error': {'message': 'not found'}}, 404)
                if body.get('stream'):
                    return self._stream()
                self._json({
                    'id': 'chatcmpl-mock', 'object': 'chat.completion', 'created': int(time.time()),
                    'model': mock.model,
                    'choices': [{'index': 0, 'finish_reason': 'stop',
                                 'message': {'role': 'assistant', 'content': mock.reply}}],
                    'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'total_tokens': 20},
                })

            def _json(self, payload, status=200):
                data = json.dumps(payload).encode('utf-8')
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _stream(self):
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Connection', 'close')
                self.end_headers()
                base = {'id': 'chatcmpl-mock', 'object': 'chat.completion.chunk',
                        'created': int(time.time()), 'model': mock.model}
                chunks = [{'role': 'assistant', 'content': ''}, {'content': mock.reply}]
                for delta in chunks:
                    event = dict(base, choices=[{'index': 0, 'delta': delta, 'finish_reason': None}])
                    self.wfile.write(b'data: ' + json.dumps(event).encode('utf-8') + b'\n\n')
                end = dict(base, choices=[{'index': 0, 'delta': {}, 'finish_reason': 'stop'}],
                           usage={'prompt_tokens': 10, 'completion_tokens': 10, 'total_tokens': 20})
                self.wfile.write(b'data: ' + json.dumps(end).encode('utf-8') + b'\n\n')
                self.wfile.write(b'data: [DONE]\n\n')
                self.wfile.flush()
                self.close_connection = True

        self._server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self._server.daemon_threads = True
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        self.base_url = 'http://127.0.0.1:%d/v1' % self._server.server_address[1]
        return self.base_url

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
