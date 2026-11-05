"""MP-E12a instrument 1 (v1.2 B.6 item 2): the read-only address space over the donor's weights.

WHAT THIS IS. A memory-mapped view of experiments/MP-E12/donor/gpt2/model.safetensors with per-tensor index
resolution taken from the file's own header, addressable by (tensor, row, column), returning raw float32
values. Nothing in this module runs the donor: no forward pass, no attention over a sequence, no sampling, no
generated text, no model class. It imports the standard library only -- no torch, no transformers, no numpy --
and `tests/test_mp_e12_address_space.py::test_no_donor_runtime_on_the_address_path` asserts exactly that,
naming the assertion, because plan condition C4 audits the deployment path for donor runtime and the check
should exist before the temptation does.

WHY THE HEADER IS THE ONLY AUTHORITY. The tensor table, the shapes and the byte ranges come from the JSON
index the file carries; the pinned spec in the registration is a claim about the file, and this instrument is
how that claim is checked rather than repeated.

THE GATHER LOOSENESS THIS FILE REFUSES TO EXPLOIT. Under the registered counting rule (MP-E12's C3 block: one
operation = one vector-by-donor-matrix multiply or one similarity search; a gather of already-read rows is not
an operation), reading the entire embedding matrix as raw rows spends ZERO operations. That is true and it is a
hole: a probe could pull 38.6 million floats for free. So the address space enforces its own byte-and-row
budget -- MAX_ROWS_PER_READ and MAX_READS_PER_PROBE -- and raises GatherBudgetExceeded when a caller asks for
more, while the loophole itself is registered in MP-E12's ledger rather than left for a reader to discover.

EVERY READ IS JOURNALED. There is no read path that bypasses the journal: `read_scalar`, `read_row` and
`read_rows` all go through `_commit`, and a construction without a journal raises. R11 says every access is
journaled; making the un-journaled path impossible is stronger than remembering to log.
"""
from __future__ import annotations

import hashlib
import json
import mmap
import re
import struct
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DONOR_FILE = "experiments/MP-E12/donor/gpt2/model.safetensors"
ADDRESS_SPACE_VERSION = "droso.donor_address_space.v1"

# the 12 causal-mask buffers, named by pattern. They are NOT weights: constant by construction, one triangle
# per layer, 1,048,576 floats each. Exclusion is enforced here and registered in MP-E12's ledger.
MASK_BUFFER_PATTERN = re.compile(r"^h\.\d+\.attn\.bias$")
MAX_ROWS_PER_READ = 64            # registered; a row of wte is 768 floats, so 64 rows is 49,152 floats
MAX_READS_PER_PROBE = 256         # registered; bounds what one probe can pull even at zero charged ops
MAX_VECTOR_VALUES = 4096          # registered; the largest 1-D tensor here is c_attn.bias at 2304, so this
                                  # admits every real vector and refuses a whole-tensor dump of something big
DTYPE_CODE = {"F32": ("f", 4), "F64": ("d", 8), "BF16": None, "F16": ("e", 2),
              "I8": ("b", 1), "I32": ("i", 4), "I64": ("q", 8), "U8": ("B", 1)}


class UnknownTensor(KeyError):
    """Asking for a tensor the file's index does not contain."""


class IndexOutOfRange(IndexError):
    """A row or column outside the tensor's recorded shape, or a negative index. Negative is refused rather
    than wrapped: Python's `[-1]` convenience would let a probe read the last row while the journal says the
    address was -1, and an address that is not a position in the file is not an address."""


class ExcludedTensor(PermissionError):
    """A read aimed at a registered non-weight buffer. Refused before the byte range is computed."""


class GatherBudgetExceeded(RuntimeError):
    """More rows or more reads than the registered gather budget. See the module docstring: without this the
    rule 'a gather is not an operation' makes bulk reads free."""


class GatherNotPermitted(PermissionError):
    """The address space was constructed without a journal, so its reads could not be journaled."""


