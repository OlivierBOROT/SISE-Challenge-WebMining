from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field, confloat, conint


# ----------------------------
# Base Event
# ----------------------------
class BaseEvent(BaseModel):
    timestamp: float = Field(..., description="Unix timestamp de l'événement")
    object: Literal["product", "category", "page", "scroll"] = Field(
        ..., description="Type d'objet"
    )


# ----------------------------
# Event produit
# ----------------------------
class ProductEvent(BaseEvent):
    object: Literal["product"]
    # Only validate product identifier, event type and time spent
    product_id: str = Field(..., description="ID du produit (data-id)")
    event_type: Literal["hover", "click", "achat"] = Field(
        ..., description="Type d'événement produit"
    )
    time_spent: confloat(ge=0) = Field(..., description="Temps passé (secondes)")


# ----------------------------
# Event catégorie
# ----------------------------
class CategoryEvent(BaseEvent):
    object: Literal["category"]
    # Only validate category identifier, event type and time spent
    category_id: str = Field(..., description="ID de la catégorie (data-id)")
    event_type: Literal["hover", "click"] = Field(
        ..., description="Type d'événement catégorie"
    )
    time_spent: confloat(ge=0) = Field(..., description="Temps passé (secondes)")


# ----------------------------
# Event page
# ----------------------------
class PageEvent(BaseEvent):
    object: Literal["page"]
    page_num: conint(ge=1)


class ScrollEvent(BaseEvent):
    object: Literal["scroll"]
    delta_y: float = Field(..., description="Delta Y du scroll (px)")
    scroll_position: float = Field(
        ..., description="Position de scroll normalisée (0.0-1.0)"
    )


# ----------------------------
# Wrapper pour les événements utilisateur
# ----------------------------
class UserEvents(BaseModel):
    user_id: str
    events: List[Union[ProductEvent, CategoryEvent, PageEvent, ScrollEvent]]
