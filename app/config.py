"""
Configuration management for ScienceQuest Live.
Loads environment variables safely using python-dotenv.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env if present
load_dotenv()


@dataclass
class Settings:
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    debug: bool = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")

    # Twitch Configuration
    simulation_mode: bool = os.getenv("SIMULATION_MODE", "true").lower() in ("true", "1", "yes")
    twitch_channel: str = os.getenv("TWITCH_CHANNEL", "")
    twitch_bot_nickname: str = os.getenv("TWITCH_BOT_NICKNAME", "ScienceQuestBot")
    twitch_oauth_token: str = os.getenv("TWITCH_OAUTH_TOKEN", "")
    twitch_client_id: str = os.getenv("TWITCH_CLIENT_ID", "")
    twitch_client_secret: str = os.getenv("TWITCH_CLIENT_SECRET", "")
    twitch_redirect_uri: str = os.getenv("TWITCH_REDIRECT_URI", "http://localhost:8000/auth/twitch/callback")

    # AI Configuration
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


settings = Settings()
