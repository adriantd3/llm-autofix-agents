from __future__ import annotations

import json
import os
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator

# Static provider URL map - single source of truth for default base URLs
PROVIDER_DEFAULT_URLS = {
    "ollama": "http://host.docker.internal:11500/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "openai": "https://api.openai.com/v1",
    "opencode_go": "https://opencode.ai/zen/go/v1",
}

# Keep these for backward compatibility with imports and tests
DEFAULT_OLLAMA_MODEL = "llama3.1:8b"
DEFAULT_OLLAMA_BASE_URL = PROVIDER_DEFAULT_URLS["ollama"]
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_GEMINI_BASE_URL = PROVIDER_DEFAULT_URLS["gemini"]
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_OPENAI_BASE_URL = PROVIDER_DEFAULT_URLS["openai"]
DEFAULT_OPENCODE_GO_MODEL = "deepseek-v4-flash"


class ProviderType(StrEnum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    GEMINI = "gemini"
    OPENCODE_GO = "opencode_go"


class LLMSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: ProviderType
    model: str = Field(min_length=1)
    api_key: SecretStr | None = None
    base_url: str | None = None
    max_turns: int = Field(default=3, ge=1, le=50)
    api_max_retries: int = Field(default=5, ge=0, le=10)
    api_retry_base_seconds: float = Field(default=1.0, ge=0.1, le=30.0)
    api_retry_max_seconds: float = Field(default=8.0, ge=0.1, le=120.0)
    tracing_disabled: bool = True
    extra_body: dict[str, Any] | None = None

    @field_validator("api_retry_max_seconds")
    @classmethod
    def _validate_retry_window(cls, value: float, info) -> float:
        base_seconds = info.data.get("api_retry_base_seconds")
        if isinstance(base_seconds, (int, float)) and value < float(base_seconds):
            raise ValueError("api_retry_max_seconds must be >= api_retry_base_seconds")
        return value

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> LLMSettings:
        """Load LLMSettings from environment.

        Note: max_turns is always set to a default value here. In batch execution,
        max_turns comes from the batch config YAML (GlobalSettings.llm.max_turns),
        not from the environment.
        """
        if env is None:
            values = _load_runtime_env()
        else:
            values = dict(env)

        # Parse and validate provider
        provider_raw = values.get("LLM_PROVIDER", ProviderType.OLLAMA.value).strip().lower()
        try:
            provider = ProviderType(provider_raw)
        except ValueError as exc:
            raise ValueError(f"Unsupported LLM_PROVIDER: {provider_raw}") from exc

        # Resolve model: explicit > provider default
        model = values.get("LLM_MODEL", "").strip()
        if not model:
            model = _get_default_model(provider)

        # Resolve base_url: static provider default only (OCP).
        # URLs are intrinsic to the provider strategy and do not change per environment.
        base_url = PROVIDER_DEFAULT_URLS[provider.value]

        # Resolve api_key: provider-specific env var with provider-specific requirements
        api_key_env_var = f"{provider.value.upper()}_API_KEY"
        api_key_value = values.get(api_key_env_var, "").strip()
        if not api_key_value:
            if provider in (ProviderType.OPENAI, ProviderType.GEMINI, ProviderType.OPENCODE_GO):
                raise ValueError(f"{api_key_env_var} is required for {provider.value} provider")
            # Ollama has a fallback API key
            api_key_value = "ollama"

        # Parse numeric fields with basic validation
        try:
            api_max_retries_str = values.get("LLM_API_MAX_RETRIES", "5").strip() or "5"
            api_max_retries = int(api_max_retries_str)

            api_retry_base_seconds_str = values.get("LLM_API_RETRY_BASE_SECONDS", "1.0").strip() or "1.0"
            api_retry_base_seconds = float(api_retry_base_seconds_str)

            api_retry_max_seconds_str = values.get("LLM_API_RETRY_MAX_SECONDS", "8.0").strip() or "8.0"
            api_retry_max_seconds = float(api_retry_max_seconds_str)
        except ValueError as exc:
            raise ValueError(f"Invalid numeric LLM configuration: {exc}") from exc

        # Parse boolean field with strict validation
        tracing_disabled_str = values.get("LLM_TRACING_DISABLED", "true").strip().lower()
        if tracing_disabled_str in {"1", "true", "yes", "on"}:
            tracing_disabled = True
        elif tracing_disabled_str in {"0", "false", "no", "off"}:
            tracing_disabled = False
        else:
            raise ValueError(f"Invalid boolean value for LLM_TRACING_DISABLED: {tracing_disabled_str}")

        try:
            return cls(
                provider=provider,
                model=model,
                api_key=SecretStr(api_key_value) if api_key_value else None,
                base_url=base_url,
                max_turns=3,  # max_turns from env is ignored; always use batch config
                api_max_retries=api_max_retries,
                api_retry_base_seconds=api_retry_base_seconds,
                api_retry_max_seconds=api_retry_max_seconds,
                tracing_disabled=tracing_disabled,
                extra_body=json.loads(values["LLM_EXTRA_BODY"]) if "LLM_EXTRA_BODY" in values else None,
            )
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

    def fingerprint_payload(self) -> dict[str, str | int | bool | None]:
        return {
            "provider": self.provider.value,
            "model": self.model,
            "base_url": self.base_url,
            "max_turns": self.max_turns,
            "api_max_retries": self.api_max_retries,
            "api_retry_base_seconds": self.api_retry_base_seconds,
            "api_retry_max_seconds": self.api_retry_max_seconds,
            "tracing_disabled": self.tracing_disabled,
        }


def _get_default_model(provider: ProviderType) -> str:
    """Return the default model for a given provider."""
    defaults = {
        ProviderType.OLLAMA: DEFAULT_OLLAMA_MODEL,
        ProviderType.GEMINI: DEFAULT_GEMINI_MODEL,
        ProviderType.OPENAI: DEFAULT_OPENAI_MODEL,
        ProviderType.OPENCODE_GO: DEFAULT_OPENCODE_GO_MODEL,
    }
    return defaults[provider]


def _load_runtime_env() -> dict[str, str]:
    values = _load_dotenv_values(Path(".env"))
    values.update(os.environ)
    return values


def _load_dotenv_values(dotenv_path: Path) -> dict[str, str]:
    if not dotenv_path.is_file():
        return {}

    parsed: dict[str, str] = {}
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, raw_value = line.split("=", 1)
        normalized_key = key.strip()
        if not normalized_key:
            continue

        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        parsed[normalized_key] = value

    return parsed
