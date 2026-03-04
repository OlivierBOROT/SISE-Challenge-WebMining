"""
Data Connector
Separates POC (Proof of Concept) data collection from production inference.
Provides a clean interface for storing and retrieving data by source.

This module allows:
1. POC frontend to collect test/fictive data independently
2. Production systems to use the same ML backend
3. Training on either POC data, production data, or both (with filtering)
4. Easy migration: when moving to production, just switch the source labels
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from app.services.feature_service import FeatureSet, FEATURE_COLUMNS
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)

# Data source constants
SOURCE_POC = "poc"
SOURCE_PRODUCTION = "production"


class DataConnector:
    """
    Manages data storage with source separation (POC vs. production).
    Wraps StorageService and provides POC-specific operations.
    """

    def __init__(self, storage: StorageService | None = None):
        """
        Initialize data connector.

        Args:
            storage: StorageService instance. If None, creates default.
        """
        self.storage = storage or StorageService()

    def persist_poc_data(
        self,
        feature_set: FeatureSet,
        schema_version: str = "1.0",
        feature_version: str = "1.0",
    ) -> None:
        """
        Store feature set from POC data collection.
        These records can be filtered out during training or used for testing.

        Args:
            feature_set: Extracted features from user interaction batch
            schema_version: Storage schema version
            feature_version: Feature extraction schema version
        """
        self.storage.append(
            feature_set,
            source=SOURCE_POC,
            schema_version=schema_version,
            feature_version=feature_version,
        )
        logger.debug(f"Persisted POC data for session {feature_set.session_id}")

    def persist_production_data(
        self,
        feature_set: FeatureSet,
        schema_version: str = "1.0",
        feature_version: str = "1.0",
    ) -> None:
        """
        Store feature set from production inference.
        These records are used for model retraining when ground truth is available.

        Args:
            feature_set: Extracted features from user interaction batch
            schema_version: Storage schema version
            feature_version: Feature extraction schema version
        """
        self.storage.append(
            feature_set,
            source=SOURCE_PRODUCTION,
            schema_version=schema_version,
            feature_version=feature_version,
        )
        logger.debug(f"Persisted production data for session {feature_set.session_id}")

    def get_training_data(
        self, include_poc: bool = False, include_production: bool = True
    ) -> list[FeatureSet]:
        """
        Load feature sets for training.

        Args:
            include_poc: Include POC data in training set
            include_production: Include production data in training set

        Returns:
            list[FeatureSet]: Combined feature sets based on filters
        """
        results = []

        if include_production:
            results.extend(self.storage.load_feature_sets(source=SOURCE_PRODUCTION))

        if include_poc:
            results.extend(self.storage.load_feature_sets(source=SOURCE_POC))

        return results

    def get_training_data_numpy(
        self, include_poc: bool = False, include_production: bool = True
    ) -> np.ndarray:
        """
        Load feature vectors as numpy array for training.

        Args:
            include_poc: Include POC data in training set
            include_production: Include production data in training set

        Returns:
            np.ndarray: Shape (N, N_FEATURES)
        """
        parts = []

        if include_production:
            prod_data = self.storage.load_numpy(source=SOURCE_PRODUCTION)
            if prod_data.shape[0] > 0:
                parts.append(prod_data)

        if include_poc:
            poc_data = self.storage.load_numpy(source=SOURCE_POC)
            if poc_data.shape[0] > 0:
                parts.append(poc_data)

        if not parts:
            return np.empty((0, len(FEATURE_COLUMNS)), dtype=float)

        return np.vstack(parts)

    def get_data_statistics(self) -> dict[str, int]:
        """
        Get counts of stored data by source.

        Returns:
            dict: {'production': int, 'poc': int, 'total': int}
        """
        prod_count = len(self.storage.load_feature_sets(source=SOURCE_PRODUCTION))
        poc_count = len(self.storage.load_feature_sets(source=SOURCE_POC))

        return {
            "production": prod_count,
            "poc": poc_count,
            "total": prod_count + poc_count,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton for backward compatibility
# ─────────────────────────────────────────────────────────────────────────────

_default_connector: DataConnector | None = None


def get_connector() -> DataConnector:
    """Get or create the default data connector singleton."""
    global _default_connector
    if _default_connector is None:
        _default_connector = DataConnector()
    return _default_connector


# ─────────────────────────────────────────────────────────────────────────────
# Legacy module-level functions for backward compatibility
# ─────────────────────────────────────────────────────────────────────────────


def persist_poc_data(
    feature_set: FeatureSet,
    schema_version: str = "1.0",
    feature_version: str = "1.0",
) -> None:
    """Backward compatible function. Uses default connector singleton."""
    get_connector().persist_poc_data(feature_set, schema_version, feature_version)


def persist_production_data(
    feature_set: FeatureSet,
    schema_version: str = "1.0",
    feature_version: str = "1.0",
) -> None:
    """Backward compatible function. Uses default connector singleton."""
    get_connector().persist_production_data(feature_set, schema_version, feature_version)


def get_training_data(
    include_poc: bool = False, include_production: bool = True
) -> list[FeatureSet]:
    """Backward compatible function. Uses default connector singleton."""
    return get_connector().get_training_data(include_poc, include_production)


def get_training_data_numpy(
    include_poc: bool = False, include_production: bool = True
) -> np.ndarray:
    """Backward compatible function. Uses default connector singleton."""
    return get_connector().get_training_data_numpy(include_poc, include_production)


def get_data_statistics() -> dict[str, int]:
    """Backward compatible function. Uses default connector singleton."""
    return get_connector().get_data_statistics()
