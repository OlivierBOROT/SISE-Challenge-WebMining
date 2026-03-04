"""
Schema definitions for bot analysis features.
"""

from pydantic import BaseModel


class BotAnalysisAnswer(BaseModel):
    """Schema for bot analysis results."""

    is_bot: bool
    bot_score: float  # Confidence score between 0 and 1
