"""The plugin on a fresh, real Hermes Agent, installed the way the README tells a stranger to.

All checks share ONE throwaway Hermes home (HERMES_HOME in a temp folder), so they never touch an
existing Hermes setup. One home, because recent Hermes versions prepare a separate runtime for
every new home, over a gigabyte each. Every check writes its own settings into that home first.
Telegram and the model are stand-ins on 127.0.0.1 (tests/mock_telegram.py, tests/mock_llm.py):
nothing reaches Telegram or a real model.

Runs only with a Python that can import Hermes (hermes_cli), for example the one in a pip
install of hermes-agent:

    /path/to/hermes-venv/bin/python -m unittest discover -s tests -v

Elsewhere these tests are skipped. Set HERMES_BIN to the `hermes` command you want to test if it
is not next to that Python. The install-from-git check needs git.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from mock_llm import MockLLM  # noqa: E402
from mock_telegram import MockTelegram  # noqa: E402

HERMES = (os.environ.get('HERMES_BIN')
          or (os.path.join(os.path.dirname(sys.executable), 'hermes')
              if os.path.exists(os.path.join(os.path.dirname(sys.executable), 'hermes')) else None)
          or shutil.which('hermes'))
HAVE_HERMES = bool(HERMES) and importlib.util.find_spec('hermes_cli') is not None

TOKEN = '111111:test-operator-token'
SET = 'speedy_by_OperatorTestBot'
OWNER = 424242
EMOJI = ['\U0001F3A7', '\U0001F4BB', '\U0001F4DD', '\U0001F4E1', '\U0001F527', '\U0001FAE1',
         '\U0001F634']
DONE = 5
PLUGIN = 'godspeed-stickers'
STRIP_ENV = ('HERMES_HOME', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_HOME_CHANNEL', 'TELEGRAM_ALLOWED_USERS',
             'GODSPEED_STICKER_SET', 'GODSPEED_STICKER_API_BASE', 'GODSPEED_STICKER_PLATFORMS',
             'GODSPEED_STICKER_TAGS', 'GODSPEED_STICKER_CHAT', 'OPENAI_API_KEY', 'OPENAI_BASE_URL',
             'OPENROUTER_API_KEY', 'ANTHROPIC_API_KEY')

# Runs inside the throwaway Hermes home: Hermes's own plugin loader, then the hook the agent
# calls on every finished reply, called the way the agent calls it.
LOADER_PROBE = textwrap.dedent('''
    import json, logging
    seen = []
    class Keep(logging.Handler):
        def emit(self, record):
            seen.append(record.getMessage())
    logging.getLogger().addHandler(Keep())
    logging.getLogger().setLevel(logging.INFO)
    from hermes_cli import plugins
    plugins.discover_plugins()
    loaded = plugins.get_plugin_manager()._plugins.get('godspeed-stickers')
    out = {'found': loaded is not None}
    if loaded is not None:
        out.update(enabled=loaded.enabled, error=loaded.error, hooks=loaded.hooks_registered)
    def reply(text):
        return plugins.invoke_hook('transform_llm_output', response_text=text, session_id='probe',
                                   model='mock-model', platform='telegram')
    out['done'] = reply('The report is in your inbox.\\n\\n[[sticker:done]]')
    out['unknown'] = reply('Here it is. [[sticker:party]]')
    out['plain'] = reply('Nothing to tag here.')
    out['log'] = [m for m in seen if 'godspeed-stickers' in m]
    print('PROBE ' + json.dumps(out))
''')


@unittest.skipUnless(HAVE_HERMES, 'needs a Python that can import Hermes (hermes_cli)')
class HermesInstallTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.tg = MockTelegram({TOKEN: 'OperatorTestBot'})
        cls.tg.add_set(SET, 'Speedy', EMOJI)
        cls.tg_base = cls.tg.start()
        cls.home = os.path.join(cls.tmp.name, 'hermes-home')
        os.makedirs(cls.home)
        cls.write_env(cls.sticker_env())
        cls.git_install = None
        if shutil.which('git'):
            # The README says `hermes plugins install MichaelZelbel/godspeed-stickers/hermes-plugin`.
            # Same installer and the same subfolder; only the address is a local git copy of this
            # repository, because the test must not depend on GitHub.
            src = os.path.join(cls.tmp.name, 'repo-for-git')
            shutil.copytree(ROOT, src, ignore=shutil.ignore_patterns('.git', '__pycache__'))
            git = ['git', '-c', 'user.name=test', '-c', 'user.email=test@example.invalid']
            for cmd in (['init', '-q', '-b', 'main'], ['add', '-A'], ['commit', '-qm', 'src']):
                subprocess.run(git + cmd, cwd=src, check=True, capture_output=True)
            cls.git_install = cls.hermes('plugins', 'install', 'file://%s#hermes-plugin' % src,
                                         '--enable', timeout=1200)
        else:
            shutil.copytree(os.path.join(ROOT, 'hermes-plugin'),
                            os.path.join(cls.home, 'plugins', PLUGIN))
            cls.hermes('plugins', 'enable', PLUGIN, timeout=1200)

    @classmethod
    def tearDownClass(cls):
        cls.tg.stop()
        cls.tmp.cleanup()

    def setUp(self):
        self.tg.calls.clear()
        self.tg.updates.clear()

    # -- helpers ---------------------------------------------------------------------------------
    @classmethod
    def env(cls):
        env = {k: v for k, v in os.environ.items() if k not in STRIP_ENV}
        env.update(HERMES_HOME=cls.home, PYTHONIOENCODING='utf-8', NO_COLOR='1', COLUMNS='200')
        return env

    @classmethod
    def hermes(cls, *args, timeout=600):
        return subprocess.run([HERMES, *args], cwd=cls.tmp.name, env=cls.env(),
                              capture_output=True, text=True, encoding='utf-8', timeout=timeout)

    @classmethod
    def write_env(cls, values):
        with open(os.path.join(cls.home, '.env'), 'w', encoding='utf-8') as fh:
            fh.write(''.join('%s=%s\n' % kv for kv in values.items()))

    @classmethod
    def sticker_env(cls):
        return {'TELEGRAM_BOT_TOKEN': TOKEN, 'TELEGRAM_HOME_CHANNEL': str(OWNER),
                'GODSPEED_STICKER_SET': SET, 'GODSPEED_STICKER_API_BASE': cls.tg_base}

    def probe(self):
        r = subprocess.run([sys.executable, '-c', LOADER_PROBE], cwd=self.tmp.name, env=self.env(),
                           capture_output=True, text=True, encoding='utf-8', timeout=600)
        line = next((l for l in r.stdout.splitlines() if l.startswith('PROBE ')), None)
        self.assertIsNotNone(line, r.stdout[-2000:] + r.stderr[-2000:])
        return json.loads(line[len('PROBE '):])

    def plugin_file(self, name):
        return os.path.join(self.home, 'plugins', PLUGIN, name)

    # -- the checks ------------------------------------------------------------------------------
    def test_1_install_from_git_as_the_readme_says(self):
        if self.git_install is None:
            self.skipTest('needs git')
        out = self.git_install.stdout + self.git_install.stderr
        self.assertEqual(self.git_install.returncode, 0, out)
        self.assertIn('godspeed-stickers is installed', out)  # after-install.md was shown
        self.assertIn('Plugin godspeed-stickers enabled', out)
        for name in ('__init__.py', 'sticker_sender.py', 'plugin.yaml'):
            self.assertTrue(os.path.isfile(self.plugin_file(name)), name)
        self.assertIn(PLUGIN, self.hermes('plugins', 'list').stdout)

        result = self.probe()
        self.assertTrue(result['found'] and result['enabled'], result)
        self.assertIsNone(result['error'])
        self.assertEqual(result['hooks'], ['transform_llm_output'])

    def test_2_install_by_hand_as_the_plugin_readme_says(self):
        self.hermes('plugins', 'disable', PLUGIN)
        shutil.rmtree(os.path.join(self.home, 'plugins', PLUGIN), ignore_errors=True)
        self.assertFalse(self.probe()['found'])

        shutil.copytree(os.path.join(ROOT, 'hermes-plugin'), os.path.join(self.home, 'plugins', PLUGIN))
        r = self.hermes('plugins', 'enable', PLUGIN)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        result = self.probe()
        self.assertTrue(result['found'] and result['enabled'], result)
        self.assertEqual(result['hooks'], ['transform_llm_output'])

    def test_3_hook_sends_one_sticker_and_strips_every_tag(self):
        self.write_env(self.sticker_env())
        result = self.probe()

        self.assertTrue(result['found'] and result['enabled'], result)
        self.assertEqual(result['done'], ['The report is in your inbox.'])
        self.assertEqual(result['unknown'], ['Here it is.'])
        self.assertEqual(result['plain'], [])
        sent = self.tg.calls_to('sendSticker')
        self.assertEqual(len(sent), 1, self.tg.calls)
        self.assertEqual(sent[0]['params']['sticker'], self.tg.file_id(TOKEN, SET, DONE))
        self.assertEqual(sent[0]['params']['chat_id'], str(OWNER))
        self.assertTrue(any('unknown tag [[sticker:party]]' in m for m in result['log']), result['log'])

    def test_4_missing_credentials_are_explained(self):
        self.write_env({'GODSPEED_STICKER_SET': SET, 'GODSPEED_STICKER_API_BASE': self.tg_base})
        result = self.probe()

        self.assertTrue(result['enabled'], result)
        self.assertEqual(result['done'], ['The report is in your inbox.'])
        self.assertEqual(self.tg.calls, [])
        log = '\n'.join(result['log'])
        self.assertIn('stickers will not send yet: no TELEGRAM_BOT_TOKEN', log)
        self.assertIn('no Telegram bot token, so no sticker was sent', log)

    def test_5_real_gateway_sends_the_sticker_and_hides_the_tag(self):
        llm = MockLLM('The report is in your inbox.\n\n[[sticker:done]]')
        llm_base = llm.start()
        gateway = None
        try:
            # Another allowed user comes first, so the sticker reaching OWNER proves it follows
            # the chat being answered rather than the first name on the list.
            self.write_env({'TELEGRAM_BOT_TOKEN': TOKEN, 'TELEGRAM_ALLOWED_USERS': '999001,%d' % OWNER,
                            'GODSPEED_STICKER_SET': SET, 'GODSPEED_STICKER_API_BASE': self.tg_base,
                            'OPENAI_API_KEY': 'mock-key'})
            self.configure_gateway(llm_base)

            log_path = os.path.join(self.tmp.name, 'gateway-test.log')
            with open(log_path, 'w', encoding='utf-8') as log:
                gateway = subprocess.Popen([HERMES, 'gateway', 'run', '-v'], cwd=self.tmp.name,
                                           env=self.env(), stdout=log, stderr=subprocess.STDOUT,
                                           start_new_session=True)
            self.wait_for(lambda: self.tg.calls_to('getUpdates'), 600, 'the gateway to poll Telegram',
                          gateway, log_path)
            self.tg.queue_message(OWNER, 'Please send me the report.')
            self.wait_for(lambda: self.final_texts(), 300, 'the reply to reach the chat', gateway, log_path)
            time.sleep(2)  # let any late edit of the message arrive too

            texts = self.final_texts()
            self.assertTrue(any('The report is in your inbox.' in t for t in texts), texts)
            for t in texts:
                self.assertNotIn('[[sticker', t)
            sent = self.tg.calls_to('sendSticker')
            self.assertEqual(len(sent), 1, [c['method'] for c in self.tg.calls])
            self.assertEqual(sent[0]['params']['sticker'], self.tg.file_id(TOKEN, SET, DONE))
            self.assertEqual(sent[0]['params']['chat_id'], str(OWNER))
            # Speedy first, then the words (Hermes may send its own notices before both).
            sticker_at = self.tg.calls.index(sent[0])
            reply_at = next(i for i, c in enumerate(self.tg.calls) if c['method'] == 'sendMessage'
                            and 'report is in your inbox' in c['params'].get('text', ''))
            self.assertLess(sticker_at, reply_at)
            self.assertTrue(llm.requests, 'the model stand-in was never asked')
            print('\n    gateway -> Telegram: %s' % ' '.join(
                c['method'] for c in self.tg.calls if c['method'] != 'getUpdates'), file=sys.stderr)
            print('    text the person sees: %r' % texts[-1], file=sys.stderr)
        finally:
            if gateway is not None:
                stop(gateway)
            llm.stop()

    # -- gateway helpers -------------------------------------------------------------------------
    def configure_gateway(self, llm_base):
        import yaml  # comes with hermes-agent
        path = os.path.join(self.home, 'config.yaml')
        cfg = {}
        if os.path.exists(path):
            with open(path, encoding='utf-8') as fh:
                cfg = yaml.safe_load(fh) or {}
        cfg['model'] = {'provider': 'custom', 'base_url': llm_base, 'default': 'mock-model',
                        'api_key': 'mock-key'}
        platforms = cfg.setdefault('platforms', {})
        platforms['telegram'] = {'enabled': True, 'extra': {
            'base_url': self.tg_base + '/bot', 'base_file_url': self.tg_base + '/file/bot'}}
        with open(path, 'w', encoding='utf-8') as fh:
            yaml.safe_dump(cfg, fh, sort_keys=False, allow_unicode=True)

    def final_texts(self):
        # Hermes sends Telegram MarkdownV2, which escapes punctuation (inbox\.); undo that.
        texts = [re.sub(r'\\(.)', r'\1', c['params'].get('text', '')) for c in self.tg.calls
                 if c['method'] in ('sendMessage', 'editMessageText')
                 and c['params'].get('chat_id') == str(OWNER)]
        return [t for t in texts if 'report' in t.lower()]

    def wait_for(self, condition, seconds, what, proc, log_path):
        deadline = time.time() + seconds
        while time.time() < deadline:
            if condition():
                return
            if proc.poll() is not None:
                break
            time.sleep(0.5)
        with open(log_path, encoding='utf-8', errors='replace') as fh:
            tail = fh.read()[-4000:]
        self.fail('waited for %s; calls so far: %s\n--- gateway log ---\n%s'
                  % (what, [c['method'] for c in self.tg.calls], tail))


def stop(proc):
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGINT)
        except (AttributeError, ProcessLookupError, PermissionError):
            proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (AttributeError, ProcessLookupError, PermissionError):
                proc.kill()
            proc.wait(timeout=10)


if __name__ == '__main__':
    unittest.main()
