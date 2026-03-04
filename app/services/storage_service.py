"""
Storage Service
Persists FeatureSet records to disk for offline model training.

Write path (called at inference time):
    append(feature_set)  →  data/features.jsonl   (one JSON line per batch)

Read path (called at training time):
    load_feature_sets()  →  list[FeatureSet]
    load_numpy()         →  np.ndarray  (N, N_FEATURES)

Snapshot path (optional — freeze a clean Parquet file before retraining):
    export_parquet()     →  data/features.parquet
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from app.services.feature_service import FeatureSet, FEATURE_COLUMNS

# ─────────────────────────────────────────────────────────────────────────────
# Paths  (data/ is created by the Flask app factory at startup)
# ─────────────────────────────────────────────────────────────────────────────

_DATA_DIR      = Path(__file__).parent.parent.parent / "data"
JSONL_PATH     = _DATA_DIR / "features.jsonl"
PARQUET_PATH   = _DATA_DIR / "features.parquet"


# ─────────────────────────────────────────────────────────────────────────────
# Write — called during inference
# ─────────────────────────────────────────────────────────────────────────────

def append(feature_set: FeatureSet) -> None:
    """
    Append a single FeatureSet to the JSONL store.
    Creates the file (and data/ dir) if they don't exist.
    One line = one batch = one training sample.
    """
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    row = asdict(feature_set)   # {session_id, page, batch_t, features, vector}
    with JSONL_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# Read — called during training
# ─────────────────────────────────────────────────────────────────────────────

def load_feature_sets(path: Path = JSONL_PATH) -> list[FeatureSet]:
    """
    Read all stored records back as FeatureSet objects.
    Skips malformed lines with a warning instead of crashing.
    """
    if not path.exists():
        return []

    results: list[FeatureSet] = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                results.append(
                    FeatureSet(
                        session_id=row["session_id"],
                        page=row["page"],
                        batch_t=row["batch_t"],
                        features=row["features"],
                        vector=row["vector"],
                    )
                )
            except (KeyError, json.JSONDecodeError) as exc:
                print(f"[storage_service] Skipping malformed line {i}: {exc}")

    return results


def load_numpy(path: Path = JSONL_PATH) -> np.ndarray:
    """
    Load all stored feature vectors as a numpy array of shape (N, N_FEATURES).
    Column order is guaranteed to match FEATURE_COLUMNS.
    """
    feature_sets = load_feature_sets(path)
    if not feature_sets:
        return np.empty((0, len(FEATURE_COLUMNS)), dtype=float)

    return np.vstack([
        [fs.features.get(col, 0.0) for col in FEATURE_COLUMNS]
        for fs in feature_sets
    ])


# ─────────────────────────────────────────────────────────────────────────────
# Parquet snapshot — optional, for larger datasets
# ─────────────────────────────────────────────────────────────────────────────

def export_parquet(
    src: Path = JSONL_PATH,
    dst: Path = PARQUET_PATH,
) -> Path:
    """
    Convert the JSONL store to a compressed Parquet file.
    Useful before a retrain run to freeze a clean snapshot.
    Requires pandas + pyarrow.

    Returns the path of the written Parquet file.
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("export_parquet() requires pandas: pip install pandas pyarrow")

    feature_sets = load_feature_sets(src)
    if not feature_sets:
        raise ValueError(f"No data found in {src}. Nothing to export.")

    rows = [
        {"session_id": fs.session_id, "page": fs.page, "batch_t": fs.batch_t,
         **{col: fs.features.get(col, 0.0) for col in FEATURE_COLUMNS}}
        for fs in feature_sets
    ]
    df = pd.DataFrame(rows)
    dst.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(dst, index=False, compression="snappy")
    return dst


def load_parquet(path: Path = PARQUET_PATH) -> np.ndarray:
    """
    Load feature vectors from a Parquet snapshot as a numpy array.
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("load_parquet() requires pandas: pip install pandas pyarrow")

    if not path.exists():
        raise FileNotFoundError(f"No Parquet snapshot found at {path}. Run export_parquet() first.")

    df = pd.read_parquet(path, columns=FEATURE_COLUMNS)
    return df.to_numpy(dtype=float)


# ─────────────────────────────────────────────────────────────────────────────
# Housekeeping
# ─────────────────────────────────────────────────────────────────────────────

def record_count(path: Path = JSONL_PATH) -> int:
    """Return the number of stored records without loading them into memory."""
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def clear(path: Path = JSONL_PATH) -> None:
    """Delete the JSONL store. Use with caution — data is not recoverable."""
    if path.exists():
        path.unlink()
