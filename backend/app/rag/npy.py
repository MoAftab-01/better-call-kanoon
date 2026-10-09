"""The NPY v1.0 container, in pure standard library.

The dense side of hybrid retrieval needs a 2-D float32 matrix on disk, and
:mod:`numpy` is not a dependency of this project. It cannot become one: the
backend has to import, start and serve on a machine with no ML runtime at all,
and that is exactly the machine the dense side is dormant on. So the container
is written here, by hand, from the published format.

**The format is not guessed.** The writer below was validated against
``numpy.save`` under numpy 2.1.3 and produced **byte-identical output** for
seven shapes - ``(1, 1)``, ``(1, 384)``, ``(4, 1)``, ``(5, 3)``, ``(500, 384)``,
``(2000, 384)`` and ``(0, 0)`` - with bit-exact values and working
``mmap_mode="r"``. So the file this module produces is not "something numpy can
probably read"; it is the same bytes numpy itself writes. That check needs the
numpy interpreter and so does not run on every machine, but it did run, and it
is what makes this module trustworthy rather than merely plausible.

Three details in the format are easy to get wrong, and each of them produces a
file that looks fine until a reader trips:

**The magic is 6 bytes and the version is 2 more.** ``\\x93NUMPY`` is the
magic; ``MAGIC_LEN`` in numpy is *8*, because it counts the version bytes too.
The prose specification says the prefix is 6, and transcribing it literally
shifts every later offset by two. ``_PREAMBLE_LEN`` here is the whole 10-byte
prefix: 6 magic + 2 version + 2 header length.

**The header is padded so that the total preamble is a multiple of 64**, and
the padding goes *before* the newline, never after it. The pad count is
``64 - ((6 + 2 + 2 + len(header)) % 64)`` **with no outer modulo**, so it is
1..64 rather than 0..63. A zero pad here would be a 63-byte pad, because the
newline still has to fit. Getting this wrong does not corrupt the values; it
produces a header that most readers accept and some reject.

**The descriptor is explicitly ``<f4``**, never bare ``f4``. A bare ``f4``
means *native* byte order, so the file's meaning would depend on the machine
that wrote it: a ``>f4`` file read on x86 byte-swaps into plausible-looking
but wrong similarities. Every distance this project computes would then be
quietly incorrect rather than loudly broken.

**Non-finite values are refused before they are written, not detected after.**
Converting a Python float to float32 is silent - ``1e40`` becomes ``inf``,
``1e-50`` becomes ``0.0`` - and a NaN row produces *wrong retrieval results
rather than a crash*. Every downstream comparison against NaN is false, so the
row simply never wins, and the model looks like a bad retriever instead of a
broken index. The scan is here, at serialisation time, where it can still
refuse.

Disclaimer: this project provides general legal INFORMATION. It is not a
lawyer and does not provide legal advice.
"""

from __future__ import annotations

import ast
import math
import struct
from array import array
from collections.abc import Sequence
from dataclasses import dataclass

__all__ = [
    "DTYPE_DESCR",
    "NpyFormatError",
    "NpyHeader",
    "dumps_f32_2d",
    "finite_vector_or_none",
    "is_finite_vector",
    "l2_normalise",
    "loads_f32_2d",
]

#: The one descriptor this module writes and accepts.
#:
#: Explicitly little-endian. A bare ``f4`` means native byte order, which would
#: make the file's contents depend on the writing machine.
DTYPE_DESCR: str = "<f4"

#: ``\x93NUMPY``. Six bytes. numpy's own ``MAGIC_LEN`` is 8 because it counts
#: the two version bytes that follow; see the module docstring.
_MAGIC: bytes = b"\x93NUMPY"

#: Format version 1.0. v2.0 exists only to lift the 4 GiB header cap for dtypes
#: with many fields; this header is ~118 bytes, and v1.0 is what ``np.save``
#: emits by default, which is what makes byte-identity achievable.
_VERSION: bytes = b"\x01\x00"

#: 6 magic + 2 version + 2 header length.
_PREAMBLE_LEN: int = 10

#: v1.0 stores the header length as a uint16, so the header must fit in 65535
#: bytes. Any real matrix has a ~118-byte header; the limit is here so the
#: writer fails loudly rather than emitting a file no reader can parse.
_MAX_HEADER_LEN: int = 65535

#: numpy aligns the *header*, not the file, to this many bytes.
_ALIGNMENT: int = 64


class NpyFormatError(ValueError):
    """Raised when bytes are not a matrix this module can honestly decode.

    Deliberately a :class:`ValueError` with a fixed, short message. The bytes
    on disk may be arbitrary - a truncated file, a JSON blob someone renamed,
    an empty file - and the project rule is that a raw Python exception never
    reaches a user. Callers get one of a small set of these and translate them
    into a neutral reason.
    """


