"""Tests for scripts/: the pack check, publish-set.sh and file-ids.py.

Run from the repository root:  python -m unittest discover -s tests -v

publish-set.sh writes into the manifests and the docs, so these tests run it on a throwaway copy
of the repository, against tests/mock_telegram.py. They need bash and curl; without them those
tests are skipped. Art that has not been delivered yet is replaced by blank placeholder PNGs in
those copies, never in the repository.
"""
from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import pack  # noqa: E402
from mock_telegram import MockTelegram  # noqa: E402

TOKEN = '111111:test-operator-token'
OTHER_TOKEN = '222222:someone-elses-token'
TAGS = [tag for tag, _, _ in pack.TAGS]
FIRST = {tag: emoji for tag, emoji, _ in pack.TAGS}
# A second emoji per tag, as the real manifests carry them (each used once per set).
SECOND = {'onit': '⏳', 'note': '\U0001F305', 'copy': '❓', 'fix': '\U0001F6E0',
          'done': '✅', 'quiet': '\U0001F4A4', 'ok': '\U0001F44C', 'think': '\U0001F4AD',
          'found': '\U0001F4A1', 'oops': '\U0001F648', 'party': '\U0001F973',
          'thanks': '\U0001F49B', 'morning': '\U0001F304', 'night': '⭐'}
TODAY_SECOND = {'speedy': '\U0001F47B', 'bit': '\U0001F916', 'mochi': '\U0001F431'}
TITLES = {'speedy': 'Speedy · Godspeed Mission Control', 'bit': 'Bit · pixel robot',
          'mochi': 'Mochi · ink doodle cat'}
# The emoji lists the live Speedy set had before this repository grew to 15 tags.
LIVE_SPEEDY = [[FIRST[t], TODAY_SECOND['speedy'] if t == 'today' else SECOND[t]] for t in TAGS[:7]]
LIVE_SPEEDY[6] = [FIRST['quiet'], FIRST['night']]  # quiet carried the moon then
PLACEHOLDER = 'speedy_by_<BOT>'
MANIFEST = 'packs/speedy/manifest.json'
# Files that name the sets (the list scripts/pack.py updates after publishing).
NAMED_IN = tuple(p.replace(os.sep, '/') for p in pack.PLACEHOLDER_FILES)


def have_bash_and_curl() -> bool:
    return bool(shutil.which('bash') and shutil.which('curl'))


def copy_repo(dest: str) -> str:
    target = os.path.join(dest, 'repo')
    shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns('.git', '__pycache__'))
    return target


def make_png(path: str, width: int = 512, height: int = 512) -> None:
    """A blank, fully transparent RGBA PNG: a stand-in for art that is not here yet."""
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    raw = b''.join(b'\x00' + b'\x00\x00\x00\x00' * width for _ in range(height))
    with open(path, 'wb') as fh:
        fh.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
                 + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def manifests(repo: str) -> dict:
    out = {}
    for name in sorted(os.listdir(os.path.join(repo, 'packs'))):
        path = os.path.join(repo, 'packs', name, 'manifest.json')
        if os.path.isfile(path):
            with open(path, encoding='utf-8') as fh:
                out[name] = json.load(fh)
    return out


def missing_art(repo: str) -> list:
    return [os.path.join('packs', name, s['file']) for name, m in manifests(repo).items()
            for s in m['stickers'] if not os.path.isfile(os.path.join(repo, 'packs', name, s['file']))]


def fill_missing_art(repo: str) -> int:
    missing = missing_art(repo)
    for rel in missing:
        make_png(os.path.join(repo, rel))
    return len(missing)


def write_manifest(repo: str, m: dict) -> None:
    with open(os.path.join(repo, 'packs', m['name'], 'manifest.json'), 'w', encoding='utf-8') as fh:
        json.dump(m, fh, ensure_ascii=False, indent=2)


