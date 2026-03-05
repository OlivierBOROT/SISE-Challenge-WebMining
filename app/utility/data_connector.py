"""
Data Connector Utility

Provides source-aware data management separating POC (Proof of Concept)
data collection from production inference. Wraps StorageService and provides
convenience methods for different data sources.

This module allows:
1. POC frontend to collect test/fictive data independently
2. Production systems to use the same ML backend
3. Training on either POC data, production data, or both (with filtering)
4. Easy migration: when moving to production, just switch the source labels
"""

from __future__ import annotations

import logging
from typing import Generic, Type, List

import numpy as np

from app.utility.storage import StorageService, T

logger = logging.getLogger(__name__)

# Data source constants
SOURCE_POC = "poc"
SOURCE_PRODUCTION = "production"


class DataConnector(Generic[T]):
    """
    Generic data connector managing source-aware storage.
    Wraps StorageService and provides POC-specific operations.
    """

    def __init__(
        self,
        feature_class: Type[T],
        storage: StorageService[T] | None = None,
    ):
        """
        Initialize data connector.

        Args:
            feature_class: The feature set class type
            storage: StorageService instance. If None, creates default.
        """
        self.feature_class = feature_class
        self.storage = storage or StorageService(feature_class)

    def persist_poc_data(
        self,
        feature_set: T,
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
        feature_set: T,
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
        sources: List[str] | None = None,
    ) -> List[T]:
        """
        Load feature sets for training.

        Args:
            include_poc: Include POC data (source="poc")
            include_production: Include production data (source="production")
            sources: Explicit list of source labels to load (overrides include_* flags)

        Returns:
            List of feature sets matching the source criteria
        """
        if sources is not None:
            # Use explicit sources list
            all_sets = []
            for src in sources:
                all_sets.extend(self.storage.load_feature_sets(source=src))
            return all_sets
        
        # Use include_* flags
        all_sets = []
        if include_poc:
            all_sets.extend(self.storage.load_feature_sets(source=SOURCE_POC))
        if include_production:
            all_sets.extend(self.storage.load_feature_sets(source=SOURCE_PRODUCTION))
        
        return all_sets

    def get_training_data_numpy(
        self,
        include_poc: bool = False,
        include_production: bool = True,
        sources: List[str] | None = None,
        feature_columns: List[str] | None = None,
    ) -> np.ndarray:
        """
        Load feature sets for training as numpy array.

        Args:
            include_poc: Include POC data
            include_production: Include production data
            sources: Explicit list of source labels
            feature_columns: Column order for features

        Returns:
            np.ndarray: Training data as feature vectors
        """
        if sources is not None:
            # Load specific sources
            all_vectors = []
            for src in sources:
                vectors = self.storage.load_numpy(source=src, feature_columns=feature_columns)
                if len(vectors) > 0:
                    all_vectors.append(vectors)
            return np.vstack(all_vectors) if all_vectors else np.empty((0, 0), dtype=float)
        
        # Combine requested sources
        all_vectors = []
        if include_poc:
            vectors = self.storage.load_numpy(source=SOURCE_POC, feature_columns=feature_columns)
            if len(vectors) > 0:
                all_vectors.append(vectors)
        if include_production:
            vectors = self.storage.load_numpy(source=SOURCE_PRODUCTION, feature_columns=feature_columns)
            if len(vectors) > 0:
                all_vectors.append(vectors)
        
        return np.vstack(all_vectors) if all_vectors else np.empty((0, 0), dtype=float)

    def get_record_count(self) -> int:
        """
        Get total record count across all sources.

        Returns:
            int: Total number of records
        """
        return self.storage.record_count()

    def get_source_breakdown(self) -> dict:
        """
        Get record count by source.

        Returns:
            dict: Records grouped by source label
        """
        return self.storage.count_by_source()

    def clear_all_data(self) -> None:
        """
        Clear all stored data.
        Use with caution — data is not recoverable.
        """
        self.storage.clear()
        logger.warning("All data cleared from storage")
