"""Tests for scripts/: the pack check, publish-set.sh and file-ids.py.

Run from the repository root:  python -m unittest discover -s tests -v

publish-set.sh writes into the manifest and the docs, so these tests run it on a throwaway copy
of the repository, against tests/mock_telegram.py. They need bash and curl; without them those
tests are skipped.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from mock_telegram import MockTelegram  # noqa: E402

TOKEN = '111111:test-operator-token'
OTHER_TOKEN = '222222:someone-elses-token'
SPEEDY_POSES = ['today', 'onit', 'note', 'copy', 'fix', 'done', 'quiet']


def have_bash_and_curl() -> bool:
    return bool(shutil.which('bash') and shutil.which('curl'))


def copy_repo(dest: str) -> str:
    target = os.path.join(dest, 'repo')
    shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns('.git', '__pycache__'))
    return target


def run(args, cwd, env=None):
    full = dict(os.environ)
    full.pop('BOT_TOKEN', None)
    full.pop('TELEGRAM_BOT_TOKEN', None)
    full.update(env or {})
    full['PYTHONIOENCODING'] = 'utf-8'
    return subprocess.run(args, cwd=cwd, env=full, capture_output=True, text=True,
                          encoding='utf-8', timeout=120)


class PackCheckTest(unittest.TestCase):
    def test_every_pack_in_the_repo_passes(self):
        r = run([sys.executable, 'scripts/pack.py', 'check', '--all'], ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('speedy: ok (7 stickers)', r.stdout)

    def test_speedy_images_meet_telegram_rules(self):
        sys.path.insert(0, os.path.join(ROOT, 'scripts'))
        import pack
        m = pack.load('speedy')
        self.assertEqual([s['pose'] for s in m['stickers']], SPEEDY_POSES)
        for s in m['stickers']:
            path = os.path.join(ROOT, 'packs', 'speedy', s['file'])
            self.assertEqual(pack.png_size(path), (512, 512), s['file'])
            self.assertLess(os.path.getsize(path), 512 * 1024, s['file'])
            self.assertNotIn('file_id', s)

    def test_check_catches_broken_packs(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = copy_repo(tmp)
            mpath = os.path.join(repo, 'packs', 'speedy', 'manifest.json')
            with open(mpath, encoding='utf-8') as fh:
                m = json.load(fh)
            m['stickers'][0]['file_id'] = 'CAAC-from-some-bot'
            m['stickers'][1]['file'] = 'missing.png'
            m['stickers'][2]['emoji'] = m['stickers'][3]['emoji']
            with open(mpath, 'w', encoding='utf-8') as fh:
                json.dump(m, fh, ensure_ascii=False)
            with open(os.path.join(repo, 'packs', 'speedy', 'speedy-fix.png'), 'wb') as fh:
                fh.write(b'not a png')
            r = run([sys.executable, 'scripts/pack.py', 'check', 'speedy'], repo)
            self.assertEqual(r.returncode, 1)
            for expected in ('no file_id in a manifest', 'missing.png: file missing',
                             'first emoji of every sticker must be unique',
                             'speedy-fix.png: not a PNG'):
                self.assertIn(expected, r.stdout)


@unittest.skipUnless(have_bash_and_curl(), 'needs bash and curl')
class PublishTest(unittest.TestCase):
    def setUp(self):
        self.tg = MockTelegram({TOKEN: 'OperatorTestBot', OTHER_TOKEN: 'SomeoneElsesBot'})
        self.base = self.tg.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = copy_repo(self.tmp.name)

    def tearDown(self):
        self.tg.stop()
        self.tmp.cleanup()

    def publish(self, token=TOKEN):
        return run(['bash', 'scripts/publish-set.sh', 'speedy'], self.repo,
                   {'BOT_TOKEN': token, 'OWNER_USER_ID': '424242', 'TELEGRAM_API_BASE': self.base})

    def manifest(self):
        with open(os.path.join(self.repo, 'packs', 'speedy', 'manifest.json'), encoding='utf-8') as fh:
            return json.load(fh)

    def read(self, rel):
        with open(os.path.join(self.repo, rel), encoding='utf-8') as fh:
            return fh.read()

    def test_publish_names_the_set_after_the_bot_and_records_it(self):
        r = self.publish()
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, out)
        self.assertNotIn('test-operator-token', out)

        created = self.tg.calls_to('createNewStickerSet')
        self.assertEqual(len(created), 1)
        params = created[0]['params']
        self.assertEqual(params['name'], 'speedy_by_OperatorTestBot')
        self.assertEqual(params['user_id'], '424242')
        self.assertEqual(params['title'], 'Speedy · Godspeed Mission Control')
        stickers = json.loads(params['stickers'])
        self.assertEqual([s['emoji_list'] for s in stickers],
                         [s['emoji'] for s in self.manifest()['stickers']])
        self.assertEqual(created[0]['files'], ['s%d' % i for i in range(7)])

        m = self.manifest()
        self.assertEqual(m['telegram_set_name'], 'speedy_by_OperatorTestBot')
        self.assertEqual(m['telegram_set'], 'https://t.me/addstickers/speedy_by_OperatorTestBot')
        self.assertNotIn('file_id', json.dumps(m))
        for rel in ('README.md', 'INTEGRATIONS.md', 'hermes-plugin/README.md', 'hermes-plugin/__init__.py'):
            text = self.read(rel)
            self.assertNotIn('speedy_by_<BOT>', text, rel)
        self.assertIn("DEFAULT_SET = 'speedy_by_OperatorTestBot'", self.read('hermes-plugin/__init__.py'))
        self.assertIn('https://t.me/addstickers/speedy_by_OperatorTestBot', self.read('README.md'))

        # The manifest is still valid and keeps its one-line-per-sticker shape.
        r = run([sys.executable, 'scripts/pack.py', 'check', 'speedy'], self.repo)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(self.read('packs/speedy/manifest.json').count('{ "pose"'), 7)

    def test_publishing_again_changes_nothing_on_telegram(self):
        self.assertEqual(self.publish().returncode, 0)
        self.tg.calls.clear()
        r = self.publish()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('already exists with 7 sticker(s)', r.stdout)
        self.assertEqual(self.tg.calls_to('createNewStickerSet'), [])
        self.assertEqual(self.tg.calls_to('addStickerToSet'), [])

    def test_new_stickers_in_the_manifest_are_added_to_the_end(self):
        self.assertEqual(self.publish().returncode, 0)
        pack_dir = os.path.join(self.repo, 'packs', 'speedy')
        shutil.copy(os.path.join(pack_dir, 'speedy-done.png'), os.path.join(pack_dir, 'speedy-cheer.png'))
        m = self.manifest()
        m['stickers'].append({'pose': 'cheer', 'file': 'speedy-cheer.png', 'emoji': ['\U0001F389'],
                              'when': 'something good happened'})
        with open(os.path.join(pack_dir, 'manifest.json'), 'w', encoding='utf-8') as fh:
            json.dump(m, fh, ensure_ascii=False, indent=2)
        self.tg.calls.clear()
        r = self.publish()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        added = self.tg.calls_to('addStickerToSet')
        self.assertEqual(len(added), 1)
        self.assertEqual(json.loads(added[0]['params']['sticker'])['emoji_list'], ['\U0001F389'])
        self.assertEqual(added[0]['files'], ['s0'])
        self.assertIn('Telegram now lists 8 sticker(s)', r.stdout)

    def test_refusal_is_reported_without_the_token(self):
        r = run(['bash', 'scripts/publish-set.sh', 'speedy'], self.repo,
                {'BOT_TOKEN': '999:not-a-known-bot', 'OWNER_USER_ID': '1', 'TELEGRAM_API_BASE': self.base})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('Telegram refused: Unauthorized', r.stdout)
        self.assertNotIn('not-a-known-bot', r.stdout + r.stderr)
        self.assertIsNone(self.manifest()['telegram_set_name'])

    def test_missing_token_is_explained(self):
        r = run(['bash', 'scripts/publish-set.sh', 'speedy'], self.repo, {'OWNER_USER_ID': '1'})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('Set BOT_TOKEN', r.stdout + r.stderr)

    def test_file_ids_are_the_asking_bots_own(self):
        self.assertEqual(self.publish().returncode, 0)
        env = {'BOT_TOKEN': OTHER_TOKEN, 'TELEGRAM_API_BASE': self.base}
        r = run([sys.executable, 'scripts/file-ids.py', '--json'], self.repo, env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        ids = json.loads(r.stdout)
        self.assertEqual(list(ids), SPEEDY_POSES)
        self.assertEqual(ids['done'], self.tg.file_id(OTHER_TOKEN, 'speedy_by_OperatorTestBot', 5))

        r = run([sys.executable, 'scripts/file-ids.py', 'https://t.me/addstickers/speedy_by_OperatorTestBot'],
                self.repo, env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('done ', r.stdout)
        self.assertNotIn('someone-elses-token', r.stdout + r.stderr)

        r = run([sys.executable, 'scripts/file-ids.py', '--prompt'], self.repo, env)
        self.assertIn('When you finished something you were asked to do, send sticker %s'
                      % ids['done'], r.stdout)

    def test_file_ids_for_a_set_republished_under_another_bot(self):
        # Someone republishes Speedy under their own bot: the poses still come out right.
        self.tg.add_set('speedy_by_SomeoneElsesBot', 'Speedy',
                        [s['emoji'][0] for s in self.manifest()['stickers']])
        r = run([sys.executable, 'scripts/file-ids.py', 'speedy_by_SomeoneElsesBot', '--json'],
                self.repo, {'BOT_TOKEN': OTHER_TOKEN, 'TELEGRAM_API_BASE': self.base})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(list(json.loads(r.stdout)), SPEEDY_POSES)

    def test_file_ids_unknown_set(self):
        r = run([sys.executable, 'scripts/file-ids.py', 'nope_by_Nobody'], self.repo,
                {'BOT_TOKEN': OTHER_TOKEN, 'TELEGRAM_API_BASE': self.base})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('STICKERSET_INVALID', r.stdout + r.stderr)


if __name__ == '__main__':
    unittest.main()
