import hashlib
import json
import mimetypes
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

SAFE_NAME_PATTERN = re.compile(r"[^\w.()\-+ ]+", re.UNICODE)
MAX_ZIP_MEMBERS = 2_000
MAX_ZIP_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200


def allocate_path(base_dir: Path, extension: str = "") -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    if extension and not extension.startswith("."):
        extension = f".{extension}"
    return base_dir / f"{uuid4().hex}{extension}"


class UnsafeArchiveError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class FileAnalysis:
    size_bytes: int
    sha256: str
    media_type: str
    archive_members: int | None = None
    archive_uncompressed_bytes: int | None = None


def safe_filename(name: str | None) -> str:
    cleaned = SAFE_NAME_PATTERN.sub("_", Path(name or "file.bin").name).strip(" .")
    return cleaned[:180] or "file.bin"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def inspect_zip(path: Path) -> tuple[int, int]:
    total_size = 0
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > MAX_ZIP_MEMBERS:
            raise UnsafeArchiveError("zip_too_many_members")

        for item in members:
            member_path = Path(item.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise UnsafeArchiveError("zip_unsafe_path")
            total_size += item.file_size
            if total_size > MAX_ZIP_UNCOMPRESSED_BYTES:
                raise UnsafeArchiveError("zip_uncompressed_limit")
            if item.file_size and item.compress_size == 0:
                raise UnsafeArchiveError("zip_suspicious_ratio")
            if (
                item.compress_size
                and item.file_size / item.compress_size > MAX_COMPRESSION_RATIO
            ):
                raise UnsafeArchiveError("zip_bomb_detected")
    return len(members), total_size


def analyze_file(path: Path, original_name: str) -> FileAnalysis:
    size = path.stat().st_size
    media_type = mimetypes.guess_type(original_name)[0] or "application/octet-stream"
    members = None
    uncompressed = None
    if zipfile.is_zipfile(path):
        media_type = "application/zip"
        members, uncompressed = inspect_zip(path)
    return FileAnalysis(
        size_bytes=size,
        sha256=sha256_file(path),
        media_type=media_type,
        archive_members=members,
        archive_uncompressed_bytes=uncompressed,
    )


def split_file(
    source: Path, output_dir: Path, chunk_size: int
) -> tuple[list[Path], Path]:
    if chunk_size <= 0:
        raise ValueError("chunk_size_invalid")
    output_dir.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    manifest_parts: list[dict[str, str | int]] = []

    with source.open("rb") as input_file:
        index = 1
        while chunk := input_file.read(chunk_size):
            part_path = output_dir / f"part-{index:04d}.bin"
            part_path.write_bytes(chunk)
            parts.append(part_path)
            manifest_parts.append(
                {
                    "name": part_path.name,
                    "size_bytes": len(chunk),
                    "sha256": sha256_file(part_path),
                }
            )
            index += 1

    manifest_data = {
        "original_file": source.name,
        "original_size_bytes": source.stat().st_size,
        "source_size": source.stat().st_size,
        "source_sha256": sha256_file(source),
        "chunk_size_bytes": chunk_size,
        "parts_count": len(parts),
        "parts": manifest_parts,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return parts, manifest_path
