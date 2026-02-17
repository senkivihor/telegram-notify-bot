"""AI service for estimating tailoring task time using Gemini."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from google import genai
from google.genai import types

try:
    from google.genai import errors as genai_errors
except ImportError:  # Fallback for environments without google.genai errors module.
    genai_errors = None

SYSTEM_PROMPT_TEMPLATE = (
    "You are an expert master tailor. A client will describe a sewing or custom tailoring task.\n"
    "Estimate the REALISTIC ACTIVE WORK TIME (Billable Minutes) needed to complete this task.\n"
    "Include time for drafting patterns, cutting, sewing, and client fittings.\n"
    "Do NOT include 'waiting' time (e.g., waiting for fabric).\n\n"
    "Examples for guidance:\n"
    "- Hemming jeans: 30 min\n"
    "- Simple dress (scratch): ~960 min (16 hours)\n"
    "- Complex/Evening dress: ~2400-4800 min\n"
    "- Wedding dress: ~9600 min\n\n"
    "A client will describe a task in Ukrainian.\n\n"
    "REFERENCE BASELINE TIMES (Use these as your anchor):\n"
    "{baseline_times}\n\n"
    "INSTRUCTIONS:\n"
    "1. Analyze the user's request.\n"
    "2. Compare it to the Reference Baselines above to find the closest match.\n"
    "3. Adjust the time if the user describes extra complexity (e.g., 'velvet fabric' or 'urgent').\n"
    "4. OUTPUT: Return ONLY raw JSON (no markdown):\n"
    '{{"task_summary": "Short description in UKRAINIAN", "estimated_minutes": integer}}\n\n'
    "If the request is unrelated to tailoring, return minutes: 0."
)

FALLBACK_MINUTES = 60
FALLBACK_SUMMARY = "Стандартна робота"
AI_UNAVAILABLE_RESULT = {"task_summary": "AI Unavailable", "estimated_minutes": 0}

logger = logging.getLogger("AIService")

ContentType = str | types.Content | list[types.Content]


def _strip_code_fences(text: str) -> str:
    if not text:
        return ""
    cleaned = text.replace("```json", "").replace("```", "")
    return cleaned.strip()


def _format_baseline_times() -> str:
    raw_json = os.getenv("SERVICE_COMPLEXITY", "{}")
    logger.info("DEBUG: Raw SERVICE_COMPLEXITY: '%s'", raw_json)
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        logger.error(
            "CRITICAL: Failed to parse SERVICE_COMPLEXITY. Raw value: %s. Error: %s",
            raw_json,
            exc,
        )
        data = {}
    if not isinstance(data, dict):
        logger.error("SERVICE_COMPLEXITY must be a JSON object.")
        return ""
    lines = []
    for key, value in data.items():
        lines.append(f"- {key}: {value} min")
    return "\n".join(lines)


class AIService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        api_key_value = os.getenv("GEMINI_API_KEY") or api_key
        self.enabled = bool(api_key_value)
        self.client = None
        self.baseline_times = _format_baseline_times()
        self.system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            baseline_times=self.baseline_times or "(no baselines provided)"
        )
        if self.enabled:
            self.client = genai.Client(api_key=api_key_value)

    def analyze_tailoring_task(self, user_text: str) -> Dict[str, Any]:
        if not self.enabled or not user_text or not self.client:
            return AI_UNAVAILABLE_RESULT
        client_error = getattr(genai_errors, "ClientError", Exception)
        raw_text = ""
        try:
            config = types.GenerateContentConfig(
                system_instruction=self.system_prompt,
                temperature=0.2,  # Low temperature ensures the AI picks the most likely baseline time and doesn't hallucinate random numbers. # noqa: E501
                top_p=0.8,
                top_k=40,
                max_output_tokens=100,
                response_mime_type="application/json",
            )
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=user_text,
                config=config,
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
        except (client_error, Exception):
            logger.error(
                "AI Service Error. Full Raw Output: %s",
                raw_text,
                exc_info=True,
            )
            try:
                fallback_config = types.GenerateContentConfig(
                    system_instruction=self.system_prompt,
                    temperature=0.2,  # Low temperature ensures the AI picks the most likely baseline time and doesn't hallucinate random numbers. # noqa: E501
                    top_p=0.8,
                    top_k=40,
                    max_output_tokens=100,
                    response_mime_type="application/json",
                )
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=user_text,
                    config=fallback_config,
                )
                raw_text = (response.text or "").strip()
                logger.info("Raw Gemini Output (Fallback): %s", raw_text)
                raw = _strip_code_fences(raw_text)
                payload = json.loads(raw)
                if not isinstance(payload, dict):
                    raise ValueError("Invalid payload")
                summary = str(payload.get("task_summary") or "").strip() or FALLBACK_SUMMARY
                minutes = int(payload.get("estimated_minutes"))
                return {"task_summary": summary, "estimated_minutes": minutes}
            except Exception:
                logger.error(
                    "AI Service Fallback Error. Full Raw Output: %s",
                    raw_text,
                    exc_info=True,
                )
                return AI_UNAVAILABLE_RESULT
