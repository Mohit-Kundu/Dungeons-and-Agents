"""No-tools Recap agent: compress prior summary + latest Turn into GameState.summary."""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.models import Model

from dnd_agent.domain.events import Event

RECAP_SYSTEM_PROMPT = """
You maintain a concise rolling Recap of a solo D&D Session for a returning player.

Rules:
- Write 2–5 short sentences in past tense.
- Preserve important facts: location changes, Checks/Saves and outcomes,
  Conditions, rests, quest progress, NPC names, and promises.
- Fold the prior Recap with the latest Turn; drop minor color that no longer matters.
- Do not invent facts that are not in the prior Recap or the latest Turn.
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
    player_text: str,
    narration: str,
    events: list[Event],
) -> str:
    mechanical = "\n".join(
        f"- {event.type}: {event.model_dump_json(exclude_none=True)}" for event in events
    ) or "- (none)"
    return (
        f"Prior Recap:\n{prior_summary.strip() or '(empty)'}\n\n"
        f"Latest Turn:\n"
        f"Player: {player_text.strip()}\n"
        f"DM: {narration.strip()}\n\n"
        f"Mechanical Events this Turn:\n{mechanical}\n\n"
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
        self._agent = build_recap_agent(model, retries=retries)

    async def generate(
        self,
        *,
        prior_summary: str,
        player_text: str,
        narration: str,
        events: list[Event],
    ) -> str:
        prompt = format_recap_prompt(
            prior_summary=prior_summary,
            player_text=player_text,
            narration=narration,
            events=events,
        )
        result = await self._agent.run(prompt)
        text = str(result.output).strip()
        if not text:
            raise ValueError("Recap model returned empty text")
        return text
