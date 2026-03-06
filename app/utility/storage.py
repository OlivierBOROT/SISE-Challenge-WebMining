"""
Storage Utility

Manages persistent storage of feature sets for model training and analysis.
Generic implementation supporting multiple feature set types (InputFeatureSet,
BehaviourFeatureSet, etc.) as long as they have session_id, features, and vector.

Supports both JSONL (current) and future migration to database backends.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Generic, List, Type, TypeVar

import numpy as np

from app.utility.feature_set_protocol import FeatureSet

# Type variable for generic feature sets, bound to FeatureSet protocol
T = TypeVar("T", bound=FeatureSet)

logger = logging.getLogger(__name__)


class StorageService(Generic[T]):
    """
    Generic storage service for managing persistent feature sets.
    Works with any feature set type that has session_id, features, and vector attributes.
    """

    def __init__(
        self,
        jsonl_path: Path | str,
        feature_class: Type[T],
        data_dir: Path | str | None = None,
        parquet_path: Path | str | None = None,
    ):
        """
        Initialize storage service.

        Args:
            feature_class: The feature set class type (e.g., InputFeatureSet)
            data_dir: Base data directory. Defaults to DATA_PATH env var or 'data'
            jsonl_path: Path to JSONL store. Defaults to data_dir/features.jsonl
            parquet_path: Path to Parquet snapshot. Defaults to data_dir/features.parquet
        """
        self.feature_class = feature_class

        if data_dir is None:
            self.data_dir = Path(os.environ.get("DATA_PATH", "data"))
        else:
            self.data_dir = Path(data_dir)

        self.jsonl_path = self.data_dir / Path(jsonl_path)

        if parquet_path is None:
            self.parquet_path = self.data_dir / "features.parquet"
        else:
            self.parquet_path = Path(parquet_path)

    def append(
        self,
        feature_set: T,
        source: str = "production",
        schema_version: str = "1.0",
        feature_version: str = "1.0",
    ) -> None:
        """
        Append a single feature set to the JSONL store with metadata.
        Creates the file (and data/ dir) if they don't exist.

        Args:
            feature_set: Feature set instance to persist
            source: Data origin ('poc' for POC collection, 'production' for real inference)
            schema_version: Storage schema version (for future migrations)
            feature_version: Feature extraction schema version
        """
        # If DEBUG is explicitly set to '0', skip writing to storage
        if os.environ.get("DEBUG", "1") == "0":
            logger.debug("DEBUG=0 set — skipping storage.append write")
            return

        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Convert feature set to dict (handles dataclasses and objects with __dict__)
        try:
            row = asdict(feature_set)  # type: ignore
        except TypeError:
            # Fallback for non-dataclass objects
            row = {
                k: v for k, v in feature_set.__dict__.items() if not k.startswith("_")
            }

        # Add versioning and metadata
        row["source"] = source
        row["schema_version"] = schema_version
        row["feature_version"] = feature_version
        row["stored_at"] = datetime.now(timezone.utc).isoformat()
        
        with self.jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    def load_feature_sets(self, source: str | None = None) -> List[T]:
        """
        Read all stored records back as feature set objects.
        Skips malformed lines with a warning instead of crashing.

        Args:
            source: Filter by source ('poc', 'production', or None for all)

        Returns:
            List of feature sets, optionally filtered by source
        """
        if not self.jsonl_path.exists():
            return []

        results: List[T] = []
        with self.jsonl_path.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)

                    # Filter by source if specified
                    if source and row.get("source") != source:
                        continue

                    # Remove metadata fields before creating feature set
                    row.pop("source", None)
                    row.pop("schema_version", None)
                    row.pop("feature_version", None)
                    row.pop("stored_at", None)

                    # Create feature set instance
                    feature_set = self.feature_class(**row)
                    results.append(feature_set)
                except (KeyError, json.JSONDecodeError, TypeError) as exc:
                    logger.warning(f"Skipping malformed line {i}: {exc}")

        return results

    def load_numpy(
        self, source: str | None = None, feature_columns: List[str] | None = None
    ) -> np.ndarray:
        """
        Load all stored feature vectors as a numpy array of shape (N, N_FEATURES).

        Args:
            source: Filter by source ('poc', 'production', or None for all)
            feature_columns: Column order for features. If None, uses dict key ordering

        Returns:
            np.ndarray: Shape (N, N_FEATURES)
        """
        feature_sets = self.load_feature_sets(source=source)
        if not feature_sets:
            n_features = len(feature_columns) if feature_columns else 0
            return np.empty((0, n_features), dtype=float)

        if feature_columns:
            return np.vstack(
                [
                    [fs.features.get(col, 0.0) for col in feature_columns]
                    for fs in feature_sets
                ]
            )
        else:
            # Use vectors directly
            return np.vstack([fs.vector for fs in feature_sets])

    def export_parquet(
        self,
        src: Path | None = None,
        dst: Path | None = None,
        feature_columns: List[str] | None = None,
    ) -> Path:
        """
        Convert the JSONL store to a compressed Parquet file.
        Requires pandas + pyarrow.

        Args:
            src: Source JSONL path. Defaults to self.jsonl_path
            dst: Destination Parquet path. Defaults to self.parquet_path
            feature_columns: Column order for features. If None, uses all features from first record

        Returns:
            Path: Destination Parquet file path
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError(
                "export_parquet() requires pandas: pip install pandas pyarrow"
            )

        if src is None:
            src = self.jsonl_path
        if dst is None:
            dst = self.parquet_path

        feature_sets = self.load_feature_sets()
        if not feature_sets:
            raise ValueError(f"No data found in {src}. Nothing to export.")

        # Determine feature columns if not provided
        if feature_columns is None:
            feature_columns = list(feature_sets[0].features.keys())

        rows = [
            {**{col: fs.features.get(col, 0.0) for col in feature_columns}}
            for fs in feature_sets
        ]
        df = pd.DataFrame(rows)
        dst.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(dst, index=False, compression="snappy")
        logger.info(f"Exported {len(rows)} records to {dst}")
        return dst

    def load_parquet(
        self, path: Path | None = None, feature_columns: List[str] | None = None
    ) -> np.ndarray:
        """
        Load feature vectors from a Parquet snapshot as a numpy array.

        Args:
            path: Path to Parquet file. Defaults to self.parquet_path
            feature_columns: Columns to load. If None, loads all columns

        Returns:
            np.ndarray: Shape (N, N_FEATURES)
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError(
                "load_parquet() requires pandas: pip install pandas pyarrow"
            )

        if path is None:
            path = self.parquet_path

        if not path.exists():
            raise FileNotFoundError(
                f"No Parquet snapshot found at {path}. Run export_parquet() first."
            )

        if feature_columns:
            df = pd.read_parquet(path, columns=feature_columns)
        else:
            df = pd.read_parquet(path)

        return df.to_numpy(dtype=float)

    def record_count(self) -> int:
        """
        Return the number of stored records without loading them into memory.

        Returns:
            int: Number of records
        """
        if not self.jsonl_path.exists():
            return 0
        with self.jsonl_path.open("r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())

    def count_by_source(self) -> Dict[str, int]:
        """
        Count stored records grouped by source label.
        Scans JSONL without loading full records into memory.

        Returns:
            dict: e.g. {'poc': 12, 'production': 8, ...}
        """
        counts: Dict[str, int] = {}
        if not self.jsonl_path.exists():
            return counts

        with self.jsonl_path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        record = json.loads(line)
                        src = record.get("source", "unknown")
                        counts[src] = counts.get(src, 0) + 1
                    except json.JSONDecodeError:
                        pass

        return counts

    def clear(self) -> None:
        """
        Delete the JSONL store.
        Use with caution — data is not recoverable.
        """
        if self.jsonl_path.exists():
            self.jsonl_path.unlink()
            logger.info(f"Cleared storage: {self.jsonl_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Module-level utility functions for simple use cases
# ─────────────────────────────────────────────────────────────────────────────

JSONL_PATH = Path(os.environ.get("DATA_PATH", "data")) / "features" / "features.jsonl"


def append(
    feature_set: FeatureSet,
    source: str = "production",
    schema_version: str = "1.0",
    feature_version: str = "1.0",
    path: Path | str | None = None,
) -> None:
    """
    Append a single feature set to the JSONL store.
    Creates the file (and parent dirs) if they don't exist.

    Args:
        feature_set: Any object implementing the FeatureSet protocol
        source: Data origin label (e.g. 'production', 'human', 'bot_linear')
        schema_version: Storage schema version
        feature_version: Feature extraction schema version
        path: Path to JSONL file. Defaults to JSONL_PATH
    """
    target = Path(path) if path is not None else JSONL_PATH
    # Respect DEBUG flag: if DEBUG=0 do not write
    if os.environ.get("DEBUG", "1") == "0":
        logger.debug("DEBUG=0 set — skipping module-level append write to %s", target)
        return

    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        row = asdict(feature_set)  # type: ignore
    except TypeError:
        row = {k: v for k, v in feature_set.__dict__.items() if not k.startswith("_")}

    row["source"] = source
    row["schema_version"] = schema_version
    row["feature_version"] = feature_version
    row["stored_at"] = datetime.now(timezone.utc).isoformat()

    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def load_numpy(
    path: Path | str | None = None, feature_columns: List[str] | None = None
) -> np.ndarray:
    """
    Load feature vectors from JSONL storage as a 2D numpy array.

    Args:
        path: Path to JSONL file. Defaults to JSONL_PATH (data/features.jsonl)
        feature_columns: Column order. If None, uses vector field directly

    Returns:
        np.ndarray: Shape (N, N_FEATURES)
    """
    if path is None:
        path = JSONL_PATH
    else:
        path = Path(path)

    if not path.exists():
        n_features = len(feature_columns) if feature_columns else 0
        return np.empty((0, n_features), dtype=float)

    vectors = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    record = json.loads(line)
                    if feature_columns:
                        vectors.append(
                            [
                                record.get("features", {}).get(col, 0.0)
                                for col in feature_columns
                            ]
                        )
                    else:
                        vectors.append(record.get("vector", []))
                except (json.JSONDecodeError, KeyError):
                    logger.warning(f"Skipped malformed line in {path}")

    if not vectors:
        n_features = len(feature_columns) if feature_columns else 0
        return np.empty((0, n_features), dtype=float)

    return np.array(vectors, dtype=float)


def record_count(path: Path | str | None = None) -> int:
    """
    Return the number of stored records without loading them into memory.

    Args:
        path: Path to JSONL file. Defaults to JSONL_PATH (data/features.jsonl)

    Returns:
        int: Number of records
    """
    if path is None:
        path = JSONL_PATH
    else:
        path = Path(path)

    if not path.exists():
        return 0

    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())
