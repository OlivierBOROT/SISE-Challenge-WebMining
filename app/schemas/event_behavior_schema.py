from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field, confloat, conint


# ----------------------------
# Base Event
# ----------------------------
class BaseEvent(BaseModel):
    timestamp: float = Field(..., description="Unix timestamp de l'événement")
    object: Literal["product", "category", "page"] = Field(
        ..., description="Type d'objet"
    )


# ----------------------------
# Event produit
# ----------------------------
class ProductEvent(BaseEvent):
    object: Literal["product"]
    category: str
    product_name: str
    price: confloat(ge=0)
    time_spent: confloat(ge=0)
    event_type: Literal["hover", "click", "achat"]


# ----------------------------
# Event catégorie
# ----------------------------
class CategoryEvent(BaseEvent):
    object: Literal["category"]
    category_name: str
    time_spent: confloat(ge=0)
    event_type: Literal["hover", "click"]


# ----------------------------
# Event page
# ----------------------------
class PageEvent(BaseEvent):
    object: Literal["page"]
    page_num: conint(ge=1)


# ----------------------------
# Wrapper pour les événements utilisateur
# ----------------------------
class UserEvents(BaseModel):
    user_id: str
    events: List[Union[ProductEvent, CategoryEvent, PageEvent]]
