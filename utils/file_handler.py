"""
File Handler

Safe, project-aware file I/O utilities used across agents and tools.

Responsibilities:
- Resolve paths relative to the project root
- Read / write text and JSON with consistent encoding and error handling
- Manage temp files with guaranteed cleanup (context manager)
- List files by extension with optional recursion
- Atomic writes (write-to-temp then rename) to prevent partial files on crash

Usage:
    from utils.file_handler import FileHandler

    fh = FileHandler()

    # Read / write
    text  = fh.read_text("data/laws/cybersecurity/parsed/act1038.txt")
    data  = fh.read_json("data/laws/sector_mapping.json")
    fh.write_text("data/output/report.txt", content)
    fh.write_json("data/cache/results.json", my_dict)

    # Temp files
    with fh.temp_file(suffix=".pdf") as tmp:
        process(tmp)          # auto-deleted on exit

    # Discovery
    pdfs = fh.list_files("data/laws/cybersecurity/raw", ext=".pdf")
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Optional


class FileHandler:
    """
    Project-aware file utility class.

    All relative paths are resolved against ``project_root``.  Absolute paths
    are used as-is.  Every write is atomic: content is written to a sibling
    ``.tmp`` file first, then renamed, so a crash mid-write never leaves a
    partial file behind.
    """

    def __init__(self, project_root: Optional[Path] = None):
        if project_root is None:
            # Infer from package location: utils/ is one level below project root
            project_root = Path(__file__).parent.parent
        self.project_root = Path(project_root).resolve()

    # ------------------------------------------------------------------
    # Path resolution
    # ------------------------------------------------------------------

    def resolve(self, path: str | Path) -> Path:
        """
        Return an absolute ``Path``.

        - Absolute paths are returned unchanged.
        - Relative paths are resolved against ``self.project_root``.
        """
        p = Path(path)
        return p if p.is_absolute() else (self.project_root / p).resolve()

    def ensure_parent(self, path: str | Path) -> Path:
        """Resolve *path* and create its parent directories if needed."""
        resolved = self.resolve(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved

    # ------------------------------------------------------------------
    # Text I/O
    # ------------------------------------------------------------------

    def read_text(self, path: str | Path, encoding: str = "utf-8") -> str:
        """
        Read and return the full text of a file.

        Raises:
            FileNotFoundError: If the path does not exist.
            IOError: On read failure.
        """
        resolved = self.resolve(path)
        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {resolved}")
        return resolved.read_text(encoding=encoding)

    def write_text(
        self,
        path: str | Path,
        content: str,
        encoding: str = "utf-8",
        *,
        atomic: bool = True,
    ) -> Path:
        """
        Write *content* to *path*.

        Args:
            path: Destination path (relative or absolute).
            content: String content to write.
            encoding: Text encoding (default UTF-8).
            atomic: If True (default), write via a temp file then rename to
                prevent partial writes on crash.

        Returns:
            Resolved ``Path`` of the written file.
        """
        resolved = self.ensure_parent(path)

        if atomic:
            tmp_path = resolved.with_suffix(resolved.suffix + ".tmp")
            try:
                tmp_path.write_text(content, encoding=encoding)
                tmp_path.replace(resolved)
            except Exception:
                tmp_path.unlink(missing_ok=True)
                raise
        else:
            resolved.write_text(content, encoding=encoding)

        return resolved

    def append_text(
        self,
        path: str | Path,
        content: str,
        encoding: str = "utf-8",
    ) -> Path:
        """Append *content* to *path*, creating the file if it doesn't exist."""
        resolved = self.ensure_parent(path)
        with open(resolved, "a", encoding=encoding) as f:
            f.write(content)
        return resolved

    # ------------------------------------------------------------------
    # JSON I/O
    # ------------------------------------------------------------------

    def read_json(self, path: str | Path, encoding: str = "utf-8") -> Any:
        """
        Read and parse a JSON file.

        Returns:
            Parsed Python object (dict, list, etc.).

        Raises:
            FileNotFoundError: File doesn't exist.
            json.JSONDecodeError: File content is not valid JSON.
        """
        text = self.read_text(path, encoding=encoding)
        return json.loads(text)

    def write_json(
        self,
        path: str | Path,
        data: Any,
        *,
        indent: int = 2,
        ensure_ascii: bool = False,
        atomic: bool = True,
    ) -> Path:
        """
        Serialise *data* to JSON and write to *path*.

        Args:
            indent: Pretty-print indentation (default 2).
            ensure_ascii: If False (default), write non-ASCII characters as-is.
            atomic: Atomic write via temp file (default True).

        Returns:
            Resolved path of the written file.
        """
        serialised = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii, default=str)
        return self.write_text(path, serialised, atomic=atomic)

    def append_jsonl(self, path: str | Path, record: Any) -> Path:
        """
        Append a single JSON record as a new line to a ``.jsonl`` file.

        Creates the file if it doesn't exist.  Safe for use as a rolling log.
        """
        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
        return self.append_text(path, line)

    def read_jsonl(self, path: str | Path) -> list[Any]:
        """
        Read all records from a ``.jsonl`` file.

        Returns:
            List of parsed records (skips blank lines and malformed lines).
        """
        resolved = self.resolve(path)
        if not resolved.exists():
            return []

        records = []
        with open(resolved, encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    # Skip corrupt lines silently — log at call site if needed
                    pass
        return records

    # ------------------------------------------------------------------
    # Temp file management
    # ------------------------------------------------------------------

    @contextmanager
    def temp_file(
        self,
        suffix: str = "",
        prefix: str = "grac_",
        content: Optional[str] = None,
        encoding: str = "utf-8",
    ) -> Generator[Path, None, None]:
        """
        Context manager that yields a temporary file path and deletes it on exit.

        Args:
            suffix: File extension, e.g. ``".pdf"``.
            prefix: Filename prefix (default ``"grac_"``).
            content: If given, write this string to the temp file before yielding.
            encoding: Encoding for *content* (default UTF-8).

        Usage::

            with file_handler.temp_file(suffix=".txt", content="hello") as tmp:
                process(tmp)
            # tmp is deleted here
        """
        fd, tmp_str = tempfile.mkstemp(suffix=suffix, prefix=prefix)
        tmp_path = Path(tmp_str)
        try:
            os.close(fd)
            if content is not None:
                tmp_path.write_text(content, encoding=encoding)
            yield tmp_path
        finally:
            tmp_path.unlink(missing_ok=True)

    @contextmanager
    def temp_dir(self, prefix: str = "grac_") -> Generator[Path, None, None]:
        """
        Context manager that yields a temporary directory and deletes it on exit.

        Usage::

            with file_handler.temp_dir() as tmpdir:
                (tmpdir / "work.txt").write_text("...")
            # tmpdir and all contents deleted here
        """
        tmp = Path(tempfile.mkdtemp(prefix=prefix))
        try:
            yield tmp
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # File discovery
    # ------------------------------------------------------------------

    def list_files(
        self,
        directory: str | Path,
        ext: Optional[str] = None,
        *,
        recursive: bool = False,
    ) -> list[Path]:
        """
        Return sorted list of files in *directory*.

        Args:
            directory: Directory to search (relative or absolute).
            ext: Optional extension filter, e.g. ``".pdf"``.  Case-insensitive.
            recursive: If True, search subdirectories as well.

        Returns:
            Sorted list of absolute ``Path`` objects.
        """
        resolved = self.resolve(directory)
        if not resolved.is_dir():
            return []

        pattern = f"**/*{ext}" if (recursive and ext) else (f"*{ext}" if ext else "*")
        glob_fn = resolved.rglob if recursive else resolved.glob

        files = [p for p in glob_fn(f"*{ext or ''}") if p.is_file()]
        if ext:
            files = [f for f in files if f.suffix.lower() == ext.lower()]

        return sorted(files)

    def list_pdfs(self, directory: str | Path, *, recursive: bool = False) -> list[Path]:
        """Convenience wrapper: list all PDF files in *directory*."""
        return self.list_files(directory, ext=".pdf", recursive=recursive)

    # ------------------------------------------------------------------
    # Safe delete / copy
    # ------------------------------------------------------------------

    def safe_delete(self, path: str | Path) -> bool:
        """
        Delete a file if it exists.  Never raises.

        Returns:
            True if the file was deleted, False if it didn't exist.
        """
        resolved = self.resolve(path)
        if resolved.exists():
            resolved.unlink()
            return True
        return False

    def copy_file(self, src: str | Path, dst: str | Path) -> Path:
        """
        Copy *src* to *dst*, creating parent directories as needed.

        Returns:
            Resolved destination path.
        """
        resolved_src = self.resolve(src)
        resolved_dst = self.ensure_parent(dst)
        shutil.copy2(str(resolved_src), str(resolved_dst))
        return resolved_dst

    # ------------------------------------------------------------------
    # Existence & size helpers
    # ------------------------------------------------------------------

    def exists(self, path: str | Path) -> bool:
        """Return True if *path* exists (file or directory)."""
        return self.resolve(path).exists()

    def file_size_bytes(self, path: str | Path) -> int:
        """Return file size in bytes, or 0 if the file doesn't exist."""
        resolved = self.resolve(path)
        return resolved.stat().st_size if resolved.exists() else 0

    def is_empty(self, path: str | Path) -> bool:
        """Return True if the file is missing or has zero bytes."""
        return self.file_size_bytes(path) == 0


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

file_handler = FileHandler()
