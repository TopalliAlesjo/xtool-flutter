from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ScriptFormatTests(unittest.TestCase):
    def test_wsl_scripts_and_environment_template_keep_lf_on_windows(self):
        scripts = ROOT / 'flutter/scripts'
        targets = [*scripts.glob('*.sh'), *scripts.glob('*.py'), scripts / 'env.sh.example',
                   *(ROOT / 'flutter/windows').glob('*.py'), *(ROOT / 'flutter/windows').glob('*.cjs')]
        for path in targets:
            with self.subTest(file=path.name):
                self.assertNotIn(b'\r', path.read_bytes(), f'{path.name} must use LF for WSL')
        self.assertIn('*.sh.example text eol=lf', (ROOT / '.gitattributes').read_text())


if __name__ == '__main__':
    unittest.main()
