import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from app.services.files import UnsafeArchiveError, inspect_zip, split_file


class FileServiceTests(unittest.TestCase):
    def test_split_creates_verifiable_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.bin"
            payload = b"abcdefghij"
            source.write_bytes(payload)

            parts, manifest_path = split_file(source, root / "out", 4)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(
                [part.read_bytes() for part in parts], [b"abcd", b"efgh", b"ij"]
            )
            self.assertEqual(manifest["source_size"], len(payload))
            self.assertEqual(
                manifest["source_sha256"], hashlib.sha256(payload).hexdigest()
            )

    def test_zip_slip_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "unsafe.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../escape.txt", "no")

            with self.assertRaises(UnsafeArchiveError):
                inspect_zip(archive_path)


if __name__ == "__main__":
    unittest.main()
