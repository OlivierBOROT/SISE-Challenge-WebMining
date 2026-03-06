import os
import numpy as np
import json


class PlotService:

    X_pca: np.ndarray

    def __init__(self) -> None:
        self.data_dir = os.environ.get('DATA_PATH', "data")
        self.labeled_data = self.__load_labeled_data()
        self.cluster_metadata = self.__load_cluster_metadata()

    def __load_labeled_data(self, filepath="models/labeled_data.npy") -> np.ndarray:
        """
        Load the fitted PCA matrix

        Args:
            filepath (str, optional): Data path file path. Defaults to "models/labeled_data.npy".

        Returns:
            pd.DataFrame: Matrix
        """
        path = os.path.join(self.data_dir, filepath) #type: ignore
        return np.load(path)
    
    def __load_cluster_metadata(self, filepath="models/clusters_metadata.json") -> dict:
        """
        Load the cluster metadata (name and description)

        Args:
            filepath (str, optional): Metadata file path. Defaults to "models/clusters_metadata.json".

        Returns:
            dict: Metadata
        """
        path = os.path.join(self.data_dir, filepath) #type: ignore
        with open(path, "r") as f:
            return json.load(f)
        
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
            "label": self.labeled_data[:, 2].tolist()
        }
