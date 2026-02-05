"""Tests for the InterviewAgent."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from spec_orca.backends.mock import MockBackend, MockBackendConfig
from spec_orca.interview import (
    CHOICE_QUESTION,
    IMPROVEMENT_PROMPT,
    INTERVIEWER_PERSONA,
    OWN_PATH_PROMPT,
    SCOPING_QUESTION,
    InterviewAgent,
    InterviewConfig,
    InterviewPhase,
)
from spec_orca.models import ResultStatus


class TestInterviewAgent:
    """Core InterviewAgent tests."""

    def test_persona_default(self) -> None:
        backend = MockBackend()
        agent = InterviewAgent(backend)
        assert agent.persona == INTERVIEWER_PERSONA

    def test_persona_custom(self) -> None:
        backend = MockBackend()
        config = InterviewConfig(persona="Custom persona")
        agent = InterviewAgent(backend, config)
        assert agent.persona == "Custom persona"

    def test_initial_phase_is_scoping(self) -> None:
        backend = MockBackend()
        agent = InterviewAgent(backend)
        assert agent.phase == InterviewPhase.SCOPING

    def test_greeting_returns_scoping_question(self) -> None:
        backend = MockBackend()
        agent = InterviewAgent(backend)
        assert agent.greeting() == SCOPING_QUESTION

    def test_send_returns_text(self) -> None:
        config = MockBackendConfig(summary="What is your goal?")
        backend = MockBackend(config=config)
        agent = InterviewAgent(backend)
        # First send goes through scoping -> returns the binary choice
        response = agent.send("I want to build a web app")
        assert response == CHOICE_QUESTION

    def test_send_calls_backend_execute(self) -> None:
        backend = MockBackend()
        agent = InterviewAgent(backend)
        # Advance past scoping and choice to reach backend-backed phase
        agent.send("I want a REST API")
        with mock.patch.object(backend, "execute", wraps=backend.execute) as mocked:
            agent.send("I have a specific path")
            mocked.assert_called_once()

    def test_send_includes_persona_in_description(self) -> None:
        backend = MockBackend()
        agent = InterviewAgent(backend)
        agent.send("I need a REST API")  # scoping
        with mock.patch.object(backend, "execute", wraps=backend.execute) as mocked:
            agent.send("own path")  # choice -> own_path, hits backend
            spec = mocked.call_args[0][0]
            assert INTERVIEWER_PERSONA in spec.description

    def test_send_includes_user_input_in_description(self) -> None:
        backend = MockBackend()
        agent = InterviewAgent(backend)
        agent.send("Build a CLI tool")  # scoping
        with mock.patch.object(backend, "execute", wraps=backend.execute) as mocked:
            agent.send("my own path please")  # choice
            spec = mocked.call_args[0][0]
            assert "my own path please" in spec.description

    def test_history_tracks_exchanges(self) -> None:
        config = MockBackendConfig(summary="Tell me more")
        backend = MockBackend(config=config)
        agent = InterviewAgent(backend)
        agent.send("first message")  # scoping -> CHOICE_QUESTION
        agent.send("improvement")  # choice -> hits backend
        assert len(agent.history) == 2
        assert agent.history[0] == ("first message", CHOICE_QUESTION)
        assert agent.history[1][0] == "improvement"

    def test_history_is_copy(self) -> None:
        backend = MockBackend()
        agent = InterviewAgent(backend)
        agent.send("hello")
        history = agent.history
        history.clear()
        assert len(agent.history) == 1

    def test_second_send_includes_history_in_prompt(self) -> None:
        config = MockBackendConfig(summary="Noted")
        backend = MockBackend(config=config)
        agent = InterviewAgent(backend)
        agent.send("first")  # scoping
        agent.send("improvement")  # choice -> IMPROVEMENT phase
        with mock.patch.object(backend, "execute", wraps=backend.execute) as mocked:
            agent.send("more details")  # follow-up in IMPROVEMENT phase
            spec = mocked.call_args[0][0]
            assert "User: first" in spec.description
            assert "User: more details" in spec.description

    def test_send_with_failure_result(self) -> None:
        config = MockBackendConfig(status=ResultStatus.FAILURE, summary="Error occurred")
        backend = MockBackend(config=config)
        agent = InterviewAgent(backend)
        # scoping phase doesn't hit backend, so advance
        agent.send("something")
        response = agent.send("improvement")  # hits backend
        assert response == "Error occurred"

    def test_config_default_repo_path(self) -> None:
        config = InterviewConfig()
        assert isinstance(config.repo_path, Path)


class TestInterviewConversationFlow:
    """Tests for the structured conversation flow."""

    def test_scoping_phase_returns_choice_question(self) -> None:
        backend = MockBackend()
        agent = InterviewAgent(backend)
        response = agent.send("I want to build a CLI tool")
        assert response == CHOICE_QUESTION
        assert agent.phase == InterviewPhase.CHOICE

    def test_choice_improvement_sets_phase(self) -> None:
        config = MockBackendConfig(summary="Here are some improvements")
        backend = MockBackend(config=config)
        agent = InterviewAgent(backend)
        agent.send("I want to build a web app")
        agent.send("improvement")
        assert agent.phase == InterviewPhase.IMPROVEMENT

    def test_choice_own_path_sets_phase(self) -> None:
        config = MockBackendConfig(summary="Tell me more about your path")
        backend = MockBackend(config=config)
        agent = InterviewAgent(backend)
        agent.send("I want to build a web app")
        agent.send("I have a specific path in mind")
        assert agent.phase == InterviewPhase.OWN_PATH

    def test_improvement_branch_includes_improvement_prompt(self) -> None:
        backend = MockBackend()
        agent = InterviewAgent(backend)
        agent.send("I want to refactor")
        with mock.patch.object(backend, "execute", wraps=backend.execute) as mocked:
            agent.send("analyze and find improvements")
            spec = mocked.call_args[0][0]
            assert IMPROVEMENT_PROMPT in spec.description

    def test_own_path_branch_includes_own_path_prompt(self) -> None:
        backend = MockBackend()
        agent = InterviewAgent(backend)
        agent.send("I want to add auth")
        with mock.patch.object(backend, "execute", wraps=backend.execute) as mocked:
            agent.send("I know exactly what I want")
            spec = mocked.call_args[0][0]
            assert OWN_PATH_PROMPT in spec.description

    def test_improvement_followup_hits_backend(self) -> None:
        config = MockBackendConfig(summary="suggestion")
        backend = MockBackend(config=config)
        agent = InterviewAgent(backend)
        agent.send("build a service")
        agent.send("improvement")
        with mock.patch.object(backend, "execute", wraps=backend.execute) as mocked:
            response = agent.send("tell me more")
            mocked.assert_called_once()
        assert response == "suggestion"
        assert agent.phase == InterviewPhase.IMPROVEMENT

    def test_own_path_followup_hits_backend(self) -> None:
        config = MockBackendConfig(summary="got it")
        backend = MockBackend(config=config)
        agent = InterviewAgent(backend)
        agent.send("build a service")
        agent.send("my own path")
        with mock.patch.object(backend, "execute", wraps=backend.execute) as mocked:
            response = agent.send("I need endpoint X")
            mocked.assert_called_once()
        assert response == "got it"
        assert agent.phase == InterviewPhase.OWN_PATH

    def test_scoping_does_not_call_backend(self) -> None:
        backend = MockBackend()
        agent = InterviewAgent(backend)
        with mock.patch.object(backend, "execute", wraps=backend.execute) as mocked:
            agent.send("I want something")
            mocked.assert_not_called()

    def test_various_improvement_keywords(self) -> None:
        for keyword in ["improvement", "improvements", "improve", "analyze", "analyse", "areas"]:
            backend = MockBackend()
            agent = InterviewAgent(backend)
            agent.send("goal")
            agent.send(keyword)
            assert agent.phase == InterviewPhase.IMPROVEMENT, f"Failed for keyword: {keyword}"

    def test_non_improvement_defaults_to_own_path(self) -> None:
        for text in ["something else", "my way", "specific", "yes I have a plan"]:
            backend = MockBackend()
            agent = InterviewAgent(backend)
            agent.send("goal")
            agent.send(text)
            assert agent.phase == InterviewPhase.OWN_PATH, f"Failed for text: {text}"

    def test_full_improvement_conversation(self) -> None:
        config = MockBackendConfig(summary="backend response")
        backend = MockBackend(config=config)
        agent = InterviewAgent(backend)

        # Step 1: Greeting
        greeting = agent.greeting()
        assert greeting == SCOPING_QUESTION

        # Step 2: User describes goal -> gets binary choice
        response = agent.send("I want to build an API")
        assert response == CHOICE_QUESTION
        assert agent.phase == InterviewPhase.CHOICE

        # Step 3: User picks improvement
        response = agent.send("analyze for improvements")
        assert agent.phase == InterviewPhase.IMPROVEMENT
        assert response == "backend response"

        # Step 4: Follow-up
        response = agent.send("tell me more about error handling")
        assert agent.phase == InterviewPhase.IMPROVEMENT
        assert response == "backend response"

    def test_full_own_path_conversation(self) -> None:
        config = MockBackendConfig(summary="backend response")
        backend = MockBackend(config=config)
        agent = InterviewAgent(backend)

        # Step 1: Greeting
        greeting = agent.greeting()
        assert greeting == SCOPING_QUESTION

        # Step 2: User describes goal -> gets binary choice
        response = agent.send("I want to add authentication")
        assert response == CHOICE_QUESTION
        assert agent.phase == InterviewPhase.CHOICE

        # Step 3: User picks own path
        response = agent.send("I have a specific plan")
        assert agent.phase == InterviewPhase.OWN_PATH
        assert response == "backend response"

        # Step 4: Follow-up
        response = agent.send("I need JWT tokens")
        assert agent.phase == InterviewPhase.OWN_PATH
        assert response == "backend response"


class TestInterviewCLI:
    """Tests for the interview CLI subcommand with the agent wired in."""

    def test_interview_creates_agent(self, capsys: pytest.CaptureFixture[str]) -> None:
        """The interview command initialises an InterviewAgent with the chosen backend."""
        with mock.patch("builtins.input", side_effect=["exit"]):
            from spec_orca.cli import main

            rc = main(["interview", "--backend", "mock"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "interactive interview session" in out
        assert "backend=mock" in out

    def test_interview_shows_greeting(self, capsys: pytest.CaptureFixture[str]) -> None:
        """The interview command prints the initial scoping question."""
        with mock.patch("builtins.input", side_effect=["exit"]):
            from spec_orca.cli import main

            rc = main(["interview", "--backend", "mock"])
        assert rc == 0
        out = capsys.readouterr().out
        assert SCOPING_QUESTION in out

    def test_interview_sends_and_receives(self, capsys: pytest.CaptureFixture[str]) -> None:
        """User input is forwarded to the agent and a response is printed."""
        with mock.patch("builtins.input", side_effect=["hello", "exit", ""]):
            from spec_orca.cli import main

            rc = main(["interview", "--backend", "mock"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Interviewer:" in out

    def test_interview_flow_shows_choice(self, capsys: pytest.CaptureFixture[str]) -> None:
        """After the user describes their goal, the binary choice is shown."""
        with mock.patch("builtins.input", side_effect=["I want a web app", "exit", ""]):
            from spec_orca.cli import main

            rc = main(["interview", "--backend", "mock"])
        assert rc == 0
        out = capsys.readouterr().out
        assert CHOICE_QUESTION in out

    def test_interview_eof_exits(self, capsys: pytest.CaptureFixture[str]) -> None:
        with mock.patch("builtins.input", side_effect=EOFError):
            from spec_orca.cli import main

            rc = main(["interview", "--backend", "mock"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Interview session ended" in out

    def test_interview_empty_input_skipped(self, capsys: pytest.CaptureFixture[str]) -> None:
        with mock.patch("builtins.input", side_effect=["", "   ", "exit"]):
            from spec_orca.cli import main

            rc = main(["interview", "--backend", "mock"])
        assert rc == 0
        out = capsys.readouterr().out
        # No interviewer response should be printed for empty inputs
        # but the greeting is always printed
        assert SCOPING_QUESTION in out
