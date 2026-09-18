"""Orchestration of operator note interpretation with guardrail validation."""

from app.schemas.request import BatterySpecs
from app.schemas.directives import DirectiveInterpretationItem
from app.llm.client import LLMClient, llm_client
from app.guardrails.validator import validate_directive_interpretations


class DirectiveInterpreter:
    """Orchestrates LLM interpretation and deterministic guardrails."""

    def __init__(self, client: LLMClient = llm_client) -> None:
        self.client = client

    async def interpret_and_validate(
        self,
        operator_notes: list[str],
        battery: BatterySpecs,
    ) -> list[DirectiveInterpretationItem]:
        """
        Interprets operator notes via LLM/fallback and executes deterministic guardrails.
        """
        raw_interpretations = await self.client.interpret_notes(operator_notes, battery)
        validated_interpretations = validate_directive_interpretations(
            raw_interpretations, len(operator_notes), battery
        )
        return validated_interpretations


directive_interpreter = DirectiveInterpreter()
