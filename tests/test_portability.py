import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import launch
from scripts.setup_env import platform_key, validate_wheels
from scripts.wheel_manifest import build_manifest


class PortabilityTests(unittest.TestCase):
    def test_platform_selection(self):
        cases=[('Darwin','arm64','macos-arm64-py311'),('Darwin','x86_64','macos-x86_64-py311'),
               ('Linux','AMD64','linux-x86_64-py311'),('Linux','aarch64','linux-aarch64-py311'),
               ('Windows','AMD64','windows-amd64-py311')]
        for os,cpu,key in cases:
            with self.subTest(os=os,cpu=cpu):self.assertEqual(platform_key(os,cpu),key)
        self.assertIsNone(platform_key('Windows','ARM64'))
        self.assertIsNone(platform_key('Linux','armv7l'))

    def test_incomplete_or_tampered_wheelhouse_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'test').mkdir();wheel=root/'test/package.whl';wheel.write_bytes(b'original')
            (root/'manifest.json').write_text(json.dumps({'test/package.whl':hashlib.sha256(b'original').hexdigest()}))
            self.assertEqual(validate_wheels(root,'test'),root/'test')
            wheel.write_bytes(b'tampered')
            with self.assertRaisesRegex(RuntimeError,'Повреждён'):validate_wheels(root,'test')
            with self.assertRaisesRegex(RuntimeError,'Неполный'):validate_wheels(root,'absent')

    def test_server_arguments_preserved(self):
        with patch('launch.environment_ready',return_value=True),patch('launch.subprocess.call',return_value=0) as run:
            self.assertEqual(launch.main(['--serve','--port','8766']),0)
            self.assertEqual(run.call_args.args[0][-2:],['--port','8766'])
            self.assertTrue(run.call_args.args[0][1].endswith('serve.py'))

    def test_paths_with_spaces_are_separate_arguments(self):
        with patch('launch.environment_ready',return_value=True),patch('launch.subprocess.call',return_value=0) as run:
            launch.main(['--data','path with spaces/data','--out','path with spaces/result'])
            args=run.call_args.args[0]
            self.assertEqual(Path(args[args.index('--data')+1]),Path('path with spaces/data').resolve())
            self.assertEqual(Path(args[args.index('--out')+1]),Path('path with spaces/result').resolve())

    def test_manifest_uses_portable_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'windows-amd64-py311').mkdir()
            (root/'windows-amd64-py311'/'example.whl').write_bytes(b'package')
            manifest=build_manifest(root)
            self.assertEqual(list(manifest),['windows-amd64-py311/example.whl'])
            self.assertEqual(next(iter(manifest.values())),hashlib.sha256(b'package').hexdigest())
