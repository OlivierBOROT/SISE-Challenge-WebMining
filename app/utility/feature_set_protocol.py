"""
Base Protocol for Feature Sets

Defines a common interface that both InputFeatureSet and BehaviourFeatureSet
must implement. This allows StorageService and DataConnector to be generic
and work with multiple feature set types.
"""

from typing import Protocol, Dict, List, runtime_checkable


@runtime_checkable
class FeatureSet(Protocol):
    """
    Protocol that defines the interface for feature set types.
    
    Any feature set (InputFeatureSet, BehaviourFeatureSet, etc.) that
    implements this protocol can be used with StorageService and DataConnector.
    
    Required attributes:
        - session_id: Unique identifier for the session
        - features: Dictionary of named features
        - vector: Ordered vector for model input
    """
    
    features: Dict[str, float]
    vector: List[float]
