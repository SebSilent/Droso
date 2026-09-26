
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "connectome" / "data"
NEURON_CSV = DATA_DIR / "neuron.csv.gz"
CONNECTIONS_CSV = DATA_DIR / "connections_princeton.csv.gz"

CONFIG_DIR = PROJECT_ROOT / "config"
MODELS_DIR = PROJECT_ROOT / "Models"
CACHE_DIR = PROJECT_ROOT / ".cache"
CHECKPOINTS_DIR = PROJECT_ROOT / "checkpoints"