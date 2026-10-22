"""Load project settings and build data paths."""

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_FILE = PROJECT_ROOT / "config" / "settings.yaml"


def load_settings():
    with open(SETTINGS_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def data_root(settings=None):
    settings = settings or load_settings()
    return Path(settings["data_root"])


def run_dir(kind, product, run, settings=None):
    """Directory for one product and run, e.g. raw/opendata/ifs_hres/20261022/00z."""
    return data_root(settings) / "raw" / kind / product / run.strftime("%Y%m%d") / f"{run:%H}z"
