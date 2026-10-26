"""Compare two snapshots of state/banc_brain.npz by array content.

np.savez embeds zip member timestamps, so byte hashes differ on every
save even when the arrays are identical. This compares arrays.
"""
import sys
import numpy as np

a = np.load(sys.argv[1], allow_pickle=True)
b = np.load(sys.argv[2], allow_pickle=True)
ka, kb = set(a.files), set(b.files)
print("keys only in A:", sorted(ka - kb))
print("keys only in B:", sorted(kb - ka))
diff = []
for k in sorted(ka & kb):
    xa, xb = a[k], b[k]
    if xa.shape != xb.shape or xa.dtype != xb.dtype:
        diff.append((k, "shape/dtype", str(xa.shape), str(xb.shape)))
        continue
    if xa.dtype == object:
        same = all((x == y) for x, y in zip(xa.tolist(), xb.tolist()))
        if not same:
            diff.append((k, "object values differ", "", ""))
        continue
    if not np.array_equal(xa, xb):
        n = int((xa != xb).sum())
        diff.append((k, "values differ", n, int(xa.size)))
print("arrays compared:", len(ka & kb))
print("differing:", diff if diff else "NONE - identical content")