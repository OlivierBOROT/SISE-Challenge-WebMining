import os
from typing import Any, Dict, List

import hdbscan
import numpy as np
from hdbscan import approximate_predict
from joblib import dump, load
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler


class BehaviourModelManager:
    """Wraps scaler/PCA/HDBSCAN and provides save/load and predict helpers."""

    def __init__(
        self, use_pca: bool = True, pca_dim: int = 5, min_cluster_size: int = 5
    ):
        self.scaler = StandardScaler()
        self.use_pca = use_pca
        self.pca = PCA(n_components=pca_dim) if use_pca else None
        self.model = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size, prediction_data=True
        )
        self.pca_dim = pca_dim
        self.pca_results = None
        self.fitted = False
        self.feature_order = None

    def fit(self, feature_dicts: List[Dict[str, Any]]):
        if not feature_dicts:
            raise ValueError("feature_dicts must be non-empty")
        self.feature_order = list(feature_dicts[0].keys())
        X = np.array(
            [[f[k] for k in self.feature_order] for f in feature_dicts], dtype=float
        )
        X_scaled = self.scaler.fit_transform(X)
        if self.use_pca and self.pca is not None:
            X_scaled = self.pca.fit_transform(X_scaled)
            self.pca_results = self.pca.explained_variance_ratio_
        self.model.fit(X_scaled)
        self.fitted = True

    def predict(self, features: Dict[str, Any]) -> int:
        if not self.fitted and self.feature_order is None:
            raise ValueError("Model not fitted or loaded")
        X = np.array([[float(features[k]) for k in self.feature_order]], dtype=float)
        X_scaled = self.scaler.transform(X)
        if self.use_pca and self.pca is not None:
            X_scaled = self.pca.transform(X_scaled)
        labels, strengths = approximate_predict(self.model, X_scaled)
        return int(labels[0])

    def save(self, path: str):
        dirpath = os.path.dirname(path)
        if dirpath and not os.path.exists(dirpath):
            os.makedirs(dirpath, exist_ok=True)
        payload = {
            "scaler": self.scaler,
            "pca": self.pca,
            "model": self.model,
            "feature_order": self.feature_order,
            "use_pca": self.use_pca,
        }
        dump(payload, path)

    @classmethod
    def load(cls, path: str) -> "ModelManager":
        if not os.path.exists(path):
            raise FileNotFoundError(f"Model file not found: {path}")
        payload = load(path)
        mm = cls(use_pca=payload.get("use_pca", True), pca_dim=5)
        mm.scaler = payload.get("scaler")
        mm.pca = payload.get("pca")
        mm.model = payload.get("model")
        mm.feature_order = payload.get("feature_order")
        mm.use_pca = payload.get("use_pca", True)
        mm.fitted = True
        return mm
