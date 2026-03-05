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
    # Allow sending either full product details or only the product id.
    product_id: Optional[str] = None
    category: Optional[str] = None
    product_name: Optional[str] = None
    price: Optional[confloat(ge=0)] = None
    time_spent: Optional[confloat(ge=0)] = None
    event_type: Optional[Literal["hover", "click", "achat"]] = None


# ----------------------------
# Event catégorie
# ----------------------------
class CategoryEvent(BaseEvent):
    object: Literal["category"]
    # category may be sent as id (data-id) or as name
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    time_spent: Optional[confloat(ge=0)] = None
    event_type: Optional[Literal["hover", "click"]] = None


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
