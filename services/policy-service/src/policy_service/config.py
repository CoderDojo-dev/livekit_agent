"""Versioned, env-driven policy thresholds (twelve-factor). No threshold hardcoded in a rule."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PolicyThresholds(BaseSettings):
    """Deterministic thresholds for the section 6 business rules."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    payment_cap: float = Field(200.0, alias="POLICY_PAYMENT_CAP_TND")
    deferral_min_age_days: int = Field(180, alias="POLICY_DEFERRAL_MIN_AGE_DAYS")
    deferral_max_per_year: int = Field(2, alias="POLICY_DEFERRAL_MAX_PER_YEAR")
    deferral_unpaid_threshold: float = Field(150.0, alias="POLICY_DEFERRAL_UNPAID_THRESHOLD_TND")
    topup_denominations: tuple[float, ...] = Field(
        (5.0, 10.0, 20.0, 50.0), alias="POLICY_TOPUP_DENOMINATIONS_TND"
    )
    plan_codes: tuple[str, ...] = Field((), alias="POLICY_PLAN_CODES")

    @field_validator("topup_denominations", mode="before")
    @classmethod
    def _parse_denominations(cls, value):
        if isinstance(value, str):
            return tuple(float(p) for p in value.replace(";", ",").split(",") if p.strip())
        return value

    @field_validator("plan_codes", mode="before")
    @classmethod
    def _parse_plan_codes(cls, value):
        if isinstance(value, str):
            return tuple(p.strip().upper() for p in value.replace(";", ",").split(",") if p.strip())
        return value


@lru_cache
def get_thresholds() -> PolicyThresholds:
    """Return cached thresholds."""
    return PolicyThresholds()  # type: ignore[call-arg]