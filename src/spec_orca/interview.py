"""Interview agent for interactive requirements gathering.

The InterviewAgent wraps a backend and positions the AI as an interviewer
that helps users articulate their goals and requirements.

The conversation follows a structured flow:
1. Ask the user what they want to write/achieve (scoping).
2. Offer a binary choice: analyse for improvements vs. follow the user's path.
3. Branch the conversation depending on the choice.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from spec_orca.backend import Backend

__all__ = ["InterviewAgent", "InterviewConfig", "InterviewPhase"]

INTERVIEWER_PERSONA = (
    "You are an expert requirements-gathering interviewer for a software project. "
    "Your role is to help the user clearly articulate their goals, constraints, and "
    "acceptance criteria. Ask focused, open-ended questions one at a time. Summarise "
    "what you have learned so far before asking the next question. When you have "
    "enough information, produce a concise summary of the requirements."
)

SCOPING_QUESTION = "What do you want to write or achieve?"

CHOICE_QUESTION = (
    "Do you want me to analyze and find areas of improvement, "
    "or do you have a specific path in mind?"
)

IMPROVEMENT_PROMPT = (
    "The user chose 'Improvement'. Analyse the context and files in the project, "
    "and suggest concrete enhancements or areas of improvement. "
    "Ask any clarifying questions if needed."
)

OWN_PATH_PROMPT = (
    "The user chose their own specific path. Follow the user's lead to detail "
    "their specific request. Ask clarifying questions to flesh out the requirements."
)


class InterviewPhase(enum.Enum):
    """Tracks the current phase of the interview conversation."""

    SCOPING = "scoping"
    CHOICE = "choice"
    IMPROVEMENT = "improvement"
    OWN_PATH = "own_path"


@dataclass(frozen=True)
class InterviewConfig:
    """Configuration for an interview session."""

    persona: str = INTERVIEWER_PERSONA
    repo_path: Path = field(default_factory=Path.cwd)


class InterviewAgent:
    """Agent that conducts an interactive interview using a backend.

    The agent wraps user input with an interviewer persona so the backend
    responds as a requirements-gathering interviewer.  The conversation
    follows a structured flow: scoping -> binary choice -> branched dialogue.
    """

    def __init__(self, backend: Backend, config: InterviewConfig | None = None) -> None:
        self._backend = backend
        self._config = config or InterviewConfig()
        self._history: list[tuple[str, str]] = []
        self._phase: InterviewPhase = InterviewPhase.SCOPING

    @property
    def persona(self) -> str:
        """Return the interviewer persona prompt."""
        return self._config.persona

    @property
    def phase(self) -> InterviewPhase:
        """Return the current conversation phase."""
        return self._phase

    @property
    def history(self) -> list[tuple[str, str]]:
        """Return conversation history as (user_input, agent_response) pairs."""
        return list(self._history)

    def greeting(self) -> str:
        """Return the initial scoping question to kick off the interview."""
        return SCOPING_QUESTION

    def send(self, user_input: str) -> str:
        """Send user input to the backend and return the agent's textual response.

        The behaviour depends on the current conversation phase:

        * **SCOPING** - the user's first answer describes their goal.  The agent
          records it and responds with the binary choice question.
        * **CHOICE** - the user picks "improvement" or "own path".  The agent
          branches accordingly and sends the first backend query.
        * **IMPROVEMENT / OWN_PATH** - free-form follow-up conversation routed
          through the backend.
        """
        if self._phase == InterviewPhase.SCOPING:
            return self._handle_scoping(user_input)
        if self._phase == InterviewPhase.CHOICE:
            return self._handle_choice(user_input)
        # IMPROVEMENT or OWN_PATH — delegate to backend
        return self._send_to_backend(user_input)

    # ------------------------------------------------------------------
    # Phase handlers
    # ------------------------------------------------------------------

    def _handle_scoping(self, user_input: str) -> str:
        """Record the user's goal and present the binary choice."""
        self._history.append((user_input, CHOICE_QUESTION))
        self._phase = InterviewPhase.CHOICE
        return CHOICE_QUESTION

    def _handle_choice(self, user_input: str) -> str:
        """Branch the conversation based on the user's choice."""
        normalised = user_input.strip().lower()
        if _is_improvement_choice(normalised):
            self._phase = InterviewPhase.IMPROVEMENT
            return self._send_to_backend_with_context(user_input, IMPROVEMENT_PROMPT)
        # Default to own-path for any other answer
        self._phase = InterviewPhase.OWN_PATH
        return self._send_to_backend_with_context(user_input, OWN_PATH_PROMPT)

    # ------------------------------------------------------------------
    # Backend interaction
    # ------------------------------------------------------------------

    def _send_to_backend(self, user_input: str) -> str:
        """Forward a message to the backend and return its textual response."""
        prompt = self._build_prompt(user_input)
        response = self._backend.chat(prompt, cwd=self._config.repo_path)
        self._history.append((user_input, response))
        return response

    def _send_to_backend_with_context(self, user_input: str, extra_context: str) -> str:
        """Forward a message to the backend with additional context injected."""
        prompt = self._build_prompt(user_input, extra_context=extra_context)
        response = self._backend.chat(prompt, cwd=self._config.repo_path)
        self._history.append((user_input, response))
        return response

    def generate_spec_yaml(self) -> str:
        """Compile gathered requirements into a valid spec YAML string.

        Extracts the goal from the first user message (scoping phase) and
        builds one spec entry per subsequent conversation exchange, using
        interviewer responses as acceptance criteria.  Returns a YAML string
        conforming to the SpecOrca spec format.
        """
        goal = self._extract_goal()
        specs = self._build_spec_entries()
        data: dict[str, Any] = {"goal": goal, "specs": specs}
        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    def save_spec(self, path: Path) -> Path:
        """Write the generated spec YAML to *path* and return its resolved path."""
        resolved = path.resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(self.generate_spec_yaml(), encoding="utf-8")
        return resolved

    # ------------------------------------------------------------------
    # Spec generation helpers
    # ------------------------------------------------------------------

    def _extract_goal(self) -> str:
        """Return the user's goal from the first exchange, or a fallback."""
        if self._history:
            return self._history[0][0]
        return "Unspecified goal"

    def _build_spec_entries(self) -> list[dict[str, Any]]:
        """Build a list of spec entry dicts from conversation history."""
        entries: list[dict[str, Any]] = []
        # Skip the first exchange (scoping) — it becomes the goal.
        # Remaining exchanges become specs.
        exchanges = self._history[1:] if len(self._history) > 1 else self._history
        if not exchanges:
            return [_placeholder_spec_entry()]
        for idx, (user_input, agent_response) in enumerate(exchanges, start=1):
            spec_id = f"spec-{idx}"
            title = _truncate(user_input, 60)
            criteria = _extract_criteria(agent_response)
            entries.append(
                {
                    "id": spec_id,
                    "title": title,
                    "description": user_input,
                    "acceptance_criteria": criteria if criteria else ["TODO: add criterion"],
                    "dependencies": [],
                }
            )
        return entries

    def _build_prompt(self, user_input: str, *, extra_context: str = "") -> str:
        """Combine persona, conversation history, and current user input."""
        parts: list[str] = [self._config.persona, ""]
        if extra_context:
            parts.append(extra_context)
            parts.append("")
        for prev_input, prev_response in self._history:
            parts.append(f"User: {prev_input}")
            parts.append(f"Interviewer: {prev_response}")
            parts.append("")
        parts.append(f"User: {user_input}")
        parts.append("")
        parts.append(
            "Respond as the interviewer. Ask a clarifying question or "
            "summarise the requirements gathered so far."
        )
        return "\n".join(parts)


