"""
Storage Service
Persists FeatureSet records to disk for offline model training.

Provides a StorageService class with methods for:
- Writing: append(feature_set, source='production')  →  data/features.jsonl
- Reading: load_feature_sets(), load_numpy() with optional source filtering
- Snapshots: export_parquet(), load_parquet()
- Housekeeping: record_count(), clear()

Each record includes metadata for versioning and future migration:
- session_id, page, batch_t, features, vector (core data)
- schema_version, feature_version (for versioning)
- stored_at (ISO timestamp for ordering)
- source (e.g., 'poc', 'production') for separating data origins
"""

from __future__ import annotations

import os
import json
import logging
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import numpy as np

from app.services.feature_service import FeatureSet, FEATURE_COLUMNS

logger = logging.getLogger(__name__)


class StorageService:
    """
    Manages persistent storage of feature sets for model training and analysis.
    Supports both JSONL (current) and future migration to database backends.
    """

    def __init__(
        self,
        data_dir: Path | str | None = None,
        jsonl_path: Path | str | None = None,
        parquet_path: Path | str | None = None,
    ):
        """
        Initialize storage service.

        Args:
            data_dir: Base data directory. Defaults to DATA_PATH env var or 'data'
            jsonl_path: Path to JSONL store. Defaults to data_dir/features.jsonl
            parquet_path: Path to Parquet snapshot. Defaults to data_dir/features.parquet
        """
        if data_dir is None:
            self.data_dir = Path(os.environ.get("DATA_PATH", "data"))
        else:
            self.data_dir = Path(data_dir)

        if jsonl_path is None:
            self.jsonl_path = self.data_dir / "features.jsonl"
        else:
            self.jsonl_path = Path(jsonl_path)

        if parquet_path is None:
            self.parquet_path = self.data_dir / "features.parquet"
        else:
            self.parquet_path = Path(parquet_path)

    def append(
        self,
        feature_set: FeatureSet,
        source: str = "production",
        schema_version: str = "1.0",
        feature_version: str = "1.0",
    ) -> None:
        """
        Append a single FeatureSet to the JSONL store with metadata.
        Creates the file (and data/ dir) if they don't exist.

        Args:
            feature_set: FeatureSet to persist
            source: Data origin ('poc' for POC collection, 'production' for real inference)
            schema_version: Storage schema version (for future migrations)
            feature_version: Feature extraction schema version
        """
        # Validate stats data
        self.data_dir.mkdir(parents=True, exist_ok=True)
        row = asdict(feature_set)
        # Add versioning and metadata
        row["source"] = source
        row["schema_version"] = schema_version
        row["feature_version"] = feature_version
        row["stored_at"] = datetime.utcnow().isoformat()
        with self.jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    def load_feature_sets(self, source: str | None = None) -> list[FeatureSet]:
        """
        Read all stored records back as FeatureSet objects.
        Skips malformed lines with a warning instead of crashing.

        Args:
            source: Filter by source ('poc', 'production', or None for all)

        Returns:
            list[FeatureSet]: Loaded feature sets, optionally filtered
        """
        if not self.jsonl_path.exists():
            return []

        results: list[FeatureSet] = []
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
                    logger.warning(f"Skipping malformed line {i}: {exc}")

        return results

    def load_numpy(self, source: str | None = None) -> np.ndarray:
        """
        Load all stored feature vectors as a numpy array of shape (N, N_FEATURES).
        Column order is guaranteed to match FEATURE_COLUMNS.

        Args:
            source: Filter by source ('poc', 'production', or None for all)

        Returns:
            np.ndarray: Shape (N, N_FEATURES)
        """
        feature_sets = self.load_feature_sets(source=source)
        if not feature_sets:
            return np.empty((0, len(FEATURE_COLUMNS)), dtype=float)

        return np.vstack([
            [fs.features.get(col, 0.0) for col in FEATURE_COLUMNS]
            for fs in feature_sets
        ])

    def export_parquet(self, src: Path | None = None, dst: Path | None = None) -> Path:
        """
        Convert the JSONL store to a compressed Parquet file.
        Useful before a retrain run to freeze a clean snapshot.
        Requires pandas + pyarrow.

        Args:
            src: Source JSONL path. Defaults to self.jsonl_path
            dst: Destination Parquet path. Defaults to self.parquet_path

        Returns:
            Path: Directory of the written Parquet file
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("export_parquet() requires pandas: pip install pandas pyarrow")

        if src is None:
            src = self.jsonl_path
        if dst is None:
            dst = self.parquet_path

        feature_sets = self.load_feature_sets()
        if not feature_sets:
            raise ValueError(f"No data found in {src}. Nothing to export.")

        rows = [
            {
                "session_id": fs.session_id,
                "page": fs.page,
                "batch_t": fs.batch_t,
                **{col: fs.features.get(col, 0.0) for col in FEATURE_COLUMNS}
            }
            for fs in feature_sets
        ]
        df = pd.DataFrame(rows)
        dst.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(dst, index=False, compression="snappy")
        logger.info(f"Exported {len(rows)} records to {dst}")
        return dst

    def load_parquet(self, path: Path | None = None) -> np.ndarray:
        """
        Load feature vectors from a Parquet snapshot as a numpy array.

        Args:
            path: Path to Parquet file. Defaults to self.parquet_path

        Returns:
            np.ndarray: Shape (N, N_FEATURES)
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("load_parquet() requires pandas: pip install pandas pyarrow")

        if path is None:
            path = self.parquet_path

        if not path.exists():
            raise FileNotFoundError(
                f"No Parquet snapshot found at {path}. Run export_parquet() first."
            )

        df = pd.read_parquet(path, columns=FEATURE_COLUMNS)
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

    def clear(self) -> None:
        """
        Delete the JSONL store.
        Use with caution — data is not recoverable.
        """
        if self.jsonl_path.exists():
            self.jsonl_path.unlink()
            logger.info(f"Cleared storage: {self.jsonl_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton for backward compatibility
# ─────────────────────────────────────────────────────────────────────────────
