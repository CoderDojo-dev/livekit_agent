"""Twelve-Factor settings: everything via environment, nothing hardcoded.

This module holds configuration values only. It imports no vendor plugin: provider
construction (including noise cancellation) lives behind the providers/ boundary.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Worker configuration loaded from the environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    # --- LiveKit transport ---
    livekit_url: str = Field("ws://localhost:7880", alias="LIVEKIT_URL")
    livekit_api_key: str = Field("devkey", alias="LIVEKIT_API_KEY")
    livekit_api_secret: str = Field("devsecret_change_me", alias="LIVEKIT_API_SECRET")
    livekit_agent_name: str = Field("telecom-agent", alias="LIVEKIT_AGENT_NAME")

    # --- Language scope / spike session language ---
    supported_languages: str = Field("fr,ar,en", alias="SUPPORTED_LANGUAGES")
    default_language: str = Field("fr", alias="DEFAULT_LANGUAGE")
    session_language: str = Field("fr", alias="SESSION_LANGUAGE")
    session_caller_msisdn: str = Field("", alias="SESSION_CALLER_MSISDN")

    # --- STT primary (Deepgram) ---
    stt_model: str = Field("nova-3", alias="STT_MODEL")

    # --- TTS chain -------------------------------------------------------
    # Primary: ElevenLabs (only when ELEVEN_API_KEY is set — see providers/tts.py).
    tts_model: str = Field("eleven_flash_v2_5", alias="TTS_MODEL")
    eleven_voice_id: str = Field("EXAVITQu4vr4xnSDxMaL", alias="ELEVEN_VOICE_ID")
    eleven_api_key: str = Field("", alias="ELEVEN_API_KEY")

    # Cartesia (primary while ElevenLabs is unfunded). sonic-2 was RETIRED by
    # Cartesia on 2026-06-01; sonic-3 is the current stable (fr/ar/en native).
    cartesia_api_key: str = Field("", alias="CARTESIA_API_KEY")
    cartesia_tts_model: str = Field("sonic-3", alias="CARTESIA_TTS_MODEL")

    # Gemini TTS fallback — reuses GOOGLE_API_KEY (verified livekit-plugins-google
    # 1.6.3 ships google.beta.GeminiTTS; FallbackAdapter stream-adapts it).
    google_api_key: str = Field("", alias="GOOGLE_API_KEY")
    gemini_tts_model: str = Field("gemini-3.1-flash-tts-preview", alias="GEMINI_TTS_MODEL")
    gemini_tts_voice: str = Field("Kore", alias="GEMINI_TTS_VOICE")

    # Azure final fallback (skipped while AZURE_SPEECH_KEY is empty).
    azure_speech_key: str = Field("", alias="AZURE_SPEECH_KEY")

    # --- LLM chain: Gemini primary, then NVIDIA / OpenAI / Groq -----------
    llm_primary_model: str = Field("gemini-2.5-flash", alias="LLM_PRIMARY_MODEL")
    llm_fallback_model: str = Field("gpt-4o-mini", alias="LLM_FALLBACK_MODEL")
    openai_api_key: str = Field("", alias="OPENAI_API_KEY")

    nvidia_api_key: str = Field("", alias="NVIDIA_API_KEY")
    nvidia_model: str = Field("meta/llama-3.1-8b-instruct", alias="NVIDIA_MODEL")
    nvidia_timeout_s: float = Field(45.0, alias="NVIDIA_TIMEOUT_S")

    groq_api_key: str = Field("", alias="GROQ_API_KEY")
    groq_model: str = Field("llama-3.1-8b-instant", alias="GROQ_MODEL")
    groq_timeout_s: float = Field(30.0, alias="GROQ_TIMEOUT_S")

    # --- Optional Gladia STT (additional fallback after Deepgram) ---
    gladia_api_key: str = Field("", alias="GLADIA_API_KEY")

    # --- VAD / turn detection / latency ---
    vad_min_silence: float = Field(0.25, alias="VAD_MIN_SILENCE")
    preemptive_generation: bool = Field(True, alias="PREEMPTIVE_GENERATION")
    noise_cancellation: bool = Field(False, alias="NOISE_CANCELLATION")
    # stt | vad | multilingual. "multilingual" requires the main-process runner
    # registration performed in server.py (see providers/turn_detection.py).
    turn_detection_mode: str = Field("stt", alias="TURN_DETECTION_MODE")

    # --- Worker process hygiene ---
    job_memory_warn_mb: float = Field(1400.0, alias="JOB_MEMORY_WARN_MB")

    # --- Decision -> Policy façade ---
    decision_confidence_threshold: float = Field(0.5, alias="DECISION_CONFIDENCE_THRESHOLD")

    # --- Resilience chaos toggles (cookbook section 16) ---
    chaos_break_stt: bool = Field(False, alias="CHAOS_BREAK_STT")
    chaos_break_llm: bool = Field(False, alias="CHAOS_BREAK_LLM")
    chaos_break_tts: bool = Field(False, alias="CHAOS_BREAK_TTS")

    # --- Domain service URLs ---
    context_service_url: str = Field("http://localhost:8101", alias="CONTEXT_SERVICE_URL")
    decision_service_url: str = Field("http://localhost:8103", alias="DECISION_SERVICE_URL")
    policy_service_url: str = Field("http://localhost:8104", alias="POLICY_SERVICE_URL")
    execution_service_url: str = Field("http://localhost:8105", alias="EXECUTION_SERVICE_URL")
    notification_service_url: str = Field("http://localhost:8106", alias="NOTIFICATION_SERVICE_URL")
    knowledge_mcp_url: str = Field("http://localhost:8201/mcp", alias="KNOWLEDGE_MCP_URL")
    ticketing_mcp_url: str = Field("http://localhost:8202/mcp", alias="TICKETING_MCP_URL")

    @property
    def languages(self) -> list[str]:
        """Parsed supported-language list."""
        return [item.strip() for item in self.supported_languages.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()