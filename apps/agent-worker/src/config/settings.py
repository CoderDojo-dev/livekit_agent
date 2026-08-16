"""Twelve-Factor settings: everything via environment, nothing hardcoded.

This module holds configuration values only. It imports no vendor plugin: provider
construction (including noise cancellation) lives behind the providers/ boundary.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Worker configuration loaded from the environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    # --- LiveKit transport (self-hosted) ---
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

    # --- TTS primary (ElevenLabs Flash v2.5) ---
    tts_model: str = Field("eleven_flash_v2_5", alias="TTS_MODEL")
    eleven_voice_id: str = Field("EXAVITQu4vr4xnSDxMaL", alias="ELEVEN_VOICE_ID")

    # --- TTS : choix dynamique du provider principal ---
    tts_primary: str = Field("cartesia", alias="TTS_PRIMARY")

    # --- TTS : Inworld (fallback, FR GA, clé Base64) ---
    inworld_api_key: str = Field("", alias="INWORLD_API_KEY")
    inworld_tts_model: str = Field("inworld-tts-2", alias="INWORLD_TTS_MODEL")
    inworld_voice_id: str = Field("alain", alias="INWORLD_VOICE_ID")

    # --- TTS : Smallest.ai (fallback, FR Beta — modèle standard, pas _pro) ---
    smallest_api_key: str = Field("", alias="SMALLEST_API_KEY")
    smallest_tts_model: str = Field("lightning_v3.1", alias="SMALLEST_TTS_MODEL")
    smallest_voice_id: str = Field("juliette", alias="SMALLEST_VOICE_ID")

    # --- TTS : Gemini (placeholder — NON branché, plugin beta streaming=False) ---
    gemini_tts_model: str = Field("gemini-2.5-flash-preview-tts", alias="GEMINI_TTS_MODEL")
    gemini_tts_voice: str = Field("Kore", alias="GEMINI_TTS_VOICE")

    # --- Deepgram TTS (optional — if livekit-plugins-deepgram adds TTS support) ---
    deepgram_tts_model: str = Field("aura-asteria-en", alias="DEEPGRAM_TTS_MODEL")
    deepgram_tts_voice: str = Field("aura-asteria-en", alias="DEEPGRAM_TTS_VOICE")

    # --- LLM chain: OpenAI primary (when enabled) or Gemini primary ---
    llm_primary_model: str = Field("gemini-2.5-flash", alias="LLM_PRIMARY_MODEL")
    llm_fallback_model: str = Field("gpt-4o-mini", alias="LLM_FALLBACK_MODEL")
    openai_enabled: bool = Field(False, alias="OPENAI_ENABLED")

    # --- Optional NVIDIA NIM fallback LLM (single key, no pool) ---
    nvidia_api_key: str = Field("", alias="NVIDIA_API_KEY")
    nvidia_model: str = Field("meta/llama-3.1-8b-instruct", alias="NVIDIA_MODEL")
    nvidia_timeout_s: float = Field(45.0, alias="NVIDIA_TIMEOUT_S")

    # --- Optional Groq fallback LLM (single key, no pool) ---
    groq_api_key: str = Field("", alias="GROQ_API_KEY")
    groq_model: str = Field("llama-3.1-8b-instant", alias="GROQ_MODEL")
    groq_timeout_s: float = Field(30.0, alias="GROQ_TIMEOUT_S")

    # --- Optional Gladia STT (additional fallback after Azure) ---
    gladia_api_key: str = Field("", alias="GLADIA_API_KEY")

    # --- Optional Cartesia TTS (additional TTS option behind ElevenLabs) ---
    cartesia_api_key: str = Field("", alias="CARTESIA_API_KEY")
    cartesia_tts_model: str = Field("sonic-2", alias="CARTESIA_TTS_MODEL")

    # --- VAD / turn detection / latency ---
    vad_min_silence: float = Field(0.25, alias="VAD_MIN_SILENCE")
    preemptive_generation: bool = Field(True, alias="PREEMPTIVE_GENERATION")

    # Consentement d'enregistrement. Mettre a false en developpement pour
    # economiser un tour TTS/LLM par appel. DOIT rester true en production.
    recording_consent_enabled: bool = Field(True, alias="RECORDING_CONSENT_ENABLED")

    noise_cancellation: bool = Field(False, alias="NOISE_CANCELLATION")

    # --- Decision -> Policy façade ---
    decision_confidence_threshold: float = Field(0.5, alias="DECISION_CONFIDENCE_THRESHOLD")

    # --- Resilience chaos toggles (cookbook section 16): break a primary on purpose ---
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
    ticketing_http_url: str = Field("http://localhost:8202", alias="TICKETING_HTTP_URL")
    # business-api binds 8108 (apps/business-api main.py); 8107 is the token-service.
    business_api_url: str = Field("http://localhost:8108", alias="BUSINESS_API_URL")
    # nms-sim publishes host port 8110 (docker-compose.apps.yml maps 8110 -> 8108).
    nms_service_url: str = Field("http://localhost:8110", alias="NMS_SERVICE_URL")

    _SERVICE_URL_FIELDS = (
        "context_service_url", "decision_service_url", "policy_service_url",
        "execution_service_url", "notification_service_url", "business_api_url",
        "nms_service_url", "ticketing_http_url", "knowledge_mcp_url",
        "ticketing_mcp_url",
    )

    @model_validator(mode="after")
    def _distinct_service_urls(self) -> Settings:
        """Deux services ne peuvent pas partager la meme adresse.

        Sinon l'agent interroge le mauvais service et recoit une reponse valide
        mais fausse - exactement le genre d'erreur qu'aucun test ne rattrape.
        """
        seen: dict[str, str] = {}
        clashes: list[str] = []
        for field in self._SERVICE_URL_FIELDS:
            url = (getattr(self, field) or "").strip().rstrip("/")
            if not url:
                continue
            if url in seen:
                clashes.append(f"{seen[url]} and {field} both point to {url}")
            else:
                seen[url] = field
        if clashes:
            raise ValueError(
                "Service URL collision: " + "; ".join(clashes)
                + ". Each service must have its own address, otherwise the agent "
                  "queries the wrong service."
            )
        return self

    @property
    def languages(self) -> list[str]:
        """Parsed supported-language list."""
        return [item.strip() for item in self.supported_languages.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()  # type: ignore[call-arg]
