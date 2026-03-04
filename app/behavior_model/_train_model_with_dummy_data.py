"""Train a behavior model on synthetic data and save it.

Usage:
    python train_model.py
    python train_model.py --out data/models/behavior_analysis_model.joblib
"""

import argparse
import random
import time
from typing import Dict, List

from behavior_model import FeatureBuilder, ModelManager


def generate_events(
    user_type: int, current_time: float, n_events: int = 25
) -> List[Dict]:
    events = []
    categories = ["shoes", "bags", "electronics", "books"]
    products = ["P1", "P2", "P3", "P4", "P5"]
    for _ in range(n_events):
        ts = current_time - random.uniform(0, 9.9)
        if user_type == 0:
            events.append(
                {
                    "timestamp": ts,
                    "object": "product",
                    "category": random.choice(categories[:2]),
                    "product_name": random.choice(products[:2]),
                    "price": round(random.uniform(10, 50), 2),
                    "time_spent": round(random.uniform(1, 5), 2),
                    "event_type": random.choice(["click", "hover"]),
                }
            )
        elif user_type == 1:
            events.append(
                {
                    "timestamp": ts,
                    "object": "product",
                    "category": random.choice(categories[2:]),
                    "product_name": random.choice(products[2:]),
                    "price": round(random.uniform(200, 500), 2),
                    "time_spent": round(random.uniform(1, 5), 2),
                    "event_type": "achat",
                }
            )
        else:
            events.append(
                {"timestamp": ts, "object": "page", "page_num": random.randint(1, 5)}
            )
    return events


def build_feature_set(num_per_type: int = 15) -> List[Dict]:
    fb = FeatureBuilder()
    current_time = time.time()
    feature_dicts = []
    for utype in range(3):
        for _ in range(num_per_type):
            events = generate_events(utype, current_time, 25)
            f = fb.build(events, current_time=current_time)
            feature_dicts.append(f)
    return feature_dicts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default="data/models/behavior_analysis_model.joblib",
        help="Output path for the trained model",
    )
    parser.add_argument(
        "--per-class", type=int, default=15, help="Synthetic users per class"
    )
    args = parser.parse_args()

    print("Building synthetic feature set...")
    features = build_feature_set(num_per_type=args.per_class)

    print("Fitting model (HDBSCAN)...")
    mm = ModelManager(use_pca=True, pca_dim=5, min_cluster_size=5)
    mm.fit(features)

    out_path = args.out
    print(f"Saving model to {out_path}...")
    mm.save(out_path)
    print("Done. Model saved.")


if __name__ == "__main__":
    main()
