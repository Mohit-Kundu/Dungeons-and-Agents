"""No-tools Recap agent: compress prior summary + pending Turns into GameState.summary."""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models import Model

RECAP_SYSTEM_PROMPT = """
You maintain a concise rolling Recap of a solo D&D Session for a returning player.

Rules:
- Write 2–5 short sentences in past tense.
- Preserve important facts: location changes, Checks/Saves and outcomes,
  Conditions, rests, quest progress, NPC names, and promises.
- Fold the prior Recap with the pending Turns; drop minor color that no longer matters.
- Do not invent facts that are not in the prior Recap or the pending Turns.
- Do not address the player with instructions; output only the Recap prose.
""".strip()


def build_recap_agent(model: Model | str, *, retries: int = 1) -> Agent[None, str]:
    return Agent(
        model,
        system_prompt=RECAP_SYSTEM_PROMPT,
        retries=retries,
    )


def format_recap_prompt(
    *,
    prior_summary: str,
    turns: list[dict[str, Any]],
) -> str:
    if not turns:
        pending = "- (none)"
    else:
        blocks: list[str] = []
        for turn in turns:
            blocks.append(
                f"Turn {turn['turn_number']}:\n"
                f"Player: {str(turn['player_text']).strip()}\n"
                f"DM: {str(turn['narration']).strip()}"
            )
        pending = "\n\n".join(blocks)
    return (
        f"Prior Recap:\n{prior_summary.strip() or '(empty)'}\n\n"
        f"Pending successful Turns:\n{pending}\n\n"
        "Write the updated Recap."
    )


class RecapService:
    """Generate Session Recap text with a no-tools model call."""

    def __init__(
        self,
        model: Model | str,
        *,
        retries: int = 1,
    ) -> None:
        from dnd_agent.telemetry.meter import meter_model

        wrapped: Model | str = meter_model(model, role="recap") if isinstance(model, Model) else model
        self._agent = build_recap_agent(wrapped, retries=retries)

    async def generate(
        self,
        *,
        prior_summary: str,
        turns: list[dict[str, Any]],
    ) -> str:
        prompt = format_recap_prompt(prior_summary=prior_summary, turns=turns)
        result = await self._agent.run(prompt)
        text = str(result.output).strip()
        if not text:
            raise ValueError("Recap model returned empty text")
        return text
