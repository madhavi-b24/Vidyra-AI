"""Central configuration, loaded from environment / .env.

Everything defaults to FREE tools so the app runs with only a free
Gemini API key (or fully offline via Ollama + local embeddings).
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    # LLM
    llm_provider: str = "gemini"          # gemini | ollama
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # Embeddings
    embeddings_provider: str = "local"    # local | gemini
    embeddings_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # TTS
    tts_provider: str = "gtts"            # gtts | edge | coqui

    # Avatar / video
    avatar_mode: str = "animated"         # animated | sadtalker | wav2lip
    sadtalker_dir: str = ""

    # Paths
    data_dir: str = "./data"

    # --- derived paths ---
    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def uploads_path(self) -> Path:
        p = self.data_path / "uploads"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def outputs_path(self) -> Path:
        p = self.data_path / "outputs"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def chroma_path(self) -> Path:
        p = self.data_path / "chroma"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def db_path(self) -> Path:
        return self.data_path / "ai_teacher.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()