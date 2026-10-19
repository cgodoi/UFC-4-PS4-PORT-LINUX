from paths import ROOT
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import game_check
from test_prepare import fixture


def param_sfo(entries):
    """A minimal param.sfo with UTF-8 string entries."""
    keys = b''.join(k.encode() + b'\0' for k in entries)
    values = [v.encode() + b'\0' for v in entries.values()]
    count = len(entries)
    key_table = 20 + 16 * count
    data_table = key_table + len(keys)
    data = bytearray(struct.pack('<4sIIII', b'\0PSF', 0x101, key_table, data_table, count))
    key_off = data_off = 0
    for key, value in zip(entries, values):
        data += struct.pack('<HHIII', key_off, 0x204, len(value), len(value), data_off)
        key_off += len(key) + 1
        data_off += len(value)
    return bytes(data + keys + b''.join(values))


class GameCheckTests(unittest.TestCase):
    def game(self, title, version, eboot=None):
        path = Path(self.tmp.name)
        (path / 'sce_sys').mkdir(exist_ok=True)
        (path / 'sce_sys/param.sfo').write_bytes(param_sfo({'APP_VER': version, 'TITLE_ID': title}))
        (path / 'eboot.bin').write_bytes(fixture() if eboot is None else eboot)
        return path

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ.pop('BB_SKIP_GAME_CHECK', None)

    def tearDown(self):
        self.tmp.cleanup()

    def test_base_game_without_the_update(self):
        for title, update in (('CUSA06534', '01.14'), ('CUSA14204', '28.00')):
            game = self.game(title, '01.00')
            self.assertEqual(game_check.problem(game), ('missing_update', title, '01.00'))
            self.assertIn(update, game_check.explain(*game_check.problem(game)))

    def test_update_metadata_with_an_old_executable(self):
        game = self.game('CUSA06534', '01.14')
        with mock.patch.dict(game_check.OLD_IMAGES, {game_check.image_sha256(game): '01.00'}):
            self.assertEqual(game_check.problem(game)[0], 'wrong_eboot')
            self.assertIsNone(game_check.profile(game))

    def test_other_build_of_the_update_is_accepted(self):
        # Another executable with the supported update's metadata (e.g. a 6.72+ backport): accepted,
        # without the address-keyed diagnostics of the reference build.
        game = self.game('CUSA06534', '01.14')
        self.assertIsNone(game_check.problem(game))
        self.assertEqual(game_check.profile(game)['name'], 'ufc3')
        self.assertEqual(game_check.profile(game)['variant'], '6.72+')
        self.assertFalse(game_check.profile(game)['known'])
        with mock.patch.object(game_check, 'KNOWN_672', {game_check.image_sha256(game)}):
            self.assertTrue(game_check.profile(game)['known'])

    def test_other_title(self):
        # Bloodborne (bbport's game) and Crash Team Racing (SacredFire's) are not profiles.
        self.assertEqual(game_check.problem(self.game('CUSA03173', '01.09'))[0], 'other_title')
        self.assertEqual(game_check.problem(self.game('CUSA13795', '01.21'))[0], 'other_title')

    def test_unreadable_executable(self):
        self.assertEqual(game_check.problem(self.game('CUSA06534', '01.14', b'junk'))[0], 'unreadable')

    def test_supported_image_passes(self):
        game = self.game('CUSA06534', '01.14')
        table = {game_check.image_sha256(game): game_check.SUPPORTED[game_check.SUPPORTED_IMAGE]}
        with mock.patch.object(game_check, 'SUPPORTED', table):
            self.assertIsNone(game_check.problem(game))
            self.assertEqual(game_check.profile(game)['name'], 'ufc3')
            self.assertEqual(game_check.profile(game)['variant'], '5.05')
            self.assertIn('libSceFios2.prx', game_check.profile(game)['modules'])

    def test_ufc4_image_has_its_own_variant(self):
        # UFC 4's variant keeps UFC 3's address-keyed hooks (they know UFC 3's 5.05 build) off.
        ufc4 = next(p for p in game_check.SUPPORTED.values() if p['name'] == 'ufc4')
        game = self.game('CUSA14204', '28.00')
        with mock.patch.object(game_check, 'SUPPORTED', {game_check.image_sha256(game): ufc4}):
            self.assertIsNone(game_check.problem(game))
            self.assertEqual(game_check.profile(game)['name'], 'ufc4')
            self.assertEqual(game_check.profile(game)['variant'], 'ufc4')

    def test_profile_guess_with_the_check_skipped(self):
        game = self.game('CUSA06534', '01.00')
        self.assertIsNone(game_check.profile(game))
        with mock.patch.dict(os.environ, {'BB_SKIP_GAME_CHECK': '1'}):
            self.assertEqual(game_check.profile(game)['name'], 'ufc3')
            self.assertEqual(game_check.profile(self.game('CUSA14204', '01.00'))['name'], 'ufc4')
            self.assertIsNone(game_check.profile(self.game('CUSA03173', '01.09')))

    def test_skip_switch(self):
        os.environ['BB_SKIP_GAME_CHECK'] = '1'
        self.assertIsNone(game_check.problem(self.game('CUSA06534', '01.00')))

    def test_every_problem_is_explained(self):
        for kind in ('missing_update', 'wrong_eboot', 'other_title', 'unreadable'):
            self.assertIn('CUSA', game_check.explain(kind, 'CUSA06534', '01.00'))
            self.assertIn('CUSA', game_check.explain(kind, 'CUSA14204', '01.00'))
            self.assertIn('CUSA', game_check.explain(kind, 'CUSA00000', '01.00'))


if __name__ == '__main__':
    unittest.main()
