"""Schema definitions for event tracking."""

from pydantic import BaseModel


class Event(BaseModel):
    """Schema for a single user event."""

    element_type: (
        str  # e.g., "Beautés & Soins", "Vêtements", "Chaussures", "Accessoires"
    )
    element_id: str  # ID of the element interacted with
    event_type: str  # e.g., "click", "mousemove", "scroll"
    event_duration_sec: float  # Duration of the event in seconds
