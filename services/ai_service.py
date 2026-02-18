"""AI service for estimating tailoring task time using Gemini."""

from __future__ import annotations

import json
import logging
import math
import os
import re
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
    "A client will describe a task in Ukrainian.\n\n"
    "REFERENCE BASELINE TIMES (Use these as your anchors):\n"
    "{baseline_times}\n"
    "   - Skirt (Simple): ~240 min (4 hours)\n"
    "   - Pants/Trousers: ~480-600 min (8-10 hours)\n"
    "   - Coat/Jacket (Lined): ~1440-2400 min (24-40 hours)\n\n"
    "LOGIC RULES (Strict Priority):\n"
    "1. Adjectives Matter: If the user describes the item as 'Simple' (Проста), 'Basic' (Базова), or 'Light', you MUST choose the lower time estimate.\n"  # noqa: E501
    "2. Keywords Mapping:\n"
    "   - 'Simple', 'Basic', 'Summer' -> Lean towards _simple.\n"
    "   - 'Complex', 'Evening', 'Wedding', 'Lined', 'Winter' -> Lean towards _complex.\n"
    "3. Ambiguity: If the user creates a conflict, assume the simpler option but add ~20% buffer.\n\n"
    "CONTEXT MULTIPLIERS (Apply these to the Baseline):\n"
    "1. SIZE / SCALE:\n"
    "   - 'Baby', 'Child', 'Kids' (Дитяче): REDUCE time by 20% (0.8x).\n"
    "   - 'Maxi', 'Floor length' (Довга): INCREASE time by 15% (1.15x).\n"
    "2. FABRIC / MATERIAL (The 'Flags'):\n"
    "   - Standard (Cotton, Denim, Wool): No change.\n"
    "   - Difficult (Silk, Chiffon, Velvet) (Шовк, Оксамит): INCREASE time by 30% (1.3x).\n"
    "   - Extreme (Sequins, Leather, Fur) (Шкіра, Хутро): INCREASE time by 50% (1.5x).\n"
    "3. CONSTRUCTION:\n"
    "   - 'Lined' (На підкладці): Add 20-30% to base time (if not already a coat).\n\n"
    "ONE-SHOT EXAMPLES (Training):\n"
    "- User: 'Simple evening dress' -> Base: make_dress_simple (480) -> Result: 480 min.\n"
    "- User: 'Winter coat' (Зимове пальто) -> Base: make_coat_complex (~2400 min).\n"
    "- User: 'Pencil skirt' (Спідниця олівець) -> Base: make_skirt_simple (~240-300 min).\n"
    "- User: 'Men's suit trousers' -> Base: make_pants (~600 min).\n"
    "- User: 'Baby dress' -> Base: make_dress_simple (480) * 0.8 (Size) -> Result: ~385 min.\n\n"
    "INSTRUCTIONS:\n"
    "1. Identify the Core Task (Dress, Skirt, Coat, Repair).\n"
    "2. Identify Modifiers (Size, Fabric, Complexity).\n"
    "3. Calculate: Baseline * Modifiers = Final Estimate.\n"
    "4. OUTPUT: Return ONLY raw JSON (no markdown):\n"
    "   {{"
    '      "task_summary": "Concise description in UKRAINIAN including modifiers", '
    '      "estimated_minutes": integer'
    "   }}\n\n"
    "If the request is unrelated to tailoring, return minutes: 0."
)

FALLBACK_MINUTES = 60
FALLBACK_SUMMARY = "Стандартна робота"
AI_UNAVAILABLE_RESULT = {"task_summary": "AI Unavailable", "estimated_minutes": 0}
AI_DISCLAIMER = (
    "\n\n💡 *Важливо:* Це орієнтовний розрахунок. "
    "Точну вартість визначить майстриня при зустрічі, "
    "врахувавши всі деталі та тканину. ✂️"
)

logger = logging.getLogger("AIService")

ContentType = str | types.Content | list[types.Content]


def _strip_code_fences(text: str) -> str:
    if not text:
        return ""
    cleaned = text.replace("```json", "").replace("```", "")
    return cleaned.strip()


def _parse_json_response(raw_text: str) -> Dict[str, Any]:
    cleaned = _strip_code_fences(raw_text)
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        json_str = match.group(0)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            logger.error("Regex found JSON but parse failed: %s", json_str)
            return json.loads(cleaned)
    logger.warning("No JSON braces found via Regex. Attempting raw parse.")
    return json.loads(cleaned)


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


def format_business_time(minutes: int) -> str:
    """
    Converts minutes into a friendly string.
    Assumption: 1 Work Day = 8 Hours.
    """
    if minutes < 60:
        return f"{minutes} хв"

    hours = minutes // 60
    remaining_mins = minutes % 60

    # If it's a small task (< 8 hours), just show hours
    if hours < 8:
        if remaining_mins > 0:
            return f"{minutes} хв ({hours} год {remaining_mins} хв)"
        return f"{minutes} хв ({hours} год)"

    # If it's a large task (> 8 hours), show Work Days
    days = hours // 8
    rest_hours = hours % 8

    time_str = f"{days} дн"
    if rest_hours > 0:
        time_str += f" {rest_hours} год"

    return f"{minutes} хв (~{time_str} роб. часу)"


def calculate_price_range(base_price: float) -> tuple[int, int]:
    """
    Returns a (min, max) tuple.
    Logic: +/- 20% spread, rounded to nearest 50 UAH for clean numbers.
    """
    if base_price == 0:
        return 0, 0

    min_price = math.floor((base_price * 0.8) / 50) * 50
    min_price = max(50, min_price)

    max_price = math.ceil((base_price * 1.2) / 50) * 50

    return int(min_price), int(max_price)


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
                temperature=0.1,
                response_mime_type="application/json",
                system_instruction=self.system_prompt,
            )
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=user_text,
                config=config,
            )
            raw_text = (response.text or "").strip()
            logger.info("Raw Gemini Output: %s", raw_text)
            payload = _parse_json_response(raw_text)
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
                    temperature=0.1,
                    response_mime_type="application/json",
                    system_instruction=self.system_prompt,
                )
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=user_text,
                    config=fallback_config,
                )
                raw_text = (response.text or "").strip()
                logger.info("Raw Gemini Output (Fallback): %s", raw_text)
                payload = _parse_json_response(raw_text)
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
