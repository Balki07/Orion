"""LLM Quota schemas, DTOs, and request/response models."""

from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LLMQuotaConfigUpdate(BaseModel):
    rpm_limit: int = Field(ge=1, le=100000, description="Configured requests per minute limit")
    tpm_limit: int = Field(ge=1, le=50000000, description="Configured tokens per minute limit")
    rpd_limit: int = Field(ge=1, le=10000000, description="Configured requests per day limit")
    quota_timezone: str = Field(default="America/Los_Angeles", description="IANA Timezone for daily quota reset")
    warning_threshold_percent: float = Field(
        ge=0.01,
        le=1.0,
        default=0.80,
        description="Warning threshold percentage (e.g. 0.80 for 80%)",
    )
    safety_margin_percent: float = Field(
        ge=0.0,
        le=0.99,
        default=0.10,
        description="Safety reserve margin percentage (e.g. 0.10 for 10%)",
    )

    @field_validator("quota_timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        v_stripped = v.strip()
        try:
            ZoneInfo(v_stripped)
            return v_stripped
        except Exception:
            raise ValueError(
                f"Invalid IANA timezone identifier: '{v}'. Must be a valid timezone identifier such as 'America/Los_Angeles' or 'UTC'."
            )


class LLMRollingUsage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rolling_60s_requests: int
    rolling_60s_tokens: int
    rpm_limit: int
    tpm_limit: int
    rpm_utilization_percent: float
    tpm_utilization_percent: float


class LLMDailyUsage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    quota_timezone: str
    today_start_utc: datetime
    unique_questions_today: int
    total_provider_attempts_today: int
    successful_generations_today: int
    failed_provider_attempts_today: int
    fallback_events_today: int
    prompt_tokens_today: int
    completion_tokens_today: int
    total_tokens_today: int
    rpd_limit: int
    rpd_utilization_percent: float


class LLMQuotaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_id: str
    is_active_model: bool
    is_reference_quota: bool = True
    quota_source_disclaimer: str = (
        "Configured reference limits based on Google AI Studio tier. "
        "ORION does not have real-time access to Google's server-side quota balance. "
        "External applications using the same Google Cloud/AI Studio project or API key "
        "may consume quota independently of ORION's local usage records."
    )
    rpm_limit: int
    tpm_limit: int
    rpd_limit: int
    quota_timezone: str
    warning_threshold_percent: float
    safety_margin_percent: float
    last_updated_at: datetime
    rolling_usage: LLMRollingUsage
    daily_usage: LLMDailyUsage


class LLMQuestionBudgetEstimate(BaseModel):
    """Estimated question budget and quota limit projections across distinct time horizons."""

    model_config = ConfigDict(from_attributes=True)

    model_id: str
    is_active_model: bool

    # --- 1. Daily Horizon (RPD) ---
    daily_questions_remaining: int = Field(
        description="Conservative estimate of remaining research questions today bounded strictly by daily requests (RPD)."
    )
    daily_questions_typical: int = Field(
        description="Estimate of remaining questions today based on observed average token and retry usage."
    )
    daily_questions_optimistic: int = Field(
        description="Estimate of remaining questions today assuming single attempt and efficient context."
    )
    daily_limiting_quota: str = Field(
        default="RPD",
        description="Quota constraint governing the daily question horizon ('RPD')."
    )

    # --- 2. Immediate Window Horizon (Rolling 60s RPM / TPM) ---
    immediate_questions_conservative: int = Field(
        description="Conservative questions that can be asked immediately in the current rolling 60s window."
    )
    immediate_questions_typical: int = Field(
        description="Typical questions that can be asked immediately in the current rolling 60s window."
    )
    immediate_questions_optimistic: int = Field(
        description="Optimistic questions that can be asked immediately in the current rolling 60s window."
    )
    immediate_limiting_quota: str = Field(
        description="The tighter constraint within the immediate 60-second window ('RPM' or 'TPM')."
    )

    # --- Aliases / Backward Compatibility ---
    estimated_questions_remaining: int = Field(
        description="Alias for daily_questions_remaining (daily horizon capacity)."
    )
    estimated_questions_typical: int = Field(
        description="Alias for daily_questions_typical."
    )
    estimated_questions_optimistic: int = Field(
        description="Alias for daily_questions_optimistic."
    )
    limiting_quota: str = Field(
        default="RPD",
        description="Alias for daily_limiting_quota ('RPD')."
    )
    rolling_questions_remaining: int = Field(
        description="Alias for immediate_questions_conservative (rolling 60s capacity)."
    )

    # --- Detailed Resource Counters ---
    remaining_requests_today: int = Field(
        description="Remaining usable provider generation requests today after applying the safety margin."
    )
    remaining_tokens_today: int | None = Field(
        default=None,
        description="Remaining tokens today. Marked unavailable (null) because Google AI Studio enforces TPM rather than daily token limits.",
    )
    rolling_requests_remaining: int = Field(
        description="Remaining usable provider requests in the rolling 60-second window after applying the safety margin."
    )
    rolling_tokens_remaining: int = Field(
        description="Remaining usable tokens in the rolling 60-second window after applying the safety margin."
    )
    average_prompt_tokens: int = Field(
        description="Average prompt tokens per successful provider generation."
    )
    average_completion_tokens: int = Field(
        description="Average completion tokens per successful provider generation."
    )
    average_total_tokens: int = Field(
        description="Average total tokens per successful provider generation."
    )
    attempts_per_question: float = Field(
        description="Average provider attempts required per research question."
    )
    sample_size: int = Field(
        description="Number of successful historical generations with valid usage metadata used for estimation."
    )
    confidence: str = Field(
        description="Estimation confidence level ('low', 'medium', or 'high')."
    )
    is_fallback_estimate: bool = Field(
        description="True if historical data is insufficient and conservative fallback assumptions were applied."
    )
    safety_margin_percent: float = Field(
        description="Safety reserve margin percentage applied to all reference limits (e.g. 0.10 for 10%)."
    )
    estimation_disclaimer: str = Field(
        description="Explanation of estimation methodology, sample size caveats, and external quota risks."
    )


