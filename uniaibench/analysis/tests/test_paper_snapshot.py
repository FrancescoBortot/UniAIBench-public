from __future__ import annotations

import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "tools/validate_paper_snapshot.py"
SPEC = importlib.util.spec_from_file_location("validate_paper_snapshot", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
SNAPSHOT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SNAPSHOT)


class FrozenPaperTests(unittest.TestCase):
    def test_modified_missing_and_added_files_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paper = Path(temporary)
            source = paper / "main.tex"
            source.write_bytes(b"fixed manuscript")
            expected = {"main.tex": hashlib.sha256(source.read_bytes()).hexdigest()}
            self.assertEqual(SNAPSHOT.verify(paper, expected), [])
            source.write_bytes(b"modified manuscript")
            self.assertIn("hash changed", SNAPSHOT.verify(paper, expected)[0])
            source.unlink()
            self.assertIn("missing", SNAPSHOT.verify(paper, expected)[0])
            source.write_bytes(b"fixed manuscript")
            (paper / "extension.tex").write_bytes(b"additional material")
            self.assertIn("unexpected", SNAPSHOT.verify(paper, expected)[0])


if __name__ == "__main__":
    unittest.main()
