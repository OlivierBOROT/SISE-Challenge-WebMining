import json
import logging
import math
import os

from rapidfuzz import process

from app.schemas import Product

logger = logging.getLogger(__name__)


class ProductData:
    def __init__(self) -> None:
        self.data, self.categories = self._load_data()

    def _load_data(self) -> tuple[list[Product], tuple[str]]:
        """
        Loads product json from data directory

        Returns:
            dict: Products
        """
        data_path = os.environ.get("DATA_PATH", "data")
        json_path = os.path.join(data_path, "products", "products.json")

        with open(json_path, "r") as f:
            content = json.load(f)

            categories = tuple({p["category"] for p in content})

            products = [Product(**p) for p in content]

        return products, categories

    def search(self, query: str, score_cutoff=60) -> list[Product]:
        """
        Retrieve a list of product by query

        Args:
            query (str): Query to retrive corresponding product

        Returns:
            list[Product]: Corresponding products
        """
        titles = [p.title for p in self.data]
        matches = process.extract(query, titles, limit=26, score_cutoff=score_cutoff)

        title_to_product = {p.title: p for p in self.data}
        return [title_to_product[match[0]] for match in matches]

    def get_all(self) -> list[Product]:
        """
        Retrieve all products

        Returns:
            dict: Products
        """
        return self.data

    def get_by_category(self, category: str) -> list[Product]:
        """
        Retrieve all products from a specific category

        Args:
            category (str): Product category

        Returns:
            dict: Products
        """
        products = [p for p in self.data if p.category == category]
        return products

    def get_by_id(self, id: str) -> Product:
        """
        Retrieve a product by its ID

        Args:
            id (str): Product ID

        Returns:
            dict: dict
        """
        for p in self.data:
            if p.id == id:
                return p

        raise IndexError(f"No product found with id {id}")

    def get_available_categories(self) -> tuple[str]:
        """
        Return a list of available product categories

        Returns:
            list[str]: Product categories
        """
        return self.categories

    def paginate(
        self, data: list[Product], page: int, count=15
    ) -> tuple[list[Product], int]:
        """
        Get paginated product

        Args:
            page (int): Page to get
            count (int, optional): Products per page. Defaults to 15.

        Returns:
            list[Product]: Paginated products
            int: Last page index for this data
        """
        # Clamp invalid low page numbers to 1 instead of raising an error.
        if page < 1:
            page = 1
        if count < 1:
            raise ValueError("count must be >= 1")

        max_page = math.ceil(len(data) / count)
        if page > max_page:
            page = max_page

        start = (page - 1) * count
        end = start + count
        return data[start:end], max_page
