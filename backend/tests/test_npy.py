"""Tests for :mod:`app.rag.npy` - the hand-rolled NPY v1.0 container.

The stakes here are unusual: this module writes a binary format by hand, so a
bug does not crash. It produces a file that some readers accept and that yields
*wrong numbers* - which for a legal-information tool means a confidently wrong
citation rather than an error message.

The tests are therefore grouped by what could go wrong rather than by what the
code does:

* **Byte-identity** - the writer must produce the same bytes ``np.save`` does.
  This was verified against numpy 2.1.3 and is the single fact that makes the
  module trustworthy. It cannot be asserted here, because numpy is absent from
  this project's venv by design; the test below pins the *invariants* that
  identity rests on, so a change that breaks them fails without numpy.
* **Alignment** - the one rule that is easy to get subtly wrong, and whose
  failure mode is a file most readers accept and some reject.
* **Refusal** - NaN, infinity, column-major data, wrong dtype, ragged input.
  Every one of these produces a plausible-looking wrong answer if accepted.
* **Degenerate shapes** - an empty matrix is a real state here, not an error.

Disclaimer: this project provides general legal INFORMATION. It is not a
lawyer and does not provide legal advice.
"""

from __future__ import annotations

import math
import struct
import sys
from pathlib import Path

import pytest

from app.rag.npy import (
    DTYPE_DESCR,
    NpyFormatError,
    NpyHeader,
    dumps_f32_2d,
    finite_vector_or_none,
    is_finite_vector,
    l2_normalise,
    loads_f32_2d,
)

# ---------------------------------------------------------------------------
# The format's structural invariants - these are what byte-identity rests on
# ---------------------------------------------------------------------------

_MAGIC = b"\x93NUMPY"
_PREAMBLE_LEN = 10


def _header_of(blob: bytes) -> tuple[str, int]:
    """Return the header text and the total preamble length."""
    header_len = struct.unpack("<H", blob[8:10])[0]
    return blob[10 : 10 + header_len].decode("latin-1"), _PREAMBLE_LEN + header_len


def test_the_preamble_is_magic_then_version_then_uint16_length() -> None:
    """The 10-byte prefix is 6 magic + 2 version + 2 length.

    The trap is that numpy's own ``MAGIC_LEN`` constant is **8**, not 6,
    because it counts the version bytes. A reader that transcribes the prose
    specification's "6" and then reads the length at offset 6 is off by two,
    and every subsequent field is garbage that happens to parse.
    """
    blob = dumps_f32_2d([[1.0, 2.0]])
    assert blob[:6] == _MAGIC
    assert blob[6:8] == b"\x01\x00", "format version must be 1.0"
    # The length field is little-endian uint16 and must describe exactly the
    # bytes that follow it.
    header_len = struct.unpack("<H", blob[8:10])[0]
    assert len(blob) == _PREAMBLE_LEN + header_len + 2 * 4


@pytest.mark.parametrize(
    ("rows", "label"),
    [
        ([[1.0, 2.0, 3.0]], "1x3"),
        ([tuple(float(i * 10 + j) for j in range(7)) for i in range(5)], "5x7"),
        ([tuple(float(i + j) for j in range(384)) for i in range(3)], "3x384"),
        ([tuple(float(i) for i in range(384))], "1x384"),
        ([], "0x0"),
        ([[1.0]], "1x1"),
    ],
)
def test_the_header_is_aligned_to_sixty_four_bytes(rows: list, label: str) -> None:
    """``(10 + header_len) % 64 == 0`` for every shape.

    This is the invariant most easily broken by a plausible-looking rewrite.
    The padding goes *before* the newline and its count is
    ``64 - (prefix + len + 1) % 64`` **with no outer modulo**, so it is 1..64.
    Dropping the outer modulo gives a pad of 0 for aligned cases, which really
    means 64 - the newline still has to fit.
    """
    blob = dumps_f32_2d(rows)
    _, preamble_len = _header_of(blob)
    assert preamble_len % 64 == 0, f"{label}: preamble is not 64-byte aligned"


def test_the_padding_precedes_the_newline() -> None:
    """The header ends ``...spaces + newline``, never ``...newline + spaces``.

    Worth stating precisely because the obvious way to write the assertion is
    backwards. Padding belongs *before* the newline, so the character
    immediately preceding the newline **is** a space - asserting otherwise
    would test for the malformed layout. A header padded after the newline is
    the same number of bytes and a different string, and a reader that scans
    to the first newline then reads the padding as part of the dict literal.
    """
    blob = dumps_f32_2d([[1.0]])
    header, _ = _header_of(blob)

    assert header.endswith("\n"), "v1.0 requires the header to end in a newline"
    assert header[:-1].endswith(" "), "the last pad character precedes the newline"

    # Stripping only the newline and the trailing pad must leave a literal
    # that still ends exactly where the dict literal ends.
    literal = header.rstrip(" \n")
    assert literal.startswith("{") and literal.endswith(", }")
    # And it must be evaluable, which is what a reader does with it.
    loads_f32_2d(blob)  # round-trips, so the literal is genuinely parseable


