
from __future__ import annotations

MB_NEUROPILS: frozenset[str] = frozenset(
    {
        "MB_CA_L",
        "MB_CA_R",
        "MB_PED_L",
        "MB_PED_R",
        "MB_VL_L",
        "MB_VL_R",
        "MB_ML_L",
        "MB_ML_R",
    }
)

CX_NEUROPILS: frozenset[str] = frozenset({"PB", "FB", "EB", "NO"})

CX_ADJACENT_EXCLUDED: frozenset[str] = frozenset(
    {"BU_L", "BU_R", "LAL_L", "LAL_R", "AOTU_L", "AOTU_R"}
)

def neuropil_group(neuropil: str) -> str:
    """Classify one neuropil label: 'mb', 'cx', or 'other'."""
    if neuropil in MB_NEUROPILS:
        return "mb"
    if neuropil in CX_NEUROPILS:
        return "cx"
    return "other"