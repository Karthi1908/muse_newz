from __future__ import annotations
import json
from typing import Any, Type, TypeVar
import httpx
from pydantic import BaseModel
from config.settings import settings

T = TypeVar("T", bound=BaseModel)


class MetaMuseModelClient:
    """
    Unified Google ADK + Meta Muse Model API client (Constitution §1, §2, §6).
    Reads LLM_API_BASE_URL and MUSE_TEXT_MODEL exclusively from .env via settings.
    Provides:
      1. Google ADK LlmAgent / ParallelAgent / LoopAgent execution via LiteLLM or Custom BaseLlm adapter.
      2. Structured Pydantic JSON completion with deterministic timeout & fallback.
    """

    def __init__(self, temperature: float = 0.2) -> None:
        self.api_base = settings.LLM_API_BASE_URL
        self.api_key = settings.MODEL_API_KEY
        self.model_id = settings.MUSE_TEXT_MODEL
        self.temperature = temperature
        self.timeout = settings.LLM_TIMEOUT_SECONDS

    def get_adk_llm(self) -> Any:
        """
        Returns a Google ADK compatible model object (LiteLlm wrapper or custom adapter)
        pointing to LLM_API_BASE_URL and MUSE_TEXT_MODEL from .env.
        """
        try:
            from google.adk.models.lite_llm import LiteLlm  # type: ignore

            return LiteLlm(
                model=f"openai/{self.model_id}",
                api_base=self.api_base,
                api_key=self.api_key or "demo-key",
                temperature=self.temperature,
            )
        except Exception:
            return self

    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Type[T],
        fallback_factory: Any = None,
    ) -> T:
        """
        Calls Meta Model API (/chat/completions) for structured JSON matching `response_schema`.
        Enforces Constitution Principle 1: timeout + deterministic fallback when offline or in demo mode.
        """
        if settings.DEMO_CACHE_MODE == "always" or not settings.has_live_api_key:
            if fallback_factory is not None:
                return fallback_factory()
            raise RuntimeError("Live Meta API key not configured and no fallback_factory provided.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        schema_json = json.dumps(response_schema.model_json_schema(), indent=2)
        payload = {
            "model": self.model_id,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"{system_prompt}\n\n"
                        f"You MUST respond ONLY with valid JSON conforming to this JSON Schema:\n{schema_json}"
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    settings.chat_completions_url,
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                body = resp.json()
                raw_content = body["choices"][0]["message"]["content"].strip()
                if raw_content.startswith("```"):
                    raw_content = raw_content.strip("`")
                    if raw_content.lower().startswith("json"):
                        raw_content = raw_content[4:].strip()
                return response_schema.model_validate_json(raw_content)
        except Exception:
            if fallback_factory is not None:
                return fallback_factory()
            raise


def get_muse_model(temperature: float = 0.2) -> MetaMuseModelClient:
    return MetaMuseModelClient(temperature=temperature)
