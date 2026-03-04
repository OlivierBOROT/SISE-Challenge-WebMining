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

from app.services.feature_service import FeatureSet
from app.services import storage_service


# Data source constants
SOUCE_POC = "poc"
SOURCE_PRODUCTION = "production"


def persist_poc_data(
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
    storage_service.append(
        feature_set,
        source=SOUCE_POC,
        schema_version=schema_version,
        feature_version=feature_version,
    )


def persist_production_data(
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
    storage_service.append(
        feature_set,
        source=SOURCE_PRODUCTION,
        schema_version=schema_version,
        feature_version=feature_version,
    )


def get_training_data(include_poc: bool = False, include_production: bool = True):
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
        results.extend(
            storage_service.load_feature_sets(source=SOURCE_PRODUCTION)
        )

    if include_poc:
        results.extend(
            storage_service.load_feature_sets(source=SOUCE_POC)
        )

    return results


def get_training_data_numpy(include_poc: bool = False, include_production: bool = True):
    """
    Load feature vectors as numpy array for training.

    Args:
        include_poc: Include POC data in training set
        include_production: Include production data in training set

    Returns:
        np.ndarray: Shape (N, N_FEATURES)
    """
    import numpy as np

    parts = []

    if include_production:
        prod_data = storage_service.load_numpy(source=SOURCE_PRODUCTION)
        if prod_data.shape[0] > 0:
            parts.append(prod_data)

    if include_poc:
        poc_data = storage_service.load_numpy(source=SOUCE_POC)
        if poc_data.shape[0] > 0:
            parts.append(poc_data)

    if not parts:
        return np.empty((0, len(storage_service.FEATURE_COLUMNS)), dtype=float)

    return np.vstack(parts)


def get_data_statistics():
    """
    Get counts of stored data by source.

    Returns:
        dict: {'production': int, 'poc': int, 'total': int}
    """
    prod_count = len(storage_service.load_feature_sets(source=SOURCE_PRODUCTION))
    poc_count = len(storage_service.load_feature_sets(source=SOUCE_POC))

    return {
        "production": prod_count,
        "poc": poc_count,
        "total": prod_count + poc_count,
    }
