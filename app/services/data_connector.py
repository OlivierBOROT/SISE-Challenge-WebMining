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

import numpy as np

from app.input_model.feature_builder import InputFeatureSet, FEATURE_COLUMNS
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
        feature_set: InputFeatureSet,
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

    def persist_production_data(
        self,
        feature_set: InputFeatureSet,
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

    def get_training_data(
        self,
        include_poc: bool = False,
        include_production: bool = True,
        sources: list[str] | None = None,
    ) -> list[InputFeatureSet]:
        """
        Load feature sets for training.

        Args:
            include_poc: Include POC data (source="poc")
            include_production: Include production data (source="production")
            sources: Explicit list of source labels to load (overrides include_* flags
                     when provided). E.g. ["human", "bot_direct", "bot_linear"]

        Returns:
            list[InputFeatureSet]: Combined feature sets based on filters
        """
        if sources is not None:
            results = []
            for src in sources:
                results.extend(self.storage.load_feature_sets(source=src))
            return results

        results = []
        if include_production:
            results.extend(self.storage.load_feature_sets(source=SOURCE_PRODUCTION))
        if include_poc:
            results.extend(self.storage.load_feature_sets(source=SOURCE_POC))
        return results

    def get_training_data_numpy(
        self,
        include_poc: bool = False,
        include_production: bool = True,
        sources: list[str] | None = None,
    ) -> np.ndarray:
        """
        Load feature vectors as numpy array for training.

        Args:
            include_poc: Include POC data (source="poc")
            include_production: Include production data (source="production")
            sources: Explicit list of source labels to load (overrides include_* flags
                     when provided). E.g. ["human", "bot_direct", "bot_scan"]

        Returns:
            np.ndarray: Shape (N, N_FEATURES)
        """
        if sources is not None:
            parts = []
            for src in sources:
                data = self.storage.load_numpy(source=src)
                if data.shape[0] > 0:
                    parts.append(data)
            return np.vstack(parts) if parts else np.empty((0, len(FEATURE_COLUMNS)), dtype=float)

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
        Get counts of stored records grouped by source label.

        Returns:
            dict: e.g. {'human': 12, 'bot_direct': 8, 'total': 20, ...}
        """
        by_source = self.storage.count_by_source()
        return {**by_source, "total": sum(by_source.values())}