def _is_improvement_choice(text: str) -> bool:
    """Return True when the user's input signals the 'improvement' branch."""
    keywords = {"improvement", "improvements", "improve", "analyze", "analyse", "areas"}
    return any(kw in text for kw in keywords)


def _truncate(text: str, length: int) -> str:
    """Return *text* truncated to *length* characters with an ellipsis if needed."""
    collapsed = " ".join(text.split())
    if len(collapsed) <= length:
        return collapsed
    return collapsed[: length - 3] + "..."


def _extract_criteria(response: str) -> list[str]:
    """Extract bullet-point items from an agent response as acceptance criteria.

    Looks for lines starting with ``-`` or ``*`` (Markdown lists).  Falls back
    to using the first sentence of the response.
    """
    bullets: list[str] = []
    for line in response.splitlines():
        stripped = line.strip()
        match = re.match(r"^[-*]\s+(.+)$", stripped)
        if match:
            bullets.append(match.group(1).strip())
    if bullets:
        return bullets
    # Fallback: use the whole response as a single criterion (truncated).
    text = " ".join(response.split()).strip()
    if text:
        return [_truncate(text, 120)]
    return []


def _placeholder_spec_entry() -> dict[str, Any]:
    """Return a placeholder spec entry for when no exchanges occurred."""
    return {
        "id": "spec-1",
        "title": "TODO: describe first task",
        "description": "",
        "acceptance_criteria": ["TODO: add criterion"],
        "dependencies": [],
    }
