from collections import Counter
import numpy as np

from app.schemas import UserEvents, ProductEvent, CategoryEvent, ScrollEvent


class BehaviourFeatureBuilder:
    @staticmethod
    def build(user_events: UserEvents) -> dict:
        """
        Transforme une liste d'événements en vecteur de features.

        Parameters
        ----------
        events : list
            Liste d'événements (dict ou Pydantic model)

        Returns
        -------
        dict
            Dictionnaire de features numériques
        """

        if not user_events:
            return {}

        events = user_events.events
        timestamps = [e.timestamp for e in events]

        # ---------- base metrics ----------
        event_count = len(events)
        duration = max(timestamps) - min(timestamps)
        duration = max(duration, 1e-6)

        events_per_second = event_count / duration

        # ---------- dt metrics ----------
        if len(timestamps) > 1:
            dt = np.diff(timestamps)
            mean_dt = float(np.mean(dt))
            std_dt = float(np.std(dt))
            min_dt = float(np.min(dt))
            max_dt = float(np.max(dt))
            burstiness = std_dt / mean_dt if mean_dt > 0 else 0
        else:
            mean_dt = std_dt = min_dt = max_dt = burstiness = 0

        # ---------- event types ----------
        hover_count = 0
        click_count = 0
        purchase_count = 0

        product_ids = []
        hover_times = []

        category_ids = []

        scroll_deltas = []

        for e in events:
            obj = e.object

            if isinstance(e, ProductEvent):
                product_ids.append(e.product_id)

                if e.event_type == "hover":
                    hover_count += 1
                    hover_times.append(e.time_spent)

                elif e.event_type == "click":
                    click_count += 1

                elif e.event_type == "achat":
                    purchase_count += 1

            elif isinstance(e, CategoryEvent):
                category_ids.append(e.category_id)

            elif isinstance(e, ScrollEvent):
                scroll_deltas.append(e.delta_y)

        product_events = len(product_ids)
        category_events = len(category_ids)

        # ---------- hover metrics ----------
        if hover_times:
            mean_hover = float(np.mean(hover_times))
            std_hover = float(np.std(hover_times))
            max_hover = float(np.max(hover_times))

            long_hover_ratio = sum(t > 0.8 for t in hover_times) / len(hover_times)
            short_hover_ratio = sum(t < 0.2 for t in hover_times) / len(hover_times)
        else:
            mean_hover = std_hover = max_hover = 0
            long_hover_ratio = short_hover_ratio = 0

        # ---------- product diversity ----------
        unique_products = len(set(product_ids))

        if product_events > 0:
            product_diversity = unique_products / product_events
        else:
            product_diversity = 0

        # focus score
        product_counts = Counter(product_ids)
        if product_counts:
            max_product_events = max(product_counts.values())
            product_focus_score = max_product_events / product_events
        else:
            product_focus_score = 0

        # ---------- category diversity ----------
        unique_categories = len(set(category_ids))

        if category_events > 0:
            category_diversity = unique_categories / category_events
        else:
            category_diversity = 0

        # ---------- entropy ----------
        def entropy(counter):
            total = sum(counter.values())
            if total == 0:
                return 0

            probs = [v / total for v in counter.values()]
            return float(-sum(p * np.log(p) for p in probs))

        product_entropy = entropy(product_counts)
        category_entropy = entropy(Counter(category_ids))

        # ---------- scroll metrics ----------
        scroll_events = len(scroll_deltas)

        if scroll_events > 0:
            total_scroll_distance = float(np.sum(np.abs(scroll_deltas)))

            scroll_speed = total_scroll_distance / duration

            scroll_std = float(np.std(scroll_deltas))

            large_scroll_ratio = (
                sum(abs(d) > 500 for d in scroll_deltas) / scroll_events
            )

        else:
            total_scroll_distance = 0
            scroll_speed = 0
            scroll_std = 0
            large_scroll_ratio = 0

        # ---------- ratios ----------
        hover_click_ratio = hover_count / (click_count + 1)

        # ---------- final feature vector ----------
        features = {
            # activity
            "events_per_second": events_per_second,
            "event_count": event_count,
            # navigation timing
            "mean_dt": mean_dt,
            "std_dt": std_dt,
            "min_dt": min_dt,
            "max_dt": max_dt,
            "burstiness": burstiness,
            # product interaction
            "hover_count": hover_count,
            "click_count": click_count,
            "purchase_count": purchase_count,
            # hover behaviour
            "mean_hover_time": mean_hover,
            "std_hover_time": std_hover,
            "max_hover_time": max_hover,
            "long_hover_ratio": long_hover_ratio,
            "short_hover_ratio": short_hover_ratio,
            # product structure
            "unique_products": unique_products,
            "product_diversity": product_diversity,
            "product_focus_score": product_focus_score,
            # category structure
            "unique_categories": unique_categories,
            "category_diversity": category_diversity,
            # entropy
            "product_entropy": product_entropy,
            "category_entropy": category_entropy,
            # scroll behaviour
            "scroll_events": scroll_events,
            "total_scroll_distance": total_scroll_distance,
            "scroll_speed": scroll_speed,
            "scroll_std": scroll_std,
            "large_scroll_ratio": large_scroll_ratio,
            # interaction ratios
            "hover_click_ratio": hover_click_ratio,
        }

        return features
