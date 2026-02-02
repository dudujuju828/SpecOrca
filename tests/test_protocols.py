"""Tests for protocol conformance."""

from __future__ import annotations

from spec_orca.protocols import AgentBackendProtocol, ArchitectProtocol
from spec_orca.stubs import EchoBackend, SimpleArchitect


class TestProtocolConformance:
    def test_simple_architect_satisfies_protocol(self) -> None:
        assert isinstance(SimpleArchitect(), ArchitectProtocol)

    def test_echo_backend_satisfies_protocol(self) -> None:
        assert isinstance(EchoBackend(), AgentBackendProtocol)
