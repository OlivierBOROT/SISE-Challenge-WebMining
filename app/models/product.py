from dataclasses import dataclass

@dataclass
class Product:
    id: str
    title: str
    description_short: str
    description_long: str
    image_url: str
    category: str
    price: float