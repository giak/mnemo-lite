"""
Ollama Client — OpenAI-compatible client for Ollama.

Uses json_schema (preferred) with fallback to json_object + json_repair.
Supports automatic model fallback (4b → 2b) on OOM.
"""

import os
import json
from typing import Optional, Dict, Any

import httpx
import structlog
from json_repair import repair_json

logger = structlog.get_logger(__name__)


class OllamaClient:
    """
    HTTP client for Ollama's OpenAI-compatible API.

    Supports native json_schema for structured output with fallback
    to json_object + json_repair for maximum reliability.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = (base_url or os.getenv("OLLAMA_URL", "http://ollama:11434/v1")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen3.5:4b")
        self.fallback_model = fallback_model or os.getenv("OLLAMA_FALLBACK_MODEL", "qwen3.5:2b")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._available: Optional[bool] = None
        self._current_model: str = self.model

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=5.0),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def is_available(self) -> bool:
        """Check if Ollama is running and model is loaded."""
        if self._available is not None:
            return self._available
        try:
            client = self._get_client()
            resp = await client.get(f"{self.base_url}/models")
            if resp.status_code == 200:
                models = resp.json().get("data", [])
                model_ids = [m.get("id", "") for m in models]
                # Check primary model first
                if any(self.model in mid for mid in model_ids):
                    self._current_model = self.model
                    self._available = True
                    return True
                # Check fallback model
                if any(self.fallback_model in mid for mid in model_ids):
                    self._current_model = self.fallback_model
                    logger.warning("ollama_primary_model_missing", model=self.model)
                    self._available = True
                    return True
            self._available = False
            return False
        except Exception as e:
            self._available = False
            logger.debug("ollama_unavailable", error=str(e))
            return False

    async def extract_json(
        self,
        system_prompt: str,
        user_content: str,
        json_schema: Dict[str, Any],
        temperature: float = 0.1,
    ) -> Optional[Dict[str, Any]]:
        """
        Extract structured JSON using Ollama.

        Strategy:
        1. Try json_schema with primary model
        2. Fallback: json_object + json_repair with primary model
        3. Retry json_schema with fallback model (2b if 4b OOM)
        4. Return None if all attempts fail
        """
        # Attempt 1: json_schema with primary model
        result = await self._attempt_extract(
            system_prompt, user_content, temperature,
            model=self._current_model,
            response_format={"type": "json_schema", "json_schema": json_schema},
        )
        if result is not None:
            return result

        # Attempt 2: json_object + json_repair with primary model
        logger.debug("ollama_json_schema_failed", fallback="json_object")
        result = await self._attempt_extract(
            system_prompt, user_content, temperature,
            model=self._current_model,
            response_format={"type": "json_object"},
        )
        if result is not None:
            return result

        # Attempt 3: json_schema with fallback model
        if self._current_model != self.fallback_model:
            logger.warning("ollama_switching_to_fallback", model=self.fallback_model)
            self._current_model = self.fallback_model
            result = await self._attempt_extract(
                system_prompt, user_content, temperature,
                model=self.fallback_model,
                response_format={"type": "json_schema", "json_schema": json_schema},
            )
            if result is not None:
                return result

        logger.warning("ollama_extraction_failed", system_prompt=system_prompt[:50])
        return None

    async def _attempt_extract(
        self,
        system_prompt: str,
        user_content: str,
        temperature: float,
        model: str,
        response_format: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Single attempt to extract JSON from Ollama."""
        try:
            client = self._get_client()
            body: Dict[str, Any] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "temperature": temperature,
                "max_tokens": 2048,
                "stream": False,
            }
            if response_format:
                body["response_format"] = response_format

            resp = await client.post(f"{self.base_url}/chat/completions", json=body)

            if resp.status_code != 200:
                logger.debug("ollama_request_failed", status=resp.status_code, body=resp.text[:200])
                return None

            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not content:
                return None

            # If json_object was used, parse with json_repair
            if response_format and response_format.get("type") == "json_object":
                repaired = repair_json(content, return_objects=True)
                if isinstance(repaired, dict):
                    return repaired
                logger.debug("ollama_json_repair_failed", content_preview=content[:100])
                return None

            # json_schema should return valid JSON directly
            return json.loads(content)

        except json.JSONDecodeError as e:
            logger.debug("ollama_json_decode_error", error=str(e))
            return None
        except Exception as e:
            logger.debug("ollama_attempt_error", error=str(e))
            return None

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