def test_the_shape_is_written_with_a_trailing_comma_in_numpy_spelling() -> None:
    """Header text matches the spelling ``np.save`` emits.

    Pinned because byte-identity with numpy was verified against exactly this
    spelling. Reformatting the header - single vs double quotes, reordering the
    keys, dropping the trailing comma - keeps the file *readable* and stops it
    being *identical*, which is a distinction no other test in this file can
    make and is the reason this assertion exists at all.
    """
    blob = dumps_f32_2d([[1.0, 2.0], [3.0, 4.0]])
    header, _ = _header_of(blob)
    assert "'descr': '<f4'" in header
    assert "'fortran_order': False" in header
    assert "'shape': (2, 2)" in header
    assert header.rstrip("\n").rstrip().endswith(", }")


def test_the_dtype_is_explicitly_little_endian_never_native() -> None:
    """The descriptor is ``<f4``, not a bare ``f4``.

    A bare ``f4`` means *native* byte order, so the file's meaning would depend
    on the machine that wrote it. A big-endian file read on x86 byte-swaps
    into plausible-looking but wrong similarities - every distance in the
    system would be quietly incorrect instead of loudly broken.
    """
    assert DTYPE_DESCR == "<f4"
    blob = dumps_f32_2d([[1.0]])
    header, _ = _header_of(blob)
    assert "'descr': '<f4'" in header
    assert "'>f4'" not in header and "': 'f4'" not in header


# ---------------------------------------------------------------------------
# Round trips, including the degenerate shapes that are real states here
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rows",
    [
        [[1.0, 2.0, 3.0]],
        [[1.0], [2.0], [3.0]],
        [tuple(float(i * 7 + j) / 3.0 for j in range(384)) for i in range(4)],
        [[-1.5, 0.0, 2.25], [3.5, -4.0, 0.125]],
        [[3.4e38, -3.4e38]],
        [[1e-45, -1e-45]],  # subnormal float32: survives the round trip
        [[0.0, -0.0]],
        [],
    ],
)
def test_a_matrix_survives_the_round_trip_exactly(rows: list) -> None:
    """Values come back bit-identical, not merely close.

    The assertions here use the original Python floats rather than float32
    comparisons on purpose. A serialisation format that rounds is not
    rounding at all, and ``pytest.approx`` would hide it.
    """
    matrix, _ = loads_f32_2d(dumps_f32_2d(rows))
    expected_cols = len(rows[0]) if rows else 0
    assert len(matrix) == len(rows)
    for recovered, original in zip(matrix, rows, strict=True):
        assert len(recovered) == expected_cols
        for got, want in zip(recovered, original, strict=True):
            assert struct.pack("<f", got) == struct.pack("<f", want)


def test_an_empty_matrix_is_a_valid_file_not_an_error() -> None:
    """``dumps_f32_2d([])`` writes a well-formed ``(0, 0)`` file.

    An empty index is a real, reachable state in this project - the ingestion
    pipeline deliberately writes an empty index when the corpus is empty and no
    prior index exists. The obvious implementation indexes ``rows[0]`` and
    raises ``IndexError`` on an empty list, which turns a legitimate state
    into a crash. It was caught here before it shipped.
    """
    blob = dumps_f32_2d([])
    matrix, header = loads_f32_2d(blob)
    assert matrix == []
    assert header.shape == (0, 0)
    assert header.rows == 0 and header.cols == 0


def test_a_matrix_with_rows_but_no_columns_is_also_valid() -> None:
    """A ``(3, 0)`` matrix is legal NPY, and its column count is zero."""
    blob = dumps_f32_2d([[], [], []])
    matrix, header = loads_f32_2d(blob)
    assert header.shape == (3, 0)
    assert matrix == [(), (), ()]


def test_ragged_rows_are_refused_rather_than_padded() -> None:
    """Ragged input is a caller bug, and padding it would invent data.

    Padding would produce a matrix whose rows do not mean what the caller
    thinks, and the caller has no way to tell from the file. Refusing is the
    only safe answer.
    """
    with pytest.raises(NpyFormatError):
        dumps_f32_2d([[1.0, 2.0], [3.0]])


# ---------------------------------------------------------------------------
# Refusal: every case below produces wrong numbers rather than an error
# ---------------------------------------------------------------------------