def three_sets(repo: str) -> None:
    """Make the copy hold all three sets with all tags (Speedy keeps the stickers it has), and
    blank placeholders for any art that is not there."""
    for name in ('speedy', 'bit', 'mochi'):
        os.makedirs(os.path.join(repo, 'packs', name), exist_ok=True)
        old = manifests(repo).get(name, {})
        have = {s['pose']: s for s in old.get('stickers', [])}
        stickers = [have.get(t) or {'pose': t, 'file': '%s-%s.png' % (name, t),
                                    'emoji': [FIRST[t], TODAY_SECOND[name] if t == 'today' else SECOND[t]]}
                    for t in TAGS]
        write_manifest(repo, {'name': name, 'title': old.get('title', TITLES[name]),
                              'telegram_set_name': old.get('telegram_set_name'),
                              'telegram_set': old.get('telegram_set'), 'stickers': stickers})
    fill_missing_art(repo)


def run(args, cwd, env=None):
    full = dict(os.environ)
    full.pop('BOT_TOKEN', None)
    full.pop('TELEGRAM_BOT_TOKEN', None)
    full.update(env or {})
    full['PYTHONIOENCODING'] = 'utf-8'
    return subprocess.run(args, cwd=cwd, env=full, capture_output=True, text=True,
                          encoding='utf-8', timeout=180)


