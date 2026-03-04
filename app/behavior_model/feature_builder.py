import numpy as np


class FeatureBuilder:
    """Build weighted features from raw event lists.

    Events are dicts with at least a `timestamp` (seconds) and `object` key.
    This reproduces the logic from the original test script.
    """

    def __init__(self, decay_lambda: float = 0.3):
        self.decay_lambda = decay_lambda

    def _time_weight(self, event_time, current_time):
        delta = current_time - event_time
        return float(np.exp(-self.decay_lambda * delta))

    def _weighted_entropy(self, values, weights):
        if not values:
            return 0.0
        weight_sum = {}
        for v, w in zip(values, weights):
            weight_sum[v] = weight_sum.get(v, 0) + w
        total = sum(weight_sum.values())
        probs = [v / total for v in weight_sum.values()]
        # small epsilon to avoid log(0)
        return -sum(p * np.log(p + 1e-9) for p in probs)

    def build(self, events, current_time=None):
        """Build a feature dict from events.

        `events` is a list of dicts. `current_time` in seconds (defaults to now).
        """
        if current_time is None:
            import time

            current_time = time.time()

        product_weights, category_weights, page_weights = [], [], []
        product_prices, product_categories = [], []
        product_hover_w = product_click_w = product_purchase_w = 0.0
        cat_hover_w = cat_click_w = 0.0
        cat_names = []
        page_nums = []

        for e in events:
            # Ensure event timestamp is float seconds
            ts = float(e.get("timestamp", current_time))
            w = self._time_weight(ts, current_time)
            obj = e.get("object")

            if obj == "product":
                product_weights.append(w)
                if e.get("event_type") == "hover":
                    product_hover_w += w
                elif e.get("event_type") == "click":
                    product_click_w += w
                elif e.get("event_type") in ("achat", "purchase"):
                    product_purchase_w += w
                if e.get("price") is not None:
                    product_prices.append((float(e["price"]), w))
                if e.get("category"):
                    product_categories.append(e["category"])

            elif obj == "category":
                category_weights.append(w)
                if e.get("event_type") == "hover":
                    cat_hover_w += w
                elif e.get("event_type") == "click":
                    cat_click_w += w
                if e.get("category_name"):
                    cat_names.append(e["category_name"])

            elif obj == "page":
                page_weights.append(w)
                if e.get("page_num") is not None:
                    page_nums.append((int(e["page_num"]), w))

        features = {}
        features["prod_hover"] = product_hover_w
        features["prod_click"] = product_click_w
        features["prod_purchase"] = product_purchase_w
        features["prod_conversion"] = (
            (product_purchase_w / product_click_w) if product_click_w > 0 else 0.0
        )
        if product_prices:
            prices = np.array([p for p, w in product_prices])
            weights = np.array([w for p, w in product_prices])
            features["price_mean"] = float(np.average(prices, weights=weights))
            features["price_std"] = float(
                np.sqrt(
                    np.average((prices - features["price_mean"]) ** 2, weights=weights)
                )
            )
        else:
            features["price_mean"] = 0.0
            features["price_std"] = 0.0
        features["prod_entropy_cat"] = self._weighted_entropy(
            product_categories, product_weights
        )
        features["cat_hover"] = cat_hover_w
        features["cat_click"] = cat_click_w
        features["cat_entropy"] = self._weighted_entropy(cat_names, category_weights)
        features["pagination_weighted"] = sum([w for _, w in page_nums])
        if page_nums:
            pages = np.array([p for p, w in page_nums])
            weights = np.array([w for p, w in page_nums])
            features["page_mean"] = float(np.average(pages, weights=weights))
            features["page_max"] = int(max(pages))
        else:
            features["page_mean"] = 0.0
            features["page_max"] = 0
        return features