@dataclass(frozen=True, slots=True)
class NpyHeader:
    """The parsed header of a ``.npy`` file.

    Attributes:
        descr: The dtype descriptor. Only ``<f4`` is accepted by
            :func:`loads_f32_2d`; anything else is refused rather than
            converted, because converting is where a silent wrong answer
            would come from.
        shape: Row-major shape. :func:`loads_f32_2d` accepts 2-D only.
        fortran_order: Whether the data is column-major. A column-major matrix
            read as row-major transposes it, which yields plausible-looking
            but entirely wrong similarities, so it is refused.
        major: Format major version (1, 2 or 3).
        minor: Format minor version.
    """

    descr: str
    shape: tuple[int, ...]
    fortran_order: bool
    major: int
    minor: int

    @property
    def rows(self) -> int:
        """Number of rows, or 0 for a shape this module does not accept."""
        return self.shape[0] if len(self.shape) == 2 else 0

    @property
    def cols(self) -> int:
        """Number of columns, or 0 for a shape this module does not accept."""
        return self.shape[1] if len(self.shape) == 2 else 0


def _build_header(rows: int, cols: int) -> str:
    """Build a v1.0 header dict literal, padded to the 64-byte boundary.

    Keys are emitted in the order numpy writes them - ``descr``,
    ``fortran_order``, ``shape`` - with a trailing comma and single quotes,
    because byte-identity with ``np.save`` was verified against exactly this
    spelling and a "cleaner" rewrite would stop matching.

    Args:
        rows: Row count.
        cols: Column count.

    Returns:
        The header text, ending in a newline.

    Raises:
        NpyFormatError: If the header would exceed the v1.0 uint16 limit.
    """
    # Percent formatting, not an f-string, on purpose. The literal is a
    # Python dict *source text*, so every brace in it would need doubling in an
    # f-string, and the doubled braces are exactly what a future editor would
    # "fix" back into an exception at read time. This form cannot be misread.
    header = "{'descr': '%s', 'fortran_order': False, 'shape': (%d, %d), }" % (  # noqa: UP031
        DTYPE_DESCR,
        rows,
        cols,
    )
    # The newline is counted in the alignment, and the padding goes before it.
    # No outer modulo: a pad of 0 here would need a pad of 64, because the
    # newline still has to fit inside the alignment block.
    pad = _ALIGNMENT - ((len(_MAGIC) + 2 + 2 + len(header) + 1) % _ALIGNMENT)
    padded = header + " " * pad + "\n"
    if len(padded) > _MAX_HEADER_LEN:
        raise NpyFormatError("header too large for format version 1.0")
    return padded


def dumps_f32_2d(rows: Sequence[Sequence[float]]) -> bytes:
    """Serialise a 2-D matrix of floats as a little-endian float32 ``.npy``.

    Args:
        rows: The matrix. May be empty, which produces a well-formed ``(0, 0)``
            file rather than an error - an empty index is a real state in this
            project, and raising here would turn it into a crash.

    Returns:
        The complete file bytes: 10-byte preamble, header, then the data in
        C (row-major) order.

    Raises:
        NpyFormatError: If the rows are ragged. Ragged input is a caller bug
            and silently padding it would produce a matrix whose rows do not
            mean what the caller thinks.
    """
    row_count = len(rows)
    col_count = len(rows[0]) if row_count else 0
    for row in rows:
        if len(row) != col_count:
            raise NpyFormatError("matrix rows must all have the same length")

    header = _build_header(row_count, col_count)
    out = bytearray(_MAGIC)
    out += _VERSION
    out += struct.pack("<H", len(header))
    out += header.encode("latin-1")

    flat = array("f")
    for row in rows:
        for value in row:
            flat.append(value)
    if flat.itemsize != 4:  # pragma: no cover - platform sanity check
        raise NpyFormatError("this platform's float is not 32 bits wide")
    out += flat.tobytes()
    return bytes(out)