class DonorAddressSpace:
    """Read-only, index-resolved access to one donor file. Opens the file once, mmaps it, parses the header,
    and answers (tensor, row, column) queries against the mapped bytes."""

    def __init__(self, path: str = DONOR_FILE, journal=None, root: Path = ROOT):
        self.root = Path(root)
        self.rel_path = path
        self.abs_path = self.root / path
        if not self.abs_path.exists():
            raise FileNotFoundError(f"donor file absent: {self.rel_path}")
        if journal is None:
            raise GatherNotPermitted(
                "the address space requires a journal: R11 says every access is journaled, so there is no "
                "un-journaled read path to fall back on")
        self.journal = journal
        self.header_len, self.table, self.metadata = self._parse_header()
        self.data_base = 8 + self.header_len
        self.n_reads = 0
        self.rows_read = 0
        self.bytes_read = 0
        self._fh = open(self.abs_path, "rb")
        self._mm = mmap.mmap(self._fh.fileno(), 0, access=mmap.ACCESS_READ)

    # ------------------------------------------------------------------ header
    def _parse_header(self):
        with self.abs_path.open("rb") as f:
            raw_len = f.read(8)
            (n,) = struct.unpack("<Q", raw_len)
            hdr = json.loads(f.read(n).decode("utf-8"))
        meta = hdr.pop("__metadata__", None)
        table = {k: {"shape": list(v["shape"]), "dtype": v["dtype"],
                     "offsets": list(v["data_offsets"])} for k, v in hdr.items()}
        return n, table, meta

    def sha256_of_file(self) -> str:
        """Hash the file THIS instance has open, not the module default. The distinction matters: a fixture
        donor built in tmp_path must hash itself, and an artifact that cites a donor hash has to mean the bytes
        it actually read. Cached, because hashing 548 MB twice in one run buys nothing."""
        if not hasattr(self, "_sha"):
            h = hashlib.sha256()
            with self.abs_path.open("rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            self._sha = h.hexdigest()
        return self._sha

    def tensor_names(self):
        return sorted(self.table)

    def shape(self, tensor: str):
        return list(self.table[tensor]["shape"])

    def dtype(self, tensor: str):
        return self.table[tensor]["dtype"]

    def is_excluded(self, tensor: str) -> bool:
        return bool(MASK_BUFFER_PATTERN.match(tensor))

    def excluded_tensors(self):
        return sorted(k for k in self.table if self.is_excluded(k))

    def byte_accounting(self) -> dict:
        """header length prefix + header JSON + the union of tensor byte ranges = the file size."""
        data_end = max(v["offsets"][1] for v in self.table.values())
        data_start = min(v["offsets"][0] for v in self.table.values())
        total = self.abs_path.stat().st_size
        return {"file_bytes": total, "length_prefix_bytes": 8, "header_json_bytes": self.header_len,
                "data_base": self.data_base, "tensor_data_bytes": data_end - data_start,
                "data_end": data_end, "sum_of_parts": 8 + self.header_len + (data_end - data_start),
                "closes": total == 8 + self.header_len + (data_end - data_start),
                "gaps_between_tensors": self._gaps(), "n_tensors": len(self.table)}

    def _gaps(self):
        """Contiguity of the data region: the header's offsets should tile without holes."""
        spans = sorted((v["offsets"][0], v["offsets"][1]) for v in self.table.values())
        gaps = []
        for (a0, a1), (b0, b1) in zip(spans, spans[1:]):
            if b0 != a1:
                gaps.append({"after_end": a1, "next_start": b0, "delta_bytes": b0 - a1})
        return gaps

    # ------------------------------------------------------------------ resolution
    def _resolve(self, tensor: str, row: int, col=None):
        if tensor not in self.table:
            raise UnknownTensor(f"{tensor!r} is not in the donor index "
                                f"(160 tensors; e.g. wte.weight, h.0.attn.c_attn.weight)")
        if self.is_excluded(tensor):
            raise ExcludedTensor(f"{tensor!r} is a registered non-weight buffer (causal mask), excluded from "
                                 f"every extraction class -- see MP-E12 registration, mask_buffer_exclusion")
        spec = self.table[tensor]
        shape, dtype = spec["shape"], spec["dtype"]
        for name, v in (("row", row), ("col", col)):
            if isinstance(v, int) and v < 0:
                raise IndexOutOfRange(f"{name}={v} is negative; addresses are positions, not Python indices")
        if not shape:
            raise IndexOutOfRange(f"{tensor} is a scalar tensor; it has no rows")
        if row >= shape[0]:
            raise IndexOutOfRange(f"row {row} beyond {tensor} shape {shape}")
        if len(shape) == 2 and col is not None and col >= shape[1]:
            raise IndexOutOfRange(f"col {col} beyond {tensor} shape {shape}")
        if dtype not in DTYPE_CODE or DTYPE_CODE[dtype] is None:
            raise UnknownTensor(f"dtype {dtype} has no reader in this instrument")
        code, size = DTYPE_CODE[dtype]
        base = self.data_base + spec["offsets"][0]
        return spec, shape, code, size, base

    # ------------------------------------------------------------------ reads
    def address_of(self, tensor: str, row: int, col: int = 0) -> dict:
        """Where a value lives, WITHOUT reading it. Header arithmetic only: no mmap slice is taken, so this
        writes no journal record. It exists because an artifact must be able to say which address produced a
        figure, and the reader should not have to re-derive the offset by hand and trust the derivation."""
        spec, shape, code, size, base = self._resolve(tensor, row, col)
        if len(shape) == 1:
            if col != 0:
                raise IndexOutOfRange(f"{tensor} is 1-dimensional; column {col} does not exist")
            off = base + row * size
        else:
            off = base + (row * shape[1] + col) * size
        return {"tensor": tensor, "row": int(row), "col": int(col) if len(shape) > 1 else None,
                "byte_offset": off, "bytes_of_one_value": size, "dtype": spec["dtype"],
                "struct_code": code,
                "tensor_base_offset": base, "shape": list(shape)}

    def read_scalar(self, tensor: str, row: int, col: int, probe_id: str = "unattributed") -> float:
        spec, shape, code, size, base = self._resolve(tensor, row, col)
        if len(shape) != 2:
            raise IndexOutOfRange(f"{tensor} is {len(shape)}-dimensional; (row, col) needs 2")
        off = base + (row * shape[1] + col) * size
        raw = self._mm[off:off + size]
        val = struct.unpack("<" + code, raw)[0]
        self._commit(probe_id, tensor, {"row": row, "col": col}, [val], raw, 1)
        return val

    def read_row(self, tensor: str, row: int, probe_id: str = "unattributed"):
        """One row of a 2-D tensor, or the single element at `row` of a 1-D tensor.

        A 1-D tensor has no rows in the matrix sense: `read_row("ln_f.weight", 0)` is one float, not the
        vector. That was not obvious and the first self-test asserted the one-float behaviour as if it were
        correct -- a test pinning the bug beside it. Whole 1-D tensors are read with `read_vector`, which
        refuses a 2-D tensor rather than guessing which of the two the caller meant.
        """
        vals = self.read_rows(tensor, [row], probe_id)
        return vals[0]

    def read_vector(self, tensor: str, probe_id: str = "unattributed"):
        """The whole of a 1-D tensor (biases, layernorm scales). Bounded, journaled, read-only."""
        spec, shape, code, size, base = self._resolve(tensor, 0, None)
        if len(shape) != 1:
            raise IndexOutOfRange(f"{tensor} is {len(shape)}-dimensional; read_vector is for 1-D tensors -- "
                                  f"use read_rows for a row of a matrix")
        n = shape[0]
        if n > MAX_VECTOR_VALUES:
            raise GatherBudgetExceeded(f"{tensor} holds {n} values, above MAX_VECTOR_VALUES="
                                       f"{MAX_VECTOR_VALUES}; a whole-tensor dump is not a probe")
        off = base
        raw = self._mm[off:off + n * size]
        vals = list(array(code, raw))
        self._commit(probe_id, tensor, {"vector": True}, vals, raw, n)
        return vals

    def read_rows(self, tensor: str, rows, probe_id: str = "unattributed"):
        rows = list(rows)
        if not rows:
            raise IndexOutOfRange("empty row list")
        if len(rows) > MAX_ROWS_PER_READ:
            raise GatherBudgetExceeded(f"{len(rows)} rows exceeds MAX_ROWS_PER_READ={MAX_ROWS_PER_READ}; "
                                       f"the op rule does not charge gathers, so this budget is what stops a "
                                       f"probe reading the donor into RAM for free")
        out = []
        for r in rows:
            spec, shape, code, size, base = self._resolve(tensor, r, None)
            width = shape[1] if len(shape) > 1 else 1
            off = base + r * width * size
            raw = self._mm[off:off + width * size]
            out.append(list(array(code, raw)))
            self._commit(probe_id, tensor, {"row": r}, out[-1], raw, width)
        return out

    def _commit(self, probe_id, tensor, indices, values, raw, n_values):
        self.n_reads += 1
        self.rows_read += 1
        self.bytes_read += len(raw)
        self.journal.record(address_space_version=ADDRESS_SPACE_VERSION, probe_id=probe_id,
                            tensor=tensor, indices=indices, shape=self.table[tensor]["shape"],
                            dtype=self.table[tensor]["dtype"], n_values=n_values, raw_bytes=len(raw),
                            values=values, charged_ops=0)

    def close(self):
        self._mm.close()
        self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def sha256_of_file(rel_path: str = DONOR_FILE, root: Path = ROOT) -> str:
    h = hashlib.sha256()
    with (Path(root) / rel_path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
