import os
from typing import Any, Dict

import numpy as np
from joblib import load

from app.schemas import BehaviourFeatureSet


class BehaviourModelManager:
    """
    Loads scaler, PCA, and KMeans models from a directory (default 'data/models').
    Allows overriding each model path via kwargs. Provides a predict method
    that returns the cluster label and the 2D PCA projection.
    """

    def __init__(self, model_path: str = "data/models", **kwargs):
        scaler_path = kwargs.get(
            "scaler_path", os.path.join(model_path, "scaler_final.joblib")
        )
        pca_path = kwargs.get("pca_path", os.path.join(model_path, "pca_final.joblib"))
        kmeans_path = kwargs.get(
            "kmeans_path", os.path.join(model_path, "kmeans_final.joblib")
        )

        if not os.path.exists(scaler_path):
            raise FileNotFoundError(f"Scaler model not found at {scaler_path}")
        if not os.path.exists(pca_path):
            raise FileNotFoundError(f"PCA model not found at {pca_path}")
        if not os.path.exists(kmeans_path):
            raise FileNotFoundError(f"KMeans model not found at {kmeans_path}")

        self.scaler = load(scaler_path)
        self.pca = load(pca_path)
        self.kmeans = load(kmeans_path)

    def predict(self, features: BehaviourFeatureSet) -> Dict[str, Any]:
        X = np.array([features.vector], dtype=float)
        X_scaled = self.scaler.transform(X)
        X_scaled = self.scaler.transform(X)
        X_pca = self.pca.transform(X_scaled)
        label = int(self.kmeans.predict(X_pca)[0])
        comp1 = float(X_pca[0, 0])
        comp2 = float(X_pca[0, 1])
        result = {"label": label, "position": {"comp1": comp1, "comp2": comp2}}

        print("\n" * 2, flush=True)
        print("Predicted cluster label:", label, flush=True)
        print("PCA position:", result["position"], flush=True)
        return result
