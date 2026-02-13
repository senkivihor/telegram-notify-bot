"""AI service for estimating tailoring task time using Gemini."""

from __future__ import annotations

import json
from typing import Any, Dict

from google import genai
from google.genai import types

SYSTEM_PROMPT = (
    "You are an expert master tailor. A client will describe a garment repair "
    "or custom sewing task. Estimate the realistic time needed to complete this "
    "task in minutes. Reply ONLY in raw JSON format without markdown blocks. "
    'Format: {"task_summary": "string", "estimated_minutes": integer}.'
)

FALLBACK_MINUTES = 60
FALLBACK_SUMMARY = "Стандартна робота"


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
            raw = (response.text or "").strip()
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("Invalid payload")
            summary = str(payload.get("task_summary") or "").strip() or FALLBACK_SUMMARY
            minutes = int(payload.get("estimated_minutes"))
            if minutes <= 0:
                raise ValueError("Invalid minutes")
            return {"task_summary": summary, "estimated_minutes": minutes}
        except Exception:
            return {"task_summary": FALLBACK_SUMMARY, "estimated_minutes": FALLBACK_MINUTES}
