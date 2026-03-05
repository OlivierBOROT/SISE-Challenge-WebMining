"""Train a behavior model on synthetic data and save it.

Improved script: robust imports, reproducible randomness, CLI options,
and clearer synthetic event generation to simulate different user types.

Run from repository root:
    python -m app.behavior_model._train_model_with_dummy_data --out data/models/behavior_analysis_model.joblib
"""

from __future__ import annotations

import argparse
import logging
import random
import time
from pathlib import Path
from typing import Dict, List

from app.behavior_model.feature_builder import FeatureBuilder
from app.behavior_model.model_manager import ModelManager

logger = logging.getLogger("behavior_train")


def generate_events(
    user_type: int, current_time: float, n_events: int = 25
) -> List[Dict]:
    """Generate a list of synthetic events for one pseudo-user.

    - user_type 0: browsing user (hovers/clicks, low-price)
    - user_type 1: purchasing user (achat events, higher price)
    - user_type 2: navigation/page-focused user (pagination events)
    """
    events: List[Dict] = []
    categories = ["shoes", "bags", "electronics", "books"]
    products = ["P1", "P2", "P3", "P4", "P5"]

    for i in range(n_events):
        ts = current_time - random.uniform(0, 9.9)
        roll = random.random()
        if user_type == 0:
            # Browsing: mix of hovers and clicks, mostly low prices
            evt = {
                "timestamp": ts,
                "object": "product",
                "category": random.choice(categories[:2]),
                "product_name": random.choice(products[:2]),
                "price": round(random.uniform(10, 80), 2),
                "time_spent": round(random.uniform(0.2, 6.0), 3),
                "event_type": "hover" if roll < 0.7 else "click",
            }
        elif user_type == 1:
            # Purchasing: more 'achat' events and higher prices
            evt = {
                "timestamp": ts,
                "object": "product",
                "category": random.choice(categories[2:]),
                "product_name": random.choice(products[2:]),
                "price": round(random.uniform(150, 600), 2),
                "time_spent": round(random.uniform(0.1, 4.0), 3),
                "event_type": "achat" if roll < 0.5 else "click",
            }
        else:
            # Navigation-focused: page events interleaved with occasional clicks
            if roll < 0.6:
                evt = {
                    "timestamp": ts,
                    "object": "page",
                    "page_num": random.randint(1, 8),
                }
            else:
                evt = {
                    "timestamp": ts,
                    "object": "product",
                    "category": random.choice(categories),
                    "product_name": random.choice(products),
                    "price": round(random.uniform(5, 300), 2),
                    "time_spent": round(random.uniform(0.1, 2.0), 3),
                    "event_type": "click",
                }
        events.append(evt)

    return events


def build_feature_set(num_per_type: int = 15, events_per_user: int = 25) -> List[Dict]:
    fb = FeatureBuilder()
    current_time = time.time()
    feature_dicts: List[Dict] = []
    for utype in range(3):
        for _ in range(num_per_type):
            events = generate_events(utype, current_time, n_events=events_per_user)
            f = fb.build(events, current_time=current_time)
            feature_dicts.append(f)
    return feature_dicts


def main() -> None:
    parser = argparse.ArgumentParser(description="Train synthetic behavior model.")
    parser.add_argument(
        "--out",
        default="data/models/behavior_analysis_model.joblib",
        help="Output path for the trained model",
    )
    parser.add_argument(
        "--per-class", type=int, default=50, help="Synthetic users per class"
    )
    parser.add_argument(
        "--events", type=int, default=25, help="Events per synthetic user"
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for reproducibility"
    )
    parser.add_argument(
        "--min-cluster", type=int, default=5, help="HDBSCAN min_cluster_size"
    )
    parser.add_argument(
        "--pca-dim", type=int, default=5, help="PCA output dims (if used)"
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    logger.info("Starting synthetic training run")

    random.seed(args.seed)

    logger.info("Building synthetic feature set...")
    features = build_feature_set(
        num_per_type=args.per_class, events_per_user=args.events
    )

    logger.info("Fitting model (HDBSCAN)...")
    mm = ModelManager(
        use_pca=True, pca_dim=args.pca_dim, min_cluster_size=args.min_cluster
    )
    mm.fit(features)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Saving model to {out_path}...")
    mm.save(str(out_path))
    logger.info("Done. Model saved.")


if __name__ == "__main__":
    main()
