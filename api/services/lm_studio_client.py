"""
LM Studio Client — Async HTTP client for LM Studio's OpenAI-compatible API.

Uses json_schema (GBNF grammar) for guaranteed structured JSON output.
Falls back to plain text + json_repair if schema enforcement fails.

Usage:
    client = LMStudioClient(base_url="http://host.docker.internal:1234/v1")
    if await client.is_available():
        result = await client.extract_json(system_prompt, user_content, schema)
"""

import os
from typing import Optional, Dict, Any

import httpx
import structlog
from json_repair import repair_json

logger = structlog.get_logger(__name__)


class LMStudioClient:
    """
    Async HTTP client for LM Studio (OpenAI-compatible API).

    Handles structured JSON extraction with graceful degradation.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = (base_url or os.getenv("LM_STUDIO_URL", "http://host.docker.internal:1234/v1")).rstrip("/")
        self.model = model or os.getenv("LM_STUDIO_MODEL", "qwen2.5-7b-instruct")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._available: Optional[bool] = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=5.0),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def is_available(self) -> bool:
        """Check if LM Studio server is running and has models loaded."""
        if self._available is not None:
            return self._available
        try:
            client = self._get_client()
            resp = await client.get(f"{self.base_url}/models")
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("data", [])
                self._available = len(models) > 0
                if self._available:
                    logger.info("lm_studio_available", model=models[0].get("id", "unknown"))
                return self._available
            self._available = False
            return False
        except Exception as e:
            self._available = False
            logger.debug("lm_studio_unavailable", error=str(e))
            return False

    async def extract_json(
        self,
        system_prompt: str,
        user_content: str,
        json_schema: Dict[str, Any],
        temperature: float = 0.1,
    ) -> Optional[Dict[str, Any]]:
        """
        Extract structured JSON from LM Studio.

        Strategy:
        1. Try json_schema (GBNF grammar) for guaranteed valid JSON
        2. Fallback: no response_format + json_repair parsing
        3. Return None if all attempts fail

        Args:
            system_prompt: System prompt for the LLM
            user_content: User content to extract from
            json_schema: JSON Schema for structured output
            temperature: Sampling temperature (low for extraction)

        Returns:
            Parsed JSON dict, or None if extraction failed
        """
        # Attempt 1: json_schema (GBNF grammar)
        result = await self._attempt_extract(
            system_prompt, user_content, temperature,
            response_format={"type": "json_schema", "json_schema": json_schema},
        )
        if result is not None:
            return result

        # Attempt 2: No response_format + json_repair
        logger.debug("lm_studio_json_schema_failed", fallback="json_repair")
        result = await self._attempt_extract(
            system_prompt, user_content, temperature,
            response_format=None,
        )
        if result is not None:
            return result

        logger.warning("lm_studio_extraction_failed", system_prompt=system_prompt[:50])
        return None

    async def _attempt_extract(
        self,
        system_prompt: str,
        user_content: str,
        temperature: float,
        response_format: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Single attempt to extract JSON from LM Studio."""
        try:
            client = self._get_client()
            body: Dict[str, Any] = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "temperature": temperature,
                "max_tokens": 2048,
            }
            if response_format:
                body["response_format"] = response_format

            resp = await client.post(f"{self.base_url}/chat/completions", json=body)

            if resp.status_code != 200:
                logger.debug("lm_studio_request_failed", status=resp.status_code, body=resp.text[:200])
                return None

            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not content:
                return None

            # Parse JSON (json_repair handles minor formatting issues)
            repaired = repair_json(content, return_objects=True)
            if isinstance(repaired, dict):
                return repaired

            logger.debug("lm_studio_json_repair_failed", content_preview=content[:100])
            return None

        except Exception as e:
            logger.debug("lm_studio_attempt_error", error=str(e))
            return None

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
