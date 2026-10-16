"""Tests for the Hermes plugin in hermes-plugin/.

Run from the repository root:

    python -m unittest discover -s tests -v

Nothing here talks to Telegram: every call goes to tests/mock_telegram.py on 127.0.0.1.

The first group loads the plugin the way Hermes does (import the folder, call register(ctx))
with a stand-in for Hermes, so it runs anywhere. The second group (test_hermes_install.py) runs
only where the `hermes` command is installed and uses the real Hermes.
"""
from __future__ import annotations

import importlib.util
import logging
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PLUGIN_DIR = os.path.join(ROOT, 'hermes-plugin')
sys.path.insert(0, HERE)

from mock_telegram import MockTelegram  # noqa: E402

# The plugin's warnings are checked with assertLogs; keep them out of the test output otherwise.
logging.getLogger().addHandler(logging.NullHandler())

TOKEN = '111111:test-operator-token'
OTHER_TOKEN = '222222:someone-elses-token'
SET = 'speedy_by_OperatorTestBot'
SPEEDY_EMOJI = ['\U0001F3A7', '\U0001F4BB', '\U0001F4DD', '\U0001F4E1', '\U0001F527',
                '\U0001FAE1', '\U0001F634']
POSES = ['today', 'onit', 'note', 'copy', 'fix', 'done', 'quiet']
ENV_KEYS = ('TELEGRAM_BOT_TOKEN', 'TELEGRAM_HOME_CHANNEL', 'TELEGRAM_HOME_CHANNEL_THREAD_ID',
            'TELEGRAM_ALLOWED_USERS', 'GODSPEED_STICKER_SET', 'GODSPEED_STICKER_TAGS',
            'GODSPEED_STICKER_PLATFORMS', 'GODSPEED_STICKER_CHAT', 'GODSPEED_STICKER_API_BASE',
            'HERMES_HOME', 'HERMES_SESSION_PLATFORM', 'HERMES_SESSION_CHAT_ID',
            'HERMES_SESSION_THREAD_ID')

_loaded = 0


def load_plugin():
    """Import hermes-plugin/ as a package, the way Hermes's plugin loader does."""
    global _loaded
    _loaded += 1
    name = 'hermes_plugins_test_%d.godspeed_stickers' % _loaded
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(PLUGIN_DIR, '__init__.py'), submodule_search_locations=[PLUGIN_DIR])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class FakeContext:
    def __init__(self):
        self.hooks = {}

    def register_hook(self, name, callback):
        self.hooks.setdefault(name, []).append(callback)


class PluginTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tg = MockTelegram({TOKEN: 'OperatorTestBot', OTHER_TOKEN: 'SomeoneElsesBot'})
        cls.tg.add_set(SET, 'Speedy', SPEEDY_EMOJI)
        cls.base = cls.tg.start()

    @classmethod
    def tearDownClass(cls):
        cls.tg.stop()

    def setUp(self):
        self.tg.calls.clear()
        self.home = tempfile.TemporaryDirectory()
        env = {k: v for k, v in os.environ.items() if k not in ENV_KEYS}
        env.update({'HERMES_HOME': self.home.name, 'TELEGRAM_BOT_TOKEN': TOKEN,
                    'TELEGRAM_HOME_CHANNEL': '424242', 'GODSPEED_STICKER_SET': SET,
                    'GODSPEED_STICKER_API_BASE': self.base})
        self.env = mock.patch.dict(os.environ, env, clear=True)
        self.env.start()
        self.plugin = load_plugin()
        self.ctx = FakeContext()
        self.plugin.register(self.ctx)

    def tearDown(self):
        self.env.stop()
        self.home.cleanup()

    def reply(self, text, platform='telegram'):
        return self.ctx.hooks['transform_llm_output'][0](
            response_text=text, session_id='s1', model='m', platform=platform,
            telemetry_schema_version=1)

    def sent(self):
        return self.tg.calls_to('sendSticker')

    # -- the checks ------------------------------------------------------------------------------
    def test_register_adds_the_reply_hook(self):
        self.assertEqual(list(self.ctx.hooks), ['transform_llm_output'])

    def test_done_tag_sends_exactly_one_done_sticker_and_disappears(self):
        out = self.reply('The report is in your inbox.\n\n[[sticker:done]]')
        self.assertEqual(out, 'The report is in your inbox.')
        sent = self.sent()
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]['params']['sticker'], self.tg.file_id(TOKEN, SET, POSES.index('done')))
        self.assertEqual(sent[0]['params']['chat_id'], '424242')
        self.assertEqual(sent[0]['bot'], '111111')

    def test_every_speedy_pose_sends_its_own_sticker(self):
        for i, pose in enumerate(POSES):
            self.tg.calls.clear()
            self.assertEqual(self.reply('ok [[sticker:%s]]' % pose), 'ok')
            self.assertEqual([c['params']['sticker'] for c in self.sent()],
                             [self.tg.file_id(TOKEN, SET, i)], pose)

    def test_file_ids_come_from_the_operators_own_bot(self):
        self.reply('first [[sticker:copy]]')
        lookups = self.tg.calls_to('getStickerSet')
        self.assertEqual(len(lookups), 1)
        self.assertEqual(lookups[0]['bot'], '111111')
        self.assertNotIn('222222', self.sent()[0]['params']['sticker'])

    def test_set_is_looked_up_once_then_cached(self):
        self.reply('one [[sticker:done]]')
        self.reply('two [[sticker:done]]')
        self.assertEqual(len(self.tg.calls_to('getStickerSet')), 1)
        self.assertEqual(len(self.sent()), 2)

    def test_unknown_tag_is_removed_without_sending_or_crashing(self):
        with self.assertLogs(level=logging.WARNING) as logs:
            out = self.reply('Here you go. [[sticker:party]]')
        self.assertEqual(out, 'Here you go.')
        self.assertEqual(self.sent(), [])
        self.assertIn('unknown tag [[sticker:party]]', '\n'.join(logs.output))

    def test_several_tags_send_one_sticker_and_all_tags_go(self):
        out = self.reply('[[sticker:onit]] Working.\n[[sticker:wat]]\nDone now. [[sticker:done]]')
        self.assertNotIn('[[', out)
        self.assertEqual(len(self.sent()), 1)
        self.assertEqual(self.sent()[0]['params']['sticker'], self.tg.file_id(TOKEN, SET, 1))

    def test_missing_token_strips_tag_and_says_so_plainly(self):
        del os.environ['TELEGRAM_BOT_TOKEN']
        with self.assertLogs(level=logging.WARNING) as logs:
            out = self.reply('All set. [[sticker:done]]')
        self.assertEqual(out, 'All set.')
        self.assertEqual(self.tg.calls, [])
        self.assertIn('no Telegram bot token', '\n'.join(logs.output))
        self.assertIn('TELEGRAM_BOT_TOKEN', '\n'.join(logs.output))

    def test_missing_chat_strips_tag_and_says_so_plainly(self):
        del os.environ['TELEGRAM_HOME_CHANNEL']
        with self.assertLogs(level=logging.WARNING) as logs:
            out = self.reply('All set. [[sticker:done]]')
        self.assertEqual(out, 'All set.')
        self.assertEqual(self.sent(), [])
        self.assertIn('no chat to send the sticker to', '\n'.join(logs.output))

    def test_register_warns_when_token_is_missing(self):
        del os.environ['TELEGRAM_BOT_TOKEN']
        with self.assertLogs(level=logging.WARNING) as logs:
            load_plugin().register(FakeContext())
        self.assertIn('no TELEGRAM_BOT_TOKEN', '\n'.join(logs.output))

    def test_token_from_hermes_dotenv_when_not_in_environment(self):
        del os.environ['TELEGRAM_BOT_TOKEN']
        with open(os.path.join(self.home.name, '.env'), 'w', encoding='utf-8') as fh:
            fh.write('# hermes\nTELEGRAM_BOT_TOKEN="%s"\n' % TOKEN)
        self.reply('ok [[sticker:done]]')
        self.assertEqual(len(self.sent()), 1)

    def test_falls_back_to_first_allowed_user(self):
        del os.environ['TELEGRAM_HOME_CHANNEL']
        os.environ['TELEGRAM_ALLOWED_USERS'] = '777, 888'
        self.reply('ok [[sticker:done]]')
        self.assertEqual(self.sent()[0]['params']['chat_id'], '777')

    def test_unknown_set_is_reported_not_raised(self):
        os.environ['GODSPEED_STICKER_SET'] = 'nope_by_OperatorTestBot'
        with self.assertLogs(level=logging.WARNING) as logs:
            out = self.reply('ok [[sticker:done]]')
        self.assertEqual(out, 'ok')
        self.assertIn('no sticker set', '\n'.join(logs.output))
        self.assertIn('STICKERSET_INVALID', '\n'.join(logs.output))

    def test_unpublished_default_set_does_not_call_telegram(self):
        del os.environ['GODSPEED_STICKER_SET']
        if '<' not in self.plugin.DEFAULT_SET:
            self.skipTest('DEFAULT_SET already filled in by publish-set.sh')
        with self.assertLogs(level=logging.WARNING) as logs:
            out = self.reply('ok [[sticker:done]]')
        self.assertEqual(out, 'ok')
        self.assertEqual(self.tg.calls, [])
        self.assertIn('no sticker set configured', '\n'.join(logs.output))

    def test_other_platforms_only_strip_the_tag(self):
        self.assertEqual(self.reply('ok [[sticker:done]]', platform='cli'), 'ok')
        self.assertEqual(self.sent(), [])

    def test_platform_list_can_be_widened(self):
        os.environ['GODSPEED_STICKER_PLATFORMS'] = 'telegram,cron'
        self.reply('ok [[sticker:done]]', platform='cron')
        self.assertEqual(len(self.sent()), 1)

    def test_reply_without_tag_is_left_alone(self):
        self.assertIsNone(self.reply('Just words.'))
        self.assertEqual(self.tg.calls, [])

    def test_tag_only_reply_becomes_the_emoji(self):
        self.assertEqual(self.reply('[[sticker:done]]'), '\U0001FAE1')
        self.assertEqual(len(self.sent()), 1)

    def test_tag_in_backticks_and_odd_spacing_is_removed(self):
        self.assertEqual(self.reply('Done. `[[ sticker: DONE ]]`'), 'Done.')
        self.assertEqual(len(self.sent()), 1)

    def test_custom_tags_for_your_own_set(self):
        os.environ['GODSPEED_STICKER_TAGS'] = 'yay=\U0001FAE1,hmm=\U0001F4E1'
        self.reply('ok [[sticker:yay]]')
        self.assertEqual(self.sent()[0]['params']['sticker'], self.tg.file_id(TOKEN, SET, 5))
        self.tg.calls.clear()
        self.reply('ok [[sticker:done]]')  # the Speedy names are replaced, not added to
        self.assertEqual(self.sent(), [])

    def test_fixed_chat_overrides_home_channel(self):
        os.environ['GODSPEED_STICKER_CHAT'] = '-100123'
        self.reply('ok [[sticker:done]]')
        self.assertEqual(self.sent()[0]['params']['chat_id'], '-100123')

    def test_sticker_is_silent(self):
        self.reply('ok [[sticker:done]]')
        self.assertIs(self.sent()[0]['params']['disable_notification'], True)

    def test_telegram_down_never_breaks_the_reply_or_leaks_the_token(self):
        os.environ['GODSPEED_STICKER_API_BASE'] = 'http://127.0.0.1:9'  # nothing listens there
        with self.assertLogs(level=logging.WARNING) as logs:
            out = self.reply('ok [[sticker:done]]')
        self.assertEqual(out, 'ok')
        self.assertNotIn(TOKEN, '\n'.join(logs.output))
        self.assertNotIn('test-operator-token', '\n'.join(logs.output))

    def test_bad_api_base_error_does_not_leak_the_token(self):
        os.environ['GODSPEED_STICKER_API_BASE'] = 'htp:/broken'
        with self.assertLogs(level=logging.WARNING) as logs:
            self.reply('ok [[sticker:done]]')
        self.assertNotIn('test-operator-token', '\n'.join(logs.output))


if __name__ == '__main__':
    unittest.main()
