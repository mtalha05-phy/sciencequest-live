"""
Quark AI Science Companion for ScienceQuest Live.
Generates contextual, tiered scientific explanations leveraging OpenAI API
with zero-downtime curated local fallback.
"""

from typing import Dict, Any, Optional
import os
import logging
import httpx

from app.ai.fallback_knowledge import get_curated_explanation

logger = logging.getLogger("sciencequest.quark")


class QuarkCompanion:
    """Manages conversational explanations, question answering, and explanation tiers."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.current_explanation_level: str = "SCIENTIST"  # "EXPLORER", "SCIENTIST", "RESEARCHER"

    def set_explanation_level(self, level: str) -> bool:
        norm = level.strip().upper()
        if norm in ("EXPLORER", "SCIENTIST", "RESEARCHER"):
            self.current_explanation_level = norm
            return True
        return False

    async def explain_active_experiment(
        self,
        mission_id: str,
        mission_title: str,
        current_params: Dict[str, Any],
        physics_result: Dict[str, Any],
        level: Optional[str] = None,
    ) -> str:
        tier = (level or self.current_explanation_level).upper()

        # If no OpenAI API key is configured, instantly return high-grade curated scientific text
        if not self.api_key:
            return get_curated_explanation(mission_id, tier)

        prompt = (
            f"Explain the ongoing experiment '{mission_title}' to the audience.\n"
            f"Current Parameters: {current_params}\n"
            f"Physics Calculations from Engine: {physics_result}\n"
            f"Explanation Tier: {tier}\n"
            f"Highlight why classical mechanics and quantum mechanics differ here."
        )
        return await self._call_ai(prompt, mission_id, tier, current_params, physics_result)

    async def answer_user_question(
        self,
        question: str,
        mission_id: str,
        mission_title: str,
        current_params: Dict[str, Any],
        physics_result: Dict[str, Any],
        level: Optional[str] = None,
    ) -> str:
        tier = (level or self.current_explanation_level).upper()

        if not self.api_key:
            # Curated response plus direct answer acknowledgment
            base = get_curated_explanation(mission_id, tier)
            return f"BEEP! Regarding your question '{question}': {base}"

        prompt = (
            f"A livestream viewer asks: '{question}'\n"
            f"Active Experiment: '{mission_title}' ({mission_id})\n"
            f"Active Simulation Parameters: {current_params}\n"
            f"Exact Physics Engine Output: {physics_result}\n"
            f"Target Explanation Level: {tier}\n"
            f"Answer accurately based on the physics engine data and the physical principles involved."
        )
        return await self._call_ai(prompt, mission_id, tier, current_params, physics_result)

    async def _call_ai(
        self,
        user_prompt: str,
        mission_id: str,
        tier: str,
        params: Dict[str, Any],
        physics_result: Dict[str, Any],
    ) -> str:
        system_instructions = (
            "You are Quark, a friendly, enthusiastic, and scientifically rigorous AI robot science companion "
            "for the livestream game 'ScienceQuest Live'.\n"
            "Rules you must strictly follow:\n"
            "1. The physics engine is the sole source of numerical truth. Never fabricate experimental results "
            "or contradict the simulation results provided.\n"
            "2. Adapt your tone strictly to the requested Tier:\n"
            "   - EXPLORER: Friendly, playful, fun analogies, simple vocabulary, no complex math.\n"
            "   - SCIENTIST: Precise physical terminology, parameter effects, equations in words, graph interpretation.\n"
            "   - RESEARCHER: Mathematical wave equations, boundary conditions, Hamiltonian operators, formal limits.\n"
            "3. Keep responses engaging and concise (2 to 4 sentences) so they fit nicely in a livestream chat overlay.\n"
            "4. Distinguish models from physical reality and distinguish probabilities from individual measurement clicks."
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.4,
            "max_tokens": 250,
        }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    logger.warning(f"OpenAI API error {resp.status_code}: {resp.text}. Falling back to local knowledge.")
                    return get_curated_explanation(mission_id, tier)
        except Exception as e:
            logger.warning(f"AI request exception: {e}. Falling back to local knowledge.")
            return get_curated_explanation(mission_id, tier)