class PackCheckTest(unittest.TestCase):
    def test_every_pack_in_the_repo_passes(self):
        # Art still being made is stood in for by placeholders, in a copy.
        with tempfile.TemporaryDirectory() as tmp:
            repo = copy_repo(tmp)
            fill_missing_art(repo)
            r = run([sys.executable, 'scripts/pack.py', 'check', '--all'], repo)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn('speedy: ok', r.stdout)

    def test_all_art_is_delivered(self):
        missing = missing_art(ROOT)
        if missing:
            self.skipTest('art not delivered yet: %d file(s) missing, for example %s'
                          % (len(missing), missing[0]))

    def test_delivered_images_meet_telegram_rules(self):
        for name, m in manifests(ROOT).items():
            for s in m['stickers']:
                path = os.path.join(ROOT, 'packs', name, s['file'])
                if not os.path.isfile(path):
                    continue
                w, h = pack.png_size(path)
                self.assertEqual(max(w, h), 512, s['file'])
                self.assertLessEqual(min(w, h), 512, s['file'])
                self.assertLess(os.path.getsize(path), 512 * 1024, s['file'])
                self.assertNotIn('file_id', s)

    def test_every_pack_uses_the_tags_with_their_first_emoji(self):
        for name, m in manifests(ROOT).items():
            poses = [s['pose'] for s in m['stickers']]
            self.assertEqual(poses, [t for t in TAGS if t in poses], name)  # tag order
            for s in m['stickers']:
                self.assertEqual(s['emoji'][0], FIRST[s['pose']], (name, s['pose']))

    def test_three_full_sets_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = copy_repo(tmp)
            three_sets(repo)
            r = run([sys.executable, 'scripts/pack.py', 'check', '--all'], repo)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            for name in ('bit', 'mochi', 'speedy'):
                self.assertIn('%s: ok (15 stickers)' % name, r.stdout)

    def test_check_catches_broken_packs(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = copy_repo(tmp)
            three_sets(repo)
            m = manifests(repo)['speedy']
            st = {s['pose']: s for s in m['stickers']}
            st['today']['file_id'] = 'CAAC-from-some-bot'
            st['onit']['file'] = 'missing.png'
            st['quiet']['emoji'] = [FIRST['quiet'], FIRST['night']]   # the moon twice
            st['ok']['emoji'] = ['✅']                               # not ok's first emoji
            m['stickers'].append({'pose': 'cheer', 'file': 'speedy-done.png', 'emoji': ['\U0001F38A']})
            m['stickers'][0], m['stickers'][1] = m['stickers'][1], m['stickers'][0]
            write_manifest(repo, m)
            with open(os.path.join(repo, 'packs', 'speedy', 'speedy-fix.png'), 'wb') as fh:
                fh.write(b'not a png')
            r = run([sys.executable, 'scripts/pack.py', 'check', 'speedy'], repo)
            self.assertEqual(r.returncode, 1)
            for expected in ('no file_id in a manifest', 'missing.png: file missing',
                             'is on more than one sticker (quiet, night)',
                             "the first emoji of tag 'ok' must be", "unknown tag(s) 'cheer'",
                             'stickers must follow the tag order', 'speedy-fix.png: not a PNG',
                             'emoji ✅ is on more than one sticker (done, ok)'):
                self.assertIn(expected, r.stdout)

    def test_packs_must_share_their_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = copy_repo(tmp)
            three_sets(repo)
            m = manifests(repo)['mochi']
            m['stickers'] = [s for s in m['stickers'] if s['pose'] != 'night']
            write_manifest(repo, m)
            r = run([sys.executable, 'scripts/pack.py', 'check', '--all'], repo)
            self.assertEqual(r.returncode, 1)
            self.assertIn('the packs do not all have the same tags', r.stdout)


@unittest.skipUnless(have_bash_and_curl(), 'needs bash and curl')
class PublishTest(unittest.TestCase):
    def setUp(self):
        self.tg = MockTelegram({TOKEN: 'OperatorTestBot', OTHER_TOKEN: 'SomeoneElsesBot'})
        self.base = self.tg.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = copy_repo(self.tmp.name)
        fill_missing_art(self.repo)

    def tearDown(self):
        self.tg.stop()
        self.tmp.cleanup()

    def publish(self, *packs, token=TOKEN):
        return run(['bash', 'scripts/publish-set.sh', *(packs or ('speedy',))], self.repo,
                   {'BOT_TOKEN': token, 'OWNER_USER_ID': '424242', 'TELEGRAM_API_BASE': self.base})

    def manifest(self, name='speedy'):
        return manifests(self.repo)[name]

    def read(self, rel):
        with open(os.path.join(self.repo, rel), encoding='utf-8') as fh:
            return fh.read()

    def write(self, rel, text):
        with open(os.path.join(self.repo, rel), 'w', encoding='utf-8', newline='') as fh:
            fh.write(text)

    def start_from(self, recorded):
        """Put the copy in a known state, whatever the real repository holds: Speedy never
        published (recorded=None, the docs carry the speedy_by_<BOT> placeholder) or published
        as `recorded` (the docs and the plugin name that set)."""
        m = self.manifest()
        current = m.get('telegram_set_name') or PLACEHOLDER
        target = recorded or PLACEHOLDER
        for rel in NAMED_IN:
            self.write(rel, self.read(rel).replace(current, target))
        m['telegram_set_name'] = recorded
        m['telegram_set'] = 'https://t.me/addstickers/' + recorded if recorded else None
        write_manifest(self.repo, m)
        self.assertIn("'speedy': '%s'" % target, self.read('hermes-plugin/__init__.py'))
        self.assertIn('https://t.me/addstickers/' + target, self.read('README.md'))

    def snapshot(self):
        return {rel: self.read(rel) for rel in NAMED_IN + (MANIFEST,)}

    def test_publish_from_placeholders_names_the_set_after_the_bot(self):
        self.start_from(None)
        self.check_published_as_operator()

    def test_publish_of_a_fork_replaces_the_previous_set_everywhere(self):
        # Someone forks the repository and publishes Speedy under their own bot: every link
        # and the plugin's default must point at their set, not the one they forked.
        self.start_from('speedy_by_UpstreamBot')
        self.write('README.md', self.read('README.md') + '\nNot the same set: speedy_by_UpstreamBotTwo\n')
        self.check_published_as_operator()
        for rel in NAMED_IN + (MANIFEST,):
            self.assertNotRegex(self.read(rel), r'speedy_by_UpstreamBot(?![A-Za-z0-9_])', rel)
        self.assertIn('speedy_by_UpstreamBotTwo', self.read('README.md'))  # whole names only

    def check_published_as_operator(self):
        r = self.publish()
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, out)
        self.assertNotIn('test-operator-token', out)

        count = len(self.manifest()['stickers'])
        created = self.tg.calls_to('createNewStickerSet')
        self.assertEqual(len(created), 1)
        params = created[0]['params']
        self.assertEqual(params['name'], 'speedy_by_OperatorTestBot')
        self.assertEqual(params['user_id'], '424242')
        self.assertEqual(params['title'], TITLES['speedy'])
        stickers = json.loads(params['stickers'])
        self.assertEqual([s['emoji_list'] for s in stickers],
                         [s['emoji'] for s in self.manifest()['stickers']])
        self.assertEqual(created[0]['files'], sorted('s%d' % i for i in range(count)))

        m = self.manifest()
        self.assertEqual(m['telegram_set_name'], 'speedy_by_OperatorTestBot')
        self.assertEqual(m['telegram_set'], 'https://t.me/addstickers/speedy_by_OperatorTestBot')
        self.assertNotIn('file_id', json.dumps(m))
        for rel in NAMED_IN:
            self.assertNotIn(PLACEHOLDER, self.read(rel), rel)
        self.assertIn("'speedy': 'speedy_by_OperatorTestBot'", self.read('hermes-plugin/__init__.py'))
        self.assertIn('https://t.me/addstickers/speedy_by_OperatorTestBot', self.read('README.md'))

        # The manifest is still valid and keeps its one-line-per-sticker shape.
        r = run([sys.executable, 'scripts/pack.py', 'check', 'speedy'], self.repo)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(self.read(MANIFEST).count('{ "pose"'), count)

    def test_all_three_sets_grow_from_the_live_one(self):
        # Telegram holds Speedy with its first seven stickers, quiet still carrying the moon.
        # Publishing everything adds Speedy's eight new stickers in order, takes the moon off
        # quiet, and creates Bit and Mochi with all fifteen.
        three_sets(self.repo)
        self.tg.add_set('speedy_by_OperatorTestBot', TITLES['speedy'], LIVE_SPEEDY, creator=TOKEN)
        r = self.publish('--all')
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, out)
        self.assertNotIn('test-operator-token', out)

        added = self.tg.calls_to('addStickerToSet')
        self.assertEqual([json.loads(c['params']['sticker'])['emoji_list'][0] for c in added],
                         [FIRST[t] for t in TAGS[7:]])
        self.assertTrue(all(c['params']['name'] == 'speedy_by_OperatorTestBot' for c in added))
        created = {c['params']['name']: c for c in self.tg.calls_to('createNewStickerSet')}
        self.assertEqual(sorted(created), ['bit_by_OperatorTestBot', 'mochi_by_OperatorTestBot'])
        self.assertEqual(json.loads(created['bit_by_OperatorTestBot']['params']['stickers'])[0]['emoji_list'],
                         [FIRST['today'], TODAY_SECOND['bit']])
        self.assertEqual(created['mochi_by_OperatorTestBot']['params']['title'], TITLES['mochi'])

        for name in ('speedy', 'bit', 'mochi'):
            set_name = '%s_by_OperatorTestBot' % name
            self.assertEqual(self.tg.emoji_lists(set_name),
                             [s['emoji'] for s in self.manifest(name)['stickers']], name)
            self.assertEqual(self.manifest(name)['telegram_set_name'], set_name)
            self.assertIn("'%s': '%s'" % (name, set_name), self.read('hermes-plugin/__init__.py'))
        self.assertEqual(self.tg.emoji_lists('speedy_by_OperatorTestBot')[6],
                         [FIRST['quiet'], SECOND['quiet']])

        # A second run changes no stickers: nothing created, nothing added.
        self.tg.calls.clear()
        r = self.publish('--all')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.tg.calls_to('createNewStickerSet'), [])
        self.assertEqual(self.tg.calls_to('addStickerToSet'), [])
        self.assertEqual(r.stdout.count('already exists with 15 sticker(s)'), 3)

    def test_a_set_in_another_order_is_left_alone(self):
        three_sets(self.repo)
        swapped = LIVE_SPEEDY[:]
        swapped[0], swapped[1] = swapped[1], swapped[0]
        self.tg.add_set('speedy_by_OperatorTestBot', TITLES['speedy'], swapped, creator=TOKEN)
        before = self.snapshot()
        r = self.publish('speedy')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("sticker 1 in the set is not the manifest's 'today' sticker", r.stdout)
        self.assertIn('Nothing changed', r.stdout)
        for method in ('setStickerEmojiList', 'addStickerToSet', 'setStickerSetTitle'):
            self.assertEqual(self.tg.calls_to(method), [], method)
        self.assertEqual(self.tg.emoji_lists('speedy_by_OperatorTestBot'), swapped)
        self.assertEqual(self.snapshot(), before)

    def test_title_follows_the_manifest(self):
        self.tg.add_set('speedy_by_OperatorTestBot', 'An old title',
                        [s['emoji'] for s in self.manifest()['stickers']], creator=TOKEN)
        r = self.publish('speedy')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual([c['params']['title'] for c in self.tg.calls_to('setStickerSetTitle')],
                         [TITLES['speedy']])

    def test_publishing_again_changes_no_stickers(self):
        self.assertEqual(self.publish().returncode, 0)
        self.tg.calls.clear()
        r = self.publish()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('already exists with %d sticker(s)' % len(self.manifest()['stickers']), r.stdout)
        self.assertEqual(self.tg.calls_to('createNewStickerSet'), [])
        self.assertEqual(self.tg.calls_to('addStickerToSet'), [])
        self.assertEqual(self.tg.calls_to('setStickerSetTitle'), [])

    def test_refusal_is_reported_without_the_token_and_changes_nothing(self):
        before = self.snapshot()
        r = run(['bash', 'scripts/publish-set.sh', 'speedy'], self.repo,
                {'BOT_TOKEN': '999:not-a-known-bot', 'OWNER_USER_ID': '1', 'TELEGRAM_API_BASE': self.base})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('Telegram refused: Unauthorized', r.stdout)
        self.assertNotIn('not-a-known-bot', r.stdout + r.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_missing_token_is_explained(self):
        r = run(['bash', 'scripts/publish-set.sh', 'speedy'], self.repo, {'OWNER_USER_ID': '1'})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('Set BOT_TOKEN', r.stdout + r.stderr)

    def test_unknown_pack_is_explained(self):
        r = self.publish('nosuchpack')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("No pack called 'nosuchpack'", r.stdout)

    def test_file_ids_are_the_asking_bots_own(self):
        self.assertEqual(self.publish().returncode, 0)
        env = {'BOT_TOKEN': OTHER_TOKEN, 'TELEGRAM_API_BASE': self.base}
        r = run([sys.executable, 'scripts/file-ids.py', '--json'], self.repo, env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        ids = json.loads(r.stdout)
        poses = [s['pose'] for s in self.manifest()['stickers']]
        self.assertEqual(list(ids), poses)
        self.assertEqual(ids['done'], self.tg.file_id(OTHER_TOKEN, 'speedy_by_OperatorTestBot', 5))

        for arg in ('speedy', 'https://t.me/addstickers/speedy_by_OperatorTestBot'):
            r = run([sys.executable, 'scripts/file-ids.py', arg], self.repo, env)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn('done ', r.stdout)
            self.assertNotIn('someone-elses-token', r.stdout + r.stderr)

        r = run([sys.executable, 'scripts/file-ids.py', '--prompt'], self.repo, env)
        self.assertEqual(r.returncode, 2)  # no such mode any more

    def test_file_ids_for_a_set_republished_under_another_bot(self):
        # Someone republishes a set under their own bot: the tags still come out right.
        self.tg.add_set('speedy_by_SomeoneElsesBot', 'Speedy', [FIRST[t] for t in TAGS])
        r = run([sys.executable, 'scripts/file-ids.py', 'speedy_by_SomeoneElsesBot', '--json'],
                self.repo, {'BOT_TOKEN': OTHER_TOKEN, 'TELEGRAM_API_BASE': self.base})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(list(json.loads(r.stdout)), TAGS)

    def test_file_ids_for_an_unpublished_pack_or_unknown_set(self):
        three_sets(self.repo)
        env = {'BOT_TOKEN': OTHER_TOKEN, 'TELEGRAM_API_BASE': self.base}
        m = self.manifest('bit')
        m['telegram_set_name'] = None
        write_manifest(self.repo, m)
        r = run([sys.executable, 'scripts/file-ids.py', 'bit'], self.repo, env)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('The bit set has not been published yet', r.stdout + r.stderr)
        r = run([sys.executable, 'scripts/file-ids.py', 'nope_by_Nobody'], self.repo, env)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('STICKERSET_INVALID', r.stdout + r.stderr)


if __name__ == '__main__':
    unittest.main()
