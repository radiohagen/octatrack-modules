import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from verify_provenance import verify


class ProvenanceChecks(unittest.TestCase):
    def test_changed_bytes_and_executable_mode_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / 'source.s'
            path.write_bytes(b'original\n')
            path.chmod(0o644)
            entry = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'source_mode': '100644'}
            receipt = {'files': {'source.s': entry}}
            self.assertEqual(verify(root, receipt), [])
            path.write_bytes(b'changed\n')
            self.assertIn('bytes differ', verify(root, receipt)[0])
            entry['published_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(verify(root, receipt), [])
            path.chmod(0o755)
            self.assertIn('mode differs', verify(root, receipt)[0])

    def test_missing_source_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipt = {'files': {'source.s': {'sha256': '0' * 64}}}
            self.assertTrue(verify(root, receipt))
            (root / 'target.s').write_text('same bytes do not authorize a symlink')
            (root / 'source.s').symlink_to('target.s')
            self.assertTrue(verify(root, receipt))