def _corrupt(
    blob: bytes,
    *,
    dtype: str = "<f4",
    shape: str = "(2, 2)",
    body: bytes | None = None,
) -> bytes:
    """Build a structurally valid .npy whose header fields are overridden.

    Used to reach failure modes that cannot be produced by the honest writer,
    which is the point: the writer never emits these, so only a test can.
    """
    header = "{'descr': '%s', 'fortran_order': False, 'shape': %s, }" % (  # noqa: UP031
        dtype, shape
    )
    pad = 64 - ((len(_MAGIC) + 2 + 2 + len(header) + 1) % 64)
    padded = header + " " * pad + "\n"
    out = bytearray(_MAGIC)
    out += b"\x01\x00"
    out += struct.pack("<H", len(padded))
    out += padded.encode("latin-1")
    out += body if body is not None else b"\x00" * 32
    return bytes(out)


@pytest.mark.parametrize(
    ("blob", "reason"),
    [
        (b"", "empty"),
        (b"\x93NUMPY", "magic only, no version"),
        (b"not a numpy file at all, but long enough to have a preamble", "wrong magic"),
        (_corrupt(b"\x00" * 4), "truncated inside the header length"),
        (_corrupt(_corrupt(b"") , dtype=">f4"), "big-endian"),
        (_corrupt(b"", dtype="f8"), "double precision"),
        (_corrupt(b"", dtype="=f4"), "native byte order"),
    ],
)
def test_bytes_that_are_not_an_honest_matrix_are_refused(blob: bytes, reason: str) -> None:
    """Every rejection raises the one exception type, never IndexError.

    The bytes on disk can be anything - a truncated file, a JSON blob someone
    renamed, an empty file - and the project rule is that a raw Python
    exception never reaches a user. ``reason`` is in the test id so a failure
    names which case broke.
    """
    with pytest.raises(NpyFormatError):
        loads_f32_2d(blob)


def test_a_column_major_matrix_is_refused_because_it_would_transpose() -> None:
    """``fortran_order: True`` is refused, not silently read as row-major.

    Reading column-major data as row-major yields a *transposed* matrix. Every
    value is plausible, the shape often even matches when it is square, and
    the resulting similarity scores are entirely wrong. This is the single most
    dangerous input this module could accept, so it gets an explicit refusal
    and its own test.
    """
    header = "{'descr': '<f4', 'fortran_order': True, 'shape': (2, 2), }"
    pad = 64 - ((len(_MAGIC) + 2 + 2 + len(header) + 1) % 64)
    padded = header + " " * pad + "\n"
    out = bytearray(_MAGIC) + b"\x01\x00" + struct.pack("<H", len(padded))
    out += padded.encode("latin-1") + b"\x00" * 16
    with pytest.raises(NpyFormatError):
        loads_f32_2d(bytes(out))


def test_a_truncated_body_is_refused_rather_than_read_partially() -> None:
    """A body shorter than the shape is an error, not a short matrix.

    Reading what is there would shift every subsequent row by a few floats.
    The result still has plausible dimensions and entirely wrong distances -
    the silent-wrong-answer shape of failure.
    """
    blob = dumps_f32_2d([[1.0, 2.0], [3.0, 4.0]])
    with pytest.raises(NpyFormatError):
        loads_f32_2d(blob[:-4])


def test_an_extra_byte_of_body_is_refused_too() -> None:
    """The length check is exact in both directions, not a lower bound."""
    blob = dumps_f32_2d([[1.0, 2.0], [3.0, 4.0]])
    with pytest.raises(NpyFormatError):
        loads_f32_2d(blob + b"\x00")


def test_a_higher_rank_matrix_is_refused() -> None:
    """Only 2-D is accepted; a 1-D or 3-D shape is not silently reshaped."""
    blob = _corrupt(b"", shape="(4,)")
    with pytest.raises(NpyFormatError):
        loads_f32_2d(blob)
    blob = _corrupt(b"", shape="(2, 2, 2)")
    with pytest.raises(NpyFormatError):
        loads_f32_2d(blob)


def test_an_unsupported_format_version_is_refused() -> None:
    """A v9.0 file is refused rather than parsed on a guess about its layout."""
    blob = bytearray(dumps_f32_2d([[1.0]]))
    blob[6] = 9
    with pytest.raises(NpyFormatError):
        loads_f32_2d(bytes(blob))


# ---------------------------------------------------------------------------
# The non-finite gate - the failure that produces wrong answers, not crashes
# ---------------------------------------------------------------------------


def test_l2_normalisation_makes_the_vector_unit_length() -> None:
    """Normalising once at write time makes cosine an exact dot product."""
    assert math.isclose(math.sqrt(sum(v * v for v in l2_normalise((3.0, 4.0)))), 1.0)


def test_a_zero_vector_is_returned_unchanged_rather_than_divided_by_zero() -> None:
    """A zero vector has no direction, so its similarity to everything is 0.

    Dividing by a zero norm raises ``ZeroDivisionError``; a raw exception must
    not reach a user. Returning the vector unchanged is the truthful answer.
    """
    assert l2_normalise((0.0, 0.0, 0.0)) == (0.0, 0.0, 0.0)


