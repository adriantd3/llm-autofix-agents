from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from llm_autofix_agents.llm.settings import (
    DEFAULT_GEMINI_BASE_URL,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    LLMSettings,
    ProviderType,
    _load_dotenv_values,
)


class LLMSettingsTests(unittest.TestCase):
    def test_from_env_defaults_to_ollama(self) -> None:
        settings = LLMSettings.from_env({})

        self.assertEqual(settings.provider, ProviderType.OLLAMA)
        self.assertEqual(settings.model, DEFAULT_OLLAMA_MODEL)
        self.assertEqual(settings.base_url, DEFAULT_OLLAMA_BASE_URL)

    def test_from_env_openai_requires_provider_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
            LLMSettings.from_env({"LLM_PROVIDER": "openai"})

    def test_from_env_gemini_requires_provider_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "GEMINI_API_KEY"):
            LLMSettings.from_env({"LLM_PROVIDER": "gemini"})

    def test_from_env_openai_custom_settings(self) -> None:
        settings = LLMSettings.from_env(
            {
                "LLM_PROVIDER": "openai",
                "OPENAI_API_KEY": "openai-key",
                "LLM_MODEL": "gpt-4.1",
                "LLM_TRACING_DISABLED": "false",
            }
        )

        self.assertEqual(settings.provider, ProviderType.OPENAI)
        self.assertEqual(settings.model, "gpt-4.1")
        # Base URL is static per provider (OCP) and never overridden by env.
        self.assertEqual(settings.base_url, "https://api.openai.com/v1")
        self.assertEqual(settings.max_turns, 3)  # max_turns always comes from batch config, not env
        self.assertFalse(settings.tracing_disabled)

    def test_from_env_gemini_uses_default_base_url(self) -> None:
        settings = LLMSettings.from_env(
            {
                "LLM_PROVIDER": "gemini",
                "GEMINI_API_KEY": "gemini-key",
            }
        )

        self.assertEqual(settings.provider, ProviderType.GEMINI)
        self.assertEqual(settings.model, DEFAULT_GEMINI_MODEL)
        self.assertEqual(settings.base_url, DEFAULT_GEMINI_BASE_URL)

    def test_from_env_invalid_boolean(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid boolean value"):
            LLMSettings.from_env(
                {
                    "LLM_PROVIDER": "gemini",
                    "GEMINI_API_KEY": "test-key",
                    "LLM_TRACING_DISABLED": "sometimes",
                }
            )

    def test_from_env_base_url_is_static(self) -> None:
        """Base URL is static per provider and ignores env overrides (OCP)."""
        settings = LLMSettings.from_env(
            {
                "LLM_PROVIDER": "ollama",
                "LLM_BASE_URL": "http://remote.example:11500/v1",
                "LLM_MODEL": "custom-model",
            }
        )

        self.assertEqual(settings.provider, ProviderType.OLLAMA)
        # Static default; env override is intentionally ignored.
        self.assertEqual(settings.base_url, DEFAULT_OLLAMA_BASE_URL)
        self.assertEqual(settings.model, "custom-model")

    def test_load_dotenv_values_parses_supported_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            dotenv_path = Path(tmp_dir) / ".env"
            dotenv_path.write_text(
                "# comment\n"
                "GEMINI_API_KEY=plain-key\n"
                "LLM_PROVIDER='gemini'\n"
                'LLM_MODEL="gemini-2.5-pro"\n'
                "INVALID_LINE\n",
                encoding="utf-8",
            )

            values = _load_dotenv_values(dotenv_path)

            self.assertEqual(values["GEMINI_API_KEY"], "plain-key")
            self.assertEqual(values["LLM_PROVIDER"], "gemini")
            self.assertEqual(values["LLM_MODEL"], "gemini-2.5-pro")

    def test_load_dotenv_values_missing_file(self) -> None:
        values = _load_dotenv_values(Path("non-existing-file.env"))
        self.assertEqual(values, {})


class BugEntryExtraPackagesTests(unittest.TestCase):
    def test_extra_packages_defaults_to_empty_list(self) -> None:
        from llm_autofix_agents.batch.config import BugEntry

        bug = BugEntry(id="scrapy-33", program="scrapy", metadata={"project": "scrapy", "bug_id": "33", "version": "0"})
        self.assertEqual(bug.extra_packages, [])

    def test_extra_packages_accepts_package_list(self) -> None:
        from llm_autofix_agents.batch.config import BugEntry

        bug = BugEntry(
            id="scrapy-33",
            program="scrapy",
            metadata={"project": "scrapy", "bug_id": "33", "version": "0"},
            extra_packages=["testfixtures", "six"],
        )
        self.assertEqual(bug.extra_packages, ["testfixtures", "six"])

    def test_extra_packages_rejects_non_list(self) -> None:
        from pydantic import ValidationError
        from llm_autofix_agents.batch.config import BugEntry

        with self.assertRaises(ValidationError):
            BugEntry(id="x", extra_packages="testfixtures")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
