import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("HYBRIDLLM_OFFLINE", "1")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

@pytest.fixture(scope="session")
def graph():
    from connectome.substrate import build_core_graph
    return build_core_graph()