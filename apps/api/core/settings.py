# === TASK:WP-010:START ===
"""Application settings loaded from environment via pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Runtime configuration for the Hospital Assistant API.

    All values are loaded from environment variables.
    No secrets, database URLs, or provider credentials are stored here.
    """

    app_name: str = "HospitalAssistant"
    debug: bool = False
    api_prefix: str = "/api/v1"
    booking_draft_ttl_minutes: int = 30
    enable_agentic_booking: bool = True

    model_config = {"env_prefix": "HA_", "case_sensitive": False}
# === TASK:WP-010:END ===
