
from __future__ import annotations

NT_SIGN_MAP_VERSION = "1.0.0"

NT_TO_SIGN: dict[str, int | None] = {
    "ACH": +1,          # acetylcholine
    "ACETYLCHOLINE": +1,
    "GABA": -1,
    "HIST": -1,         # histamine (visual system)
    "HISTAMINE": -1,
    "GLUT": -1,         # glutamate: context-dependent, see module docstring
    "GLUTAMATE": -1,
    "DA": 0,            # dopamine    -- modulatory (DAN populations)
    "DOPAMINE": 0,
    "OCT": 0,           # octopamine  -- modulatory
    "OCTOPAMINE": 0,
    "SER": 0,           # serotonin   -- modulatory
    "SEROTONIN": 0,
    "TYR": 0,           # tyramine    -- modulatory
    "TYRAMINE": 0,
    "": None,           # unlabeled   -- must be excluded & counted
}

CONTEXT_DEPENDENT_NTS: frozenset[str] = frozenset({"GLUT", "GLUTAMATE"})

def normalize_nt(label: str | None) -> str:
    """Normalize a raw NT label from the CSVs (handles stray quotes/spaces)."""
    if label is None:
        return ""
    return str(label).strip().strip('"').strip().upper()

def resolve_sign(label: str | None) -> int | None:
    """Map a raw NT label to a postsynaptic sign; None means 'exclude & count'."""
    return NT_TO_SIGN.get(normalize_nt(label))