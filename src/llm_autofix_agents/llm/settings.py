from __future__ import annotations

import os
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator

DEFAULT_OLLAMA_MODEL = "llama3.1:8b"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"


class ProviderType(StrEnum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    GEMINI = "gemini"


class LLMSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: ProviderType
    model: str = Field(min_length=1)
    api_key: SecretStr | None = None
    base_url: str | None = None
    max_turns: int = Field(default=3, ge=1, le=10)
    tracing_disabled: bool = True

    @field_validator("model")
    @classmethod
    def _normalize_model(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("model cannot be empty")
        return normalized

    @field_validator("base_url")
    @classmethod
    def _normalize_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> LLMSettings:
        if env is None:
            values = _load_runtime_env()
        else:
            values = dict(env)

        provider_raw = values.get("LLM_PROVIDER", ProviderType.OLLAMA.value)
        provider = _parse_provider(provider_raw)

        model = values.get("LLM_MODEL")
        if model is None:
            if provider is ProviderType.OLLAMA:
                model = DEFAULT_OLLAMA_MODEL
            elif provider is ProviderType.GEMINI:
                model = DEFAULT_GEMINI_MODEL
            else:
                model = DEFAULT_OPENAI_MODEL

        max_turns = _parse_int(values.get("LLM_MAX_TURNS"), default=3)
        tracing_disabled = _parse_bool(values.get("LLM_TRACING_DISABLED"), default=True)

        api_key: str | None
        base_url: str | None
        if provider is ProviderType.OLLAMA:
            api_key = values.get("OLLAMA_API_KEY", "ollama")
            base_url = values.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
        elif provider is ProviderType.GEMINI:
            api_key = values.get("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
            base_url = values.get("GEMINI_BASE_URL", DEFAULT_GEMINI_BASE_URL)
        else:
            api_key = values.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
            base_url = values.get("OPENAI_BASE_URL")

        try:
            return cls(
                provider=provider,
                model=model,
                api_key=SecretStr(api_key) if api_key is not None else None,
                base_url=base_url,
                max_turns=max_turns,
                tracing_disabled=tracing_disabled,
            )
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

    def fingerprint_payload(self) -> dict[str, str | int | bool | None]:
        return {
            "provider": self.provider.value,
            "model": self.model,
            "base_url": self.base_url,
            "max_turns": self.max_turns,
            "tracing_disabled": self.tracing_disabled,
        }


def _parse_provider(value: str) -> ProviderType:
    normalized = value.strip().lower()
    try:
        return ProviderType(normalized)
    except ValueError as exc:
        raise ValueError(f"Unsupported LLM_PROVIDER: {value}") from exc


def _parse_int(value: str | None, *, default: int) -> int:
    if value is None:
        return default
    normalized = value.strip()
    if not normalized:
        return default
    return int(normalized)


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if not normalized:
        return default
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


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
