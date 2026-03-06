import json
import os

import numpy as np
from joblib import load


class PlotService:
    X_pca: np.ndarray

    def __init__(self) -> None:
        self.data_dir = os.environ.get("DATA_PATH", "data")
        self.labeled_data = self.__load_labeled_data()
        self.pca = self.__load_pca()
        self.cluster_metadata = self.__load_cluster_metadata()

    def __load_labeled_data(self, filepath="models/labeled_data.npy") -> np.ndarray:
        """
        Load the fitted PCA matrix

        Args:
            filepath (str, optional): Data path file path. Defaults to "models/labeled_data.npy".

        Returns:
            pd.DataFrame: Matrix
        """
        path = os.path.join(self.data_dir, filepath)  # type: ignore
        return np.load(path)

    def __load_cluster_metadata(self, filepath="models/clusters_metadata.json") -> dict:
        """
        Load the cluster metadata (name and description)

        Args:
            filepath (str, optional): Metadata file path. Defaults to "models/clusters_metadata.json".

        Returns:
            dict: Metadata
        """
        path = os.path.join(self.data_dir, filepath)  # type: ignore
        with open(path, "r") as f:
            return json.load(f)

    def __load_pca(self, filepath="models/pca_final.joblib"):
        """
        Load the trained PCA model (joblib) to retrieve explained variance.

        Returns None if loading fails.
        """
        path = os.path.join(self.data_dir, filepath)  # type: ignore
        try:
            return load(path)
        except Exception:
            return None

    def pca_info(self) -> dict:
        """
        Return basic PCA info used by the front-end: explained variance for the
        first two components (as percentage) and labels for the axes.
        """
        if not getattr(self, "pca", None):
            return {
                "explained_variance": 0.0,
                "x_label": "Composante 1",
                "y_label": "Composante 2",
            }

        try:
            evr = getattr(self.pca, "explained_variance_ratio_", None)
            if evr is None:
                explained = 0.0
                by_comp = [0.0, 0.0]
            else:
                # total explained by first two components
                explained = float((evr[:2].sum()) * 100.0)
                # individual explained percentage per component
                by_comp = [float(evr[0] * 100.0), float(evr[1] * 100.0)]
        except Exception:
            explained = 0.0
            by_comp = [0.0, 0.0]

        return {
            "explained_variance": explained,
            "explained_by_component": by_comp,
            "x_label": "Composante 1",
            "y_label": "Composante 2",
        }

    def get_clusters(self) -> dict:
        """
        Retrive cluster metadata (name and description)

        Returns:
            dict: Metadata
        """
        return self.cluster_metadata

    def projection(self) -> dict:
        """
        Compute and format data for 2d scatter

        Returns:
            list[dict]: plot data
        """
        return {
            "x": self.labeled_data[:, 0].tolist(),
            "y": self.labeled_data[:, 1].tolist(),
            "label": self.labeled_data[:, 2].tolist(),
        }
