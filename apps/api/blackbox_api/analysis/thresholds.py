"""Tunable numeric thresholds for the analysis rules.

Every rule condition that compares against a magic number reads it from this
model instead, so deployments can tune detection per facility or robot fleet
via environment variables (prefix ``BLACKBOX_RULE_``) or ``.env`` without
forking the rules. Defaults reproduce the engine's original behavior exactly.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AnalysisThresholds(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLACKBOX_RULE_", env_file=".env", extra="ignore"
    )

    # Persistent obstacle blockage
    obstacle_safety_threshold_m: float = Field(default=0.6, gt=0)
    obstacle_blockage_min_s: float = Field(default=5.0, gt=0)
    zero_cmd_eps: float = Field(default=0.01, ge=0)
    zero_cmd_streak_min: int = Field(default=5, ge=1)
    recovery_attempts_min: int = Field(default=2, ge=1)
    recovery_displacement_max_m: float = Field(default=0.3, gt=0)
    loc_conf_healthy_min: float = Field(default=0.9, ge=0, le=1)

    # Localization failure
    loc_conf_fault: float = Field(default=0.5, ge=0, le=1)
    loc_conf_drop: float = Field(default=0.4, gt=0, le=1)
    pose_jump_m: float = Field(default=1.0, gt=0)

    # Controller oscillation
    angular_flip_min_rad_s: float = Field(default=0.3, gt=0)
    angular_flips_min: int = Field(default=8, ge=2)
    flip_progress_max_m: float = Field(default=0.5, gt=0)
    flip_mean_speed_max: float = Field(default=0.15, gt=0)
    replan_min: int = Field(default=2, ge=1)

    # Sensor dropout
    sensor_gap_factor: float = Field(default=5.0, gt=1)
    sensor_gap_min_s: float = Field(default=2.0, gt=0)


@lru_cache
def get_thresholds() -> AnalysisThresholds:
    return AnalysisThresholds()


def reset_thresholds_cache() -> None:
    """Re-read thresholds from the environment (used by tests)."""
    get_thresholds.cache_clear()
