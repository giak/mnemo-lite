"""
Ollama Client — Native Ollama API client.

Uses Ollama's native /api/chat endpoint WITHOUT format parameter.
Relies on strong system prompts + json_repair for reliable JSON extraction.

This approach avoids the known bug where Ollama/LM Studio return JSON schemas
instead of actual data when format/response_format is specified.
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
    HTTP client for Ollama's native API.

    Uses /api/chat without format parameter for reliable JSON extraction.
    Supports automatic model fallback (4b → 2b) on failure.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        timeout: float = 120.0,
    ):
        self.base_url = (base_url or os.getenv("OLLAMA_URL", "http://ollama:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen3.5:4b")
        self.fallback_model = fallback_model or os.getenv("OLLAMA_FALLBACK_MODEL", "qwen3.5:2b")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._available: Optional[bool] = None
        self._current_model: str = self.model

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def is_available(self) -> bool:
        """Check if Ollama is running and model is available."""
        if self._available is not None:
            return self._available
        try:
            client = self._get_client()
            # Use native Ollama API to check models
            resp = await client.get(f"{self.base_url}/api/tags")
            if resp.status_code == 200:
                models = resp.json().get("models") or []
                model_names = [m.get("name", "") for m in models]
                # Check primary model first
                if any(self.model in name for name in model_names):
                    self._current_model = self.model
                    self._available = True
                    return True
                # Check fallback model
                if any(self.fallback_model in name for name in model_names):
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
        Extract structured JSON using Ollama's native API.

        Strategy:
        1. Try with strong system prompt + json_repair on primary model
        2. Retry with fallback model (2b if 4b fails)
        3. Return None if all attempts fail

        Note: We deliberately DO NOT use the 'format' parameter because
        Ollama/LM Studio have a known bug where they return JSON schemas
        instead of actual data when format is specified.
        """
        # Attempt 1: Primary model
        result = await self._attempt_extract(
            system_prompt, user_content, temperature,
            model=self._current_model,
        )
        if result is not None:
            return result

        # Attempt 2: Fallback model
        if self._current_model != self.fallback_model:
            logger.warning("ollama_switching_to_fallback", model=self.fallback_model)
            self._current_model = self.fallback_model
            result = await self._attempt_extract(
                system_prompt, user_content, temperature,
                model=self.fallback_model,
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
    ) -> Optional[Dict[str, Any]]:
        """Single attempt to extract JSON from Ollama using native API."""
        try:
            client = self._get_client()
            
            # Enhance system prompt to enforce JSON output
            enhanced_system_prompt = f"{system_prompt}\n\nIMPORTANT: Return ONLY valid JSON. No explanation, no markdown, no code blocks. Just the raw JSON object."
            
            body: Dict[str, Any] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": enhanced_system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": 2048,
                },
            }

            resp = await client.post(f"{self.base_url}/api/chat", json=body)

            if resp.status_code != 200:
                logger.debug("ollama_request_failed", status=resp.status_code, body=resp.text[:200])
                return None

            data = resp.json()
            content = data.get("message", {}).get("content", "")
            if not content:
                return None

            # Parse JSON with json_repair for robustness
            # Strip markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```", 2)[1]
                if content.startswith("json"):
                    content = content[4:]
            
            repaired = repair_json(content, return_objects=True)
            if isinstance(repaired, dict):
                return repaired

            logger.debug("ollama_json_repair_failed", content_preview=content[:100])
            return None

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
