"""AI service for estimating tailoring task time using Gemini."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from google import genai
from google.genai import types

SYSTEM_PROMPT = (
    "You are an expert tailor. A client will describe a sewing task. "
    "Estimate time in minutes. Reply ONLY in raw JSON: "
    '{"task_summary": "string", "estimated_minutes": int}. NO Markdown. '
    "If the request is a joke or not about tailoring (e.g., 'do nothing', 'prices'), "
    'return: {"task_summary": "Некоректний запит", "estimated_minutes": 0}.'
)

FALLBACK_MINUTES = 60
FALLBACK_SUMMARY = "Стандартна робота"

logger = logging.getLogger("AIService")


def _strip_code_fences(text: str) -> str:
    if not text:
        return ""
    cleaned = text.replace("```json", "").replace("```", "")
    return cleaned.strip()


class AIService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.enabled = bool(api_key)
        self.client = None
        if self.enabled:
            self.client = genai.Client(api_key=api_key)

    def analyze_tailoring_task(self, user_text: str) -> Dict[str, Any]:
        if not self.enabled or not user_text:
            return {"task_summary": FALLBACK_SUMMARY, "estimated_minutes": FALLBACK_MINUTES}
        try:
            response = self.client.models.generate_content(
                model="gemini-1.5-flash",
                contents=user_text,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
            )
            raw_text = (response.text or "").strip()
            logger.info("Raw Gemini Output: %s", raw_text)
            raw = _strip_code_fences(raw_text)
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("Invalid payload")
            summary = str(payload.get("task_summary") or "").strip() or FALLBACK_SUMMARY
            minutes = int(payload.get("estimated_minutes"))
            return {"task_summary": summary, "estimated_minutes": minutes}
        except Exception as exc:
            logger.error("Failed to parse Gemini output: %s | Raw: %s", exc, raw_text if "raw_text" in locals() else "")
            return {"task_summary": FALLBACK_SUMMARY, "estimated_minutes": FALLBACK_MINUTES}