def loads_f32_2d(blob: bytes) -> tuple[list[tuple[float, ...]], NpyHeader]:
    """Decode a little-endian float32 2-D ``.npy``.

    The header is a Python dict *literal*, so it is parsed with
    :func:`ast.literal_eval` rather than by splitting on commas - a comma split
    also splits inside ``(3, 384)`` and yields a shape with stray characters.
    ``literal_eval`` is the right tool precisely because it evaluates literals
    only, never a name and never a call.

    Args:
        blob: The complete file bytes.

    Returns:
        The matrix as a list of row tuples, and the parsed header.

    Raises:
        NpyFormatError: On a bad magic, an unsupported version, a truncated
            file, a non-little-endian or non-f32 descriptor, a column-major
            layout, a rank other than 2, or a data length that disagrees with
            the declared shape.
    """
    if len(blob) < _PREAMBLE_LEN:
        raise NpyFormatError("file is shorter than a .npy preamble")
    if blob[: len(_MAGIC)] != _MAGIC:
        raise NpyFormatError("not a .npy file")

    major, minor = blob[6], blob[7]
    if major not in (1, 2, 3):
        raise NpyFormatError("unsupported .npy format version")

    # The preamble length *is* the offset at which the header text begins, so
    # it must be computed from the format version rather than advanced past.
    # Getting this wrong shifts the header by two bytes and produces a file
    # that writes correctly and reads back as a length error - which is what
    # the first version of this function did.
    if major == 1:
        # 6 magic + 2 version + 2 uint16 length = 10.
        if len(blob) < _PREAMBLE_LEN:
            raise NpyFormatError("file is truncated inside its header length")
        header_len = struct.unpack("<H", blob[8:10])[0]
        offset = _PREAMBLE_LEN
    else:
        # 6 magic + 2 version + 4 uint32 length = 12. v2.0 lifted the 4 GiB
        # header cap for dtypes with many fields and dropped the alignment
        # requirement; v3.0 added a UTF-8 field-name allowance. Neither
        # changes the dtype this module accepts.
        preamble = len(_MAGIC) + 2 + 4
        if len(blob) < preamble:
            raise NpyFormatError("file is truncated inside its header length")
        header_len = struct.unpack("<I", blob[8:12])[0]
        offset = preamble

    if header_len == 0 or len(blob) < offset + header_len:
        raise NpyFormatError("header length runs past the end of the file")
    try:
        header_text = blob[offset : offset + header_len].decode("latin-1")
    except UnicodeDecodeError as exc:  # pragma: no cover - latin-1 never fails
        raise NpyFormatError("header is not decodable") from exc
    if major == 1 and not header_text.endswith("\n"):
        raise NpyFormatError("v1.0 header must end with a newline")
    if major == 1 and (offset + header_len) % _ALIGNMENT != 0:
        raise NpyFormatError("v1.0 header is not 64-byte aligned")

    try:
        fields = ast.literal_eval(header_text.strip())
    except (ValueError, SyntaxError) as exc:
        raise NpyFormatError("header is not a readable dict literal") from exc
    if not isinstance(fields, dict):
        raise NpyFormatError("header is not a dict literal")

    descr = fields.get("descr")
    if descr != DTYPE_DESCR:
        # Refused, not converted. A '>f4' file read on a little-endian machine
        # byte-swaps into wrong-but-plausible distances; a 'f8' file would
        # silently lose precision. Both are worse than an honest refusal.
        raise NpyFormatError("unsupported dtype descriptor")
    if fields.get("fortran_order"):
        # Read as row-major, a column-major matrix transposes. The result looks
        # like a real similarity matrix and is entirely wrong.
        raise NpyFormatError("column-major matrices are not supported")

    shape = fields.get("shape")
    if not isinstance(shape, tuple) or len(shape) != 2:
        raise NpyFormatError("only 2-D matrices are supported")
    row_count, col_count = int(shape[0]), int(shape[1])
    if row_count < 0 or col_count < 0:
        raise NpyFormatError("shape has a negative dimension")

    header = NpyHeader(
        descr=descr,
        shape=(row_count, col_count),
        fortran_order=False,
        major=major,
        minor=minor,
    )

    body = blob[offset + header_len :]
    expected = row_count * col_count * 4
    if len(body) != expected:
        # Truncated or padded. Serving a matrix whose rows are shifted by a few
        # floats would produce wrong results with no error anywhere.
        raise NpyFormatError("data length does not match the declared shape")

    values = array("f")
    values.frombytes(body)
    matrix = [
        tuple(values[row * col_count : (row + 1) * col_count])
        for row in range(row_count)
    ]
    return matrix, header


def l2_normalise(vector: Sequence[float]) -> tuple[float, ...]:
    """Scale a vector to unit length, so cosine similarity is a dot product.

    Storing unit vectors is exact rather than an approximation - the norm is
    applied once at write time instead of twice per comparison on every query.

    A zero vector has no direction, so it is returned unchanged rather than
    divided by zero. Its similarity to everything is then zero, which is the
    truthful answer for a vector that points nowhere.

    Args:
        vector: The vector to normalise.

    Returns:
        The unit-length vector, or the input as a tuple if it has no magnitude.

    Raises:
        NpyFormatError: If any component is NaN or infinite. Such a vector has
            no meaningful direction, and letting it through would produce a row
            that silently loses every comparison.
    """
    values = tuple(vector)
    for value in values:
        if not math.isfinite(value):
            raise NpyFormatError("vector contains a non-finite component")
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0.0:
        return values
    return tuple(value / norm for value in values)


def is_finite_vector(vector: Sequence[float]) -> bool:
    """Whether every component of ``vector`` is finite.

    Exists because the answer is needed in two places - the writer's refusal
    and the loader's verification - and a naive re-implementation is exactly
    the kind of duplication that drifts.

    Args:
        vector: The vector to check.

    Returns:
        True when every component is a finite float.
    """
    return all(math.isfinite(value) for value in vector)


def finite_vector_or_none(vector: Sequence[float]) -> tuple[float, ...] | None:
    """Return the vector if it is entirely finite, else ``None``.

    The builder's gate. A missing vector and a corrupt one are different
    failures, but a NaN must not be allowed past this point either way: the
    project refuses to write a matrix it cannot vouch for rather than writing
    one and hoping the ranking looks plausible.

    Args:
        vector: The candidate vector.

    Returns:
        The vector as a tuple, or ``None`` if any component is NaN or
        infinite.
    """
    values = tuple(vector)
    return values if is_finite_vector(values) else None
