"""Async HTTP client for LLM communication with Gemini and OpenAI compatibility."""

import logging
from typing import Optional
import httpx

from app.config import settings
from app.schemas.directives import DirectiveInterpretationItem
from app.schemas.request import BatterySpecs
from app.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from app.llm.parser import parse_llm_output, LLMParseError
from app.llm.fallback import fallback_interpret_all

logger = logging.getLogger("gridwise.llm")


class LLMClient:
    """Async client for calling Gemini or OpenAI-compatible generative language model endpoints."""

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        key = settings.effective_api_key or ""
        headers = {
            "Authorization": f"Bearer {key}",
            "x-goog-api-key": key,  # Native header for Google Gemini endpoints
            "Content-Type": "application/json",
        }
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.LLM_TIMEOUT_SECONDS),
                headers=headers,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def interpret_notes(
        self,
        operator_notes: list[str],
        battery: BatterySpecs,
    ) -> list[DirectiveInterpretationItem]:
        """
        Interprets natural language operator notes into structured directives.
        Calls Gemini / LLM if an API key is configured; falls back safely to deterministic rules
        if offline, unconfigured, or if the LLM request fails.
        """
        api_key = settings.effective_api_key
        if not api_key:
            logger.info("No LLM/Gemini API key configured. Using deterministic fallback interpreter.")
            return fallback_interpret_all(operator_notes, battery)

        client = await self.get_client()
        user_prompt = build_user_prompt(operator_notes, battery.capacity_kwh)
        model = settings.effective_model
        base_url = settings.effective_base_url

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }

        url = f"{base_url.rstrip('/')}/chat/completions"

        try:
            logger.info(f"Sending {len(operator_notes)} notes to model '{model}' at {url}")
            response = await client.post(url, json=payload)
            response.raise_for_status()

            res_data = response.json()
            raw_content = res_data["choices"][0]["message"]["content"]
            parsed_directives = parse_llm_output(raw_content)
            logger.info(f"Model successfully returned {len(parsed_directives)} directives")
            return parsed_directives

        except (httpx.HTTPError, httpx.TimeoutException, LLMParseError, KeyError, IndexError) as exc:
            logger.warning(
                f"LLM request or parsing failed ({type(exc).__name__}: {exc}). "
                "Failing safely using deterministic fallback parser."
            )
            return fallback_interpret_all(operator_notes, battery)


# Global singleton client
llm_client = LLMClient()
