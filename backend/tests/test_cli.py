"""Tests for the ``ingest_laws`` command-line entry point.

Separate from :mod:`test_ingestion`, which exercises the library underneath.
What is under test here is the process an operator actually runs: its exit
codes, what it prints, and — just as load-bearing — what it must never print.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pymupdf
import pytest

# Put the backend root on sys.path, as tests/conftest.py does.
_BACKEND_ROOT: Path = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from scripts.ingest_laws import (  # noqa: E402
    _MAX_FILENAME_CHARS,
    EXIT_DOCUMENT_FAILED,
    EXIT_NO_SOURCE,
    EXIT_NOTHING_WRITTEN,
    EXIT_OK,
    EXIT_WRITE_FAILED,
    _shorten,
    main,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_pdf(path: Path, text_per_page: list[str]) -> Path:
    """Write a synthetic text-layer PDF, one string per page."""
    document = pymupdf.open()
    try:
        for text in text_per_page:
            page = document.new_page()
            assert page.insert_textbox(pymupdf.Rect(40, 40, 550, 800), text, fontsize=11) >= 0
        document.save(path)
    finally:
        document.close()
    return path


def _write_corrupt_pdf(path: Path) -> Path:
    path.write_bytes(b"not a pdf at all")
    return path


@pytest.fixture
def laws_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "laws"
    directory.mkdir()
    return directory


@pytest.fixture
def index_dir(tmp_path: Path) -> Path:
    return tmp_path / "index"


def _run_cli(laws: Path, index: Path) -> subprocess.CompletedProcess[str]:
    """Run the CLI as a real subprocess, so exit codes and streams are real.

    ``PYTHONIOENCODING`` is stripped from the child environment and output is
    decoded as UTF-8. Both are deliberate, and without them these tests cannot
    fail when they should.

    The developer's own shell usually exports ``PYTHONIOENCODING=utf-8``, which
    propagates to the child and makes the CLI encode correctly *because it was
    told to*, not because of anything the CLI does — so the mojibake test would
    pass against the unfixed code. A plain shell has no such variable: Python
    falls back to the console code page, ``cp1252`` on this machine. Removing
    it reproduces the environment an operator actually runs in.

    Decoding as UTF-8 is then not a convenience but a requirement: with the
    fix, the CLI writes UTF-8 bytes whatever the ambient code page, and
    ``text=True`` would decode them as ``cp1252`` and report the very mojibake
    the CLI no longer produces.
    """
    env = {key: value for key, value in os.environ.items() if key != "PYTHONIOENCODING"}
    return subprocess.run(
        [
            sys.executable,
            str(_BACKEND_ROOT / "scripts" / "ingest_laws.py"),
            "--laws-dir",
            str(laws),
            "--index-dir",
            str(index),
        ],
        capture_output=True,
        env=env,
        cwd=str(_BACKEND_ROOT),
    )


def _decode(raw: bytes) -> str:
    """Decode child output as UTF-8, whatever the ambient code page claims."""
    return raw.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# A shortened filename must stay identifiable
# ---------------------------------------------------------------------------


def test_two_long_filenames_differing_only_in_their_tail_stay_distinguishable() -> None:
    """The failure this pins is an operator re-downloading the wrong Act.

    Statute filenames follow a pattern, and the part that distinguishes two
    copies of the same Act is the tail: ``... Act X of YYYY (1).pdf`` and
    ``... Act X of YYYY (2).pdf``. A head truncation throws exactly that away,
    so the summary printed two identical lines and the operator had no way to
    tell which file to fix.
    """
    prefix = "Indian Penal Code 1860 as amended by Act YYYY" + "Y" * 45
    alpha = _shorten(f"{prefix}PARTALPHA.pdf")
    beta = _shorten(f"{prefix}PARTBETA.pdf")

    assert alpha != beta, f"both failures print identically:\n  {alpha!r}\n  {beta!r}"
    # The differentiating part has to actually be *shown*, not merely differ.
    assert "ALPHA" in alpha and "BETA" in beta
    assert alpha.endswith(".pdf"), f"the extension was lost: {alpha!r}"


def test_shortened_filenames_stay_inside_the_display_budget() -> None:
    """The budget exists to keep one failure on one terminal line."""
    long_name = "A" * 400 + ".pdf"

    shortened = _shorten(long_name)

    assert len(shortened) <= _MAX_FILENAME_CHARS
    assert shortened.endswith(".pdf")


def test_a_filename_within_budget_is_printed_whole() -> None:
    """Truncation must not fire on a name that already fits.

    The common case, and a bug here would be invisible in the one-line demo and
    obvious in a real corpus.
    """
    assert _shorten("BNS 2023.pdf") == "BNS 2023.pdf"
    # The boundary itself: exactly at the budget is not longer than it.
    assert _shorten("A" * _MAX_FILENAME_CHARS) == "A" * _MAX_FILENAME_CHARS
    assert _shorten("A" * (_MAX_FILENAME_CHARS + 1)) != "A" * (_MAX_FILENAME_CHARS + 1)


# ---------------------------------------------------------------------------
# The report must survive a console that cannot encode the filename
# ---------------------------------------------------------------------------


def test_a_devanagari_filename_is_not_mojibake_on_a_redirected_pipe(
    laws_dir: Path, index_dir: Path
) -> None:
    """A Hindi statute's name must reach the operator readable.

    This is the payoff of the Devanagari ``law_id`` work. A Hindi Act on disk is
    named in Devanagari, and that name is how the operator finds the file to fix
    — so if the CLI prints mojibake, keeping the name intact in the index buys
    nothing. On a redirected pipe the stream inherits the console code page
    (``cp1252`` here) and the characters come back as ``à¤­à¤¾à¤°à¤¤à¥€``.

    The ellipsis is the same hazard on its own: it is not in ``cp1252`` either.
    """
    _write_corrupt_pdf(laws_dir / "भारतीय संविधान.pdf")

    proc = _run_cli(laws_dir, index_dir)
    out = _decode(proc.stdout)

    assert proc.returncode == EXIT_DOCUMENT_FAILED
    failed_lines = [line for line in out.splitlines() if line.strip().startswith("FAILED")]
    assert len(failed_lines) == 1, f"expected one failure line, got {failed_lines}"
    assert "भारतीय संविधान.pdf" in failed_lines[0], (
        f"the filename is unreadable in the report: {failed_lines[0]!r}"
    )
    # Guard against a fix that merely changes one mangled form for another.
    assert "à¤" not in out, f"mojibake in stdout: {out!r}"
    # The bytes must actually be UTF-8, not merely decodable as such.
    assert proc.stdout.decode("utf-8"), "stdout is not valid UTF-8"


def test_printing_a_devanagari_filename_does_not_crash_the_run(
    laws_dir: Path, index_dir: Path
) -> None:
    """A console that genuinely cannot encode the name must not raise.

    With ``strict`` error handling the alternative to mojibake is a
    ``UnicodeEncodeError`` traceback printed *after* a run that actually
    succeeded — the worst of both. The run must complete and report normally.
    """
    _write_pdf(laws_dir / "भारतीय न्याय संहिता 2023.pdf", ["1. Short title. Sample statute text."])

    proc = _run_cli(laws_dir, index_dir)

    assert proc.returncode == EXIT_OK, _decode(proc.stderr)
    assert "Traceback" not in _decode(proc.stderr), _decode(proc.stderr)


def test_configure_streams_tolerates_a_stream_that_cannot_be_reconfigured() -> None:
    """Reporting a filename must never be the thing that raises.

    A test double or an unusual replacement stream may have no ``reconfigure``
    at all, or may refuse it. The helper is called on every run, so an
    unguarded attribute access would turn a cosmetic concern into a crash.
    """
    from scripts.ingest_laws import _configure_streams

    class NoReconfigure:
        def write(self, text: str) -> int:
            return len(text)

    original_out, original_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = NoReconfigure(), NoReconfigure()  # type: ignore[assignment]
    try:
        _configure_streams()  # must not raise
    finally:
        sys.stdout, sys.stderr = original_out, original_err


def test_configure_streams_installs_utf8_with_a_safe_fallback() -> None:
    """UTF-8 first, and an escape hatch that is still recoverable.

    ``backslashreplace`` is the last resort because it is lossy in a way an
    operator can undo: ``\\u092d\\u093e`` can be read back as a character,
    whereas mojibake cannot.
    """

    class FakeStream:
        def __init__(self) -> None:
            self.kwargs: dict[str, Any] = {}

        def reconfigure(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    from scripts.ingest_laws import _configure_streams

    fake_out, fake_err = FakeStream(), FakeStream()
    original_out, original_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = fake_out, fake_err  # type: ignore[assignment]
    try:
        _configure_streams()
    finally:
        sys.stdout, sys.stderr = original_out, original_err

    for stream in (fake_out, fake_err):
        assert stream.kwargs == {"encoding": "utf-8", "errors": "backslashreplace"}


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------


def test_a_missing_laws_directory_exits_two(
    tmp_path: Path, index_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["--laws-dir", str(tmp_path / "nope"), "--index-dir", str(index_dir)])

    assert rc == EXIT_NO_SOURCE
    assert "No laws directory" in capsys.readouterr().out


def test_a_corrupt_document_exits_one(laws_dir: Path, index_dir: Path) -> None:
    _write_corrupt_pdf(laws_dir / "Broken Act.pdf")

    assert main(["--laws-dir", str(laws_dir), "--index-dir", str(index_dir)]) == (
        EXIT_DOCUMENT_FAILED
    )


def test_a_dry_run_writes_nothing(
    laws_dir: Path, index_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_pdf(laws_dir / "Alpha Act.pdf", ["1. Short title. This is real statute text."])

    rc = main(["--laws-dir", str(laws_dir), "--index-dir", str(index_dir), "--dry-run"])

    assert rc == EXIT_OK
    assert "Dry run" in capsys.readouterr().out
    assert not index_dir.exists() or list(index_dir.iterdir()) == []


def test_an_unwritable_index_exits_four_with_no_traceback(
    laws_dir: Path, tmp_path: Path
) -> None:
    """A filesystem refusal must be reported, not raised.

    An unwritable index directory is an ordinary operational event. Letting it
    escape would print a traceback carrying absolute paths and OS error codes —
    the one thing this script promises never to do.
    """
    _write_pdf(laws_dir / "Alpha Act.pdf", ["1. Short title. Alpha."])
    index_is_a_file = tmp_path / "not_a_directory"
    index_is_a_file.write_text("I am a file.")

    proc = _run_cli(laws_dir, index_is_a_file)

    assert proc.returncode == EXIT_WRITE_FAILED, _decode(proc.stderr)
    assert "Traceback" not in _decode(proc.stderr), _decode(proc.stderr)
    assert "WinError" not in _decode(proc.stderr), _decode(proc.stderr)
    assert "left untouched" in _decode(proc.stdout)


def test_an_existing_index_is_never_replaced_with_an_empty_one(
    laws_dir: Path, index_dir: Path
) -> None:
    """A corpus that yields nothing must leave the working index alone.

    This is the accident an operator actually makes: they move or delete their
    PDFs, re-run, and come back to an emptied knowledge base.
    """
    _write_pdf(laws_dir / "Alpha Act.pdf", ["1. Short title. This is real statute text."])
    assert main(["--laws-dir", str(laws_dir), "--index-dir", str(index_dir)]) == EXIT_OK
    before = (index_dir / "chunks.json").read_bytes()

    (laws_dir / "Alpha Act.pdf").unlink()
    _write_corrupt_pdf(laws_dir / "Broken.pdf")

    assert main(["--laws-dir", str(laws_dir), "--index-dir", str(index_dir)]) == (
        EXIT_NOTHING_WRITTEN
    )
    assert (index_dir / "chunks.json").read_bytes() == before


def test_the_run_summary_never_prints_statute_text(
    laws_dir: Path, index_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The summary reports counts, never the contents of a statute."""
    _write_pdf(
        laws_dir / "Alpha Act.pdf",
        ["7001. UNIQUEVIOLATORSENTENCE sample filler that must never be echoed."],
    )

    main(["--laws-dir", str(laws_dir), "--index-dir", str(index_dir)])

    out = capsys.readouterr().out
    assert "UNIQUEVIOLATORSENTENCE" not in out, f"statute text leaked into the summary: {out!r}"
    assert "Documents ingested" in out
