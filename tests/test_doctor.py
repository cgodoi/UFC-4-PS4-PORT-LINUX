from paths import ROOT
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import doctor


class DoctorTests(unittest.TestCase):
    def test_amd_gpu_sysfs_and_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            device = Path(tmp) / 'card1/device'
            device.mkdir(parents=True)
            (device / 'mem_info_gtt_total').write_text(str(4 * 2**30))
            (device / 'mem_info_vram_total').write_text(str(512 * 2**20))
            (device / 'power_dpm_force_performance_level').write_text('manual\n')
            (device / 'pp_dpm_sclk').write_text('0: 800Mhz\n1: 1600Mhz *\n2: 2700Mhz\n')
            (Path(tmp) / 'card1-eDP-1').mkdir()      # a connector, not a card
            found = doctor.amd_gpus(Path(tmp))
        self.assertEqual(len(found), 1)
        card, info = found[0]
        self.assertEqual((card, info['gtt_gib'], info['level'], info['sclk']), ('card1', 4.0, 'manual', '1600Mhz'))

    def test_report_without_game_and_scrubbed_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / 'data'
            (data / 'logs').mkdir(parents=True)
            (data / 'logs/1.log').write_text('line\n' + 'x' * 500 + '\n')
            (data / 'ufc3.conf').write_text('# comment\nBB_FPS_LIMIT=0\nBB_FSR1=\n')
            with mock.patch.object(doctor, 'amd_gpus', return_value=[('card0', dict(
                    gtt_gib=3.0, vram_gib=0.5, level='manual', sclk='?'))]), \
                 mock.patch.object(doctor, 'glibc_version', return_value=(2, 39)), \
                 mock.patch.object(Path, 'home', return_value=Path(tmp)):
                text = doctor.report(data=data)
        self.assertIn('Game folder: not set', text)
        self.assertIn('ufc3.conf: BB_FPS_LIMIT=0\n', text)
        self.assertIn('glibc 2.39 is older', text)
        self.assertIn('GTT is 3.0 GiB', text)
        self.assertIn("clock mode is 'manual'", text)
        self.assertIn(' [...]', text)
        self.assertNotIn(tmp, text)
        self.assertIn('Data: ~/data', text)

    def test_game_folder_falls_back_to_merged(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / 'CUSA14204'
            base.mkdir()
            (base / 'eboot.bin').write_bytes(b'not an executable')
            merged = Path(tmp) / 'CUSA14204-merged'
            merged.mkdir()
            (merged / 'eboot.bin').write_bytes(b'still not one')
            lines, warnings = doctor.check_game(base)
        self.assertIn(f'Merged folder: {merged}', lines)
        self.assertTrue(any('could not be read' in w for w in warnings))


    def test_scrub_linked_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / 'var/home/me'
            real.mkdir(parents=True)
            (Path(tmp) / 'home').mkdir()
            link = Path(tmp) / 'home/me'
            link.symlink_to(real)
            with mock.patch.object(Path, 'home', return_value=link):
                text = doctor.scrub(f'{real}/Games and {link}/Games')
        self.assertEqual(text, '~/Games and ~/Games')


if __name__ == '__main__':
    unittest.main()