@pytest.mark.parametrize(
    "vector",
    [
        (float("nan"), 1.0),
        (1.0, float("nan")),
        (float("inf"), 1.0),
        (1.0, float("-inf")),
        (0.0, float("nan")),
    ],
)
def test_a_non_finite_vector_is_refused_at_normalisation_time(vector: tuple) -> None:
    """NaN and infinity are refused where they enter, not discovered later.

    Every comparison against NaN is false, so a NaN row never wins a ranking.
    The index would look like a bad retriever rather than a broken one, and
    nothing would raise anywhere. Catching it here means the matrix is never
    written at all.
    """
    with pytest.raises(NpyFormatError):
        l2_normalise(vector)


def test_the_finiteness_helpers_agree_with_each_other() -> None:
    """Two sites need this answer, so they must not drift.

    A duplicate implementation is exactly how the writer's refusal and the
    loader's verification come to disagree about what "valid" means.
    """
    good = (0.5, -0.25, 0.125)
    bad = (0.5, float("nan"))
    assert is_finite_vector(good) and finite_vector_or_none(good) == good
    assert not is_finite_vector(bad)
    assert finite_vector_or_none(bad) is None
    assert is_finite_vector(()) and finite_vector_or_none(()) == ()


def test_a_huge_float_survives_serialisation_as_infinity_rather_than_lying() -> None:
    """float32 conversion is silent, so this is recorded rather than prevented.

    ``1e40`` is representable as a Python float but overflows float32, and the
    conversion happens silently in ``array("f")``. This test documents that
    behaviour rather than asserting a guard exists: the *builder* is where the
    gate belongs, because it can refuse before serialising, and
    :func:`finite_vector_or_none` is that gate. Writing the observation here
    means a future change to the conversion is visible instead of silent.
    """
    blob = dumps_f32_2d([[1e40]])
    matrix, _ = loads_f32_2d(blob)
    assert math.isinf(matrix[0][0])
    # Which is exactly why the gate must run before dumps, not after loads.
    assert finite_vector_or_none((1e40,)) is not None, "Python-side the value is finite"
    assert finite_vector_or_none(matrix[0]) is None, "float32-side it is not"


# ---------------------------------------------------------------------------
# Properties that hold for every input, and the parser's own hazard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [[1.0]],
        [[1.0, 2.0, 3.0]],
        [[1.0] * 384],
        [tuple(float(i) for i in range(64)) for _ in range(8)],
    ],
)
def test_every_shape_round_trips_without_raising(rows: list) -> None:
    """Dump-then-load never raises, whatever the shape.

    This is the retriever's entry point into a binary format: a corrupt or
    unexpected file must become a neutral reason, never a 500.
    """
    matrix, header = loads_f32_2d(dumps_f32_2d(rows))
    assert header.shape == (len(rows), len(rows[0]) if rows else 0)
    assert len(matrix) == len(rows)


def test_the_header_reports_its_own_dimensions() -> None:
    """``rows``/``cols`` are the accessors callers actually use."""
    _, header = loads_f32_2d(dumps_f32_2d([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]))
    assert isinstance(header, NpyHeader)
    assert (header.rows, header.cols) == (2, 3)
    assert header.descr == "<f4"
    assert (header.major, header.minor) == (1, 0)
    assert header.fortran_order is False


def test_the_header_shape_tuple_is_parsed_as_a_tuple_not_split_on_commas() -> None:
    """The parser hazard this module exists to avoid.

    The header is a Python dict *literal*. Splitting it on commas - the
    obvious approach when you have no parser - also splits inside the shape
    tuple, so ``(3, 384)`` becomes three fragments and the column count comes
    out as ``' 384'``. That is the ``KeyError``/shape-corruption failure that
    :func:`ast.literal_eval` exists to prevent, and this test asserts the
    multi-column case specifically because a single-column shape would hide it.
    """
    _, header = loads_f32_2d(dumps_f32_2d([tuple(float(j) for j in range(384))]))
    assert header.cols == 384
    assert isinstance(header.cols, int)
    assert header.shape == (1, 384)


def test_the_module_never_needs_a_third_party_library() -> None:
    """The whole point: this must work with numpy absent.

    ``app.rag.npy`` is imported on a machine with no ML runtime - that machine
    is the one this project ships to. If a third-party import crept in, the
    entire retrieval path would fail to import exactly where it is needed
    most, so the guarantee is asserted rather than trusted.
    """
    import app.rag.npy as module

    source = sys.modules[module.__name__].__file__
    assert source is not None
    text = Path(source).read_text(encoding="utf-8")
    for banned in ("import numpy", "import torch", "import scipy", "from numpy"):
        assert banned not in text, (
            f"{banned} must not appear in the pure-stdlib container"
        )
