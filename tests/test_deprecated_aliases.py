"""Tests for backwards-compatible deprecated aliases.

These tests verify that the old spec_orchestrator import names and
spec-orchestrator CLI command still work with appropriate deprecation warnings.
"""

from __future__ import annotations

import subprocess
import sys
import warnings

import pytest


class TestDeprecatedPackageImport:
    """Test that importing spec_orchestrator shows deprecation warning and works."""

    def test_import_warns_once(self) -> None:
        """Importing spec_orchestrator emits a DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Import in a fresh namespace
            import spec_orchestrator

            # Should have at least one deprecation warning
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
            assert "spec_orca" in str(deprecation_warnings[0].message)
            assert "renamed" in str(deprecation_warnings[0].message).lower()

            # Verify the module works
            assert hasattr(spec_orchestrator, "__version__")
            assert spec_orchestrator.__version__ == "0.1.0"

    def test_reexports_version(self) -> None:
        """spec_orchestrator.__version__ matches spec_orca.__version__."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import spec_orchestrator
            from spec_orca import __version__

            assert spec_orchestrator.__version__ == __version__

    def test_reexports_models(self) -> None:
        """spec_orchestrator re-exports core model classes."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import spec_orchestrator

            # Verify key exports exist
            assert hasattr(spec_orchestrator, "Spec")
            assert hasattr(spec_orchestrator, "Instruction")
            assert hasattr(spec_orchestrator, "StepResult")
            assert hasattr(spec_orchestrator, "MockBackend")
            assert hasattr(spec_orchestrator, "run_loop")

    def test_reexports_are_identical(self) -> None:
        """Exported classes are the same objects as spec_orca exports."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import spec_orchestrator
            from spec_orca.backends import MockBackend
            from spec_orca.models import Spec

            assert spec_orchestrator.Spec is Spec
            assert spec_orchestrator.MockBackend is MockBackend


class TestDeprecatedSubmoduleImports:
    """Test that importing spec_orchestrator submodules works with warnings."""

    def test_backends_submodule(self) -> None:
        """spec_orchestrator.backends forwards to spec_orca.backends."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from spec_orchestrator.backends import MockBackend

            # Should warn about the submodule
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert any("backends" in str(x.message) for x in deprecation_warnings)

            # Should work
            from spec_orca.backends import MockBackend as NewMockBackend

            assert MockBackend is NewMockBackend

    def test_models_submodule(self) -> None:
        """spec_orchestrator.models forwards to spec_orca.models."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from spec_orchestrator.models import Spec, StepStatus

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert any("models" in str(x.message) for x in deprecation_warnings)

            from spec_orca.models import Spec as NewSpec
            from spec_orca.models import StepStatus as NewStepStatus

            assert Spec is NewSpec
            assert StepStatus is NewStepStatus

    def test_cli_submodule(self) -> None:
        """spec_orchestrator.cli forwards to spec_orca.cli."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from spec_orchestrator.cli import main

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert any("cli" in str(x.message) for x in deprecation_warnings)

            from spec_orca.cli import main as new_main

            assert main is new_main

    def test_dev_git_submodule(self) -> None:
        """spec_orchestrator.dev.git forwards to spec_orca.dev.git."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from spec_orchestrator.dev.git import auto_commit

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert any("dev.git" in str(x.message) for x in deprecation_warnings)

            from spec_orca.dev.git import auto_commit as new_auto_commit

            assert auto_commit is new_auto_commit


class TestDeprecatedCLICommand:
    """Test that the deprecated spec-orchestrator CLI command works."""

    def test_deprecated_cli_shows_warning(self) -> None:
        """spec-orchestrator command prints deprecation warning to stderr."""
        proc = subprocess.run(
            [sys.executable, "-m", "spec_orca._deprecated_cli", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert proc.returncode == 0
        # Warning should be in stderr
        assert "WARNING" in proc.stderr
        assert "spec-orchestrator" in proc.stderr
        assert "spec-orca" in proc.stderr
        # Help should still appear in stdout
        assert "spec-orca" in proc.stdout

    def test_deprecated_cli_forwards_version(self) -> None:
        """spec-orchestrator --version works and shows warning."""
        proc = subprocess.run(
            [sys.executable, "-m", "spec_orca._deprecated_cli", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert proc.returncode == 0
        assert "WARNING" in proc.stderr
        assert "0.1.0" in proc.stdout

    def test_deprecated_cli_forwards_run(self, tmp_path: pytest.TempPathFactory) -> None:
        """spec-orchestrator run works and shows warning."""
        spec = tmp_path / "spec.md"  # type: ignore[operator]
        spec.write_text("# Test\nDo it.\n", encoding="utf-8")

        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "spec_orca._deprecated_cli",
                "run",
                "--spec",
                str(spec),
                "--backend",
                "mock",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert proc.returncode == 0
        assert "WARNING" in proc.stderr
        assert "[step 0]" in proc.stdout
        assert "[mock]" in proc.stdout


class TestNewCanonicalNames:
    """Verify new canonical names work without warnings."""

    def test_spec_orca_import_no_warning(self) -> None:
        """Importing spec_orca does not emit deprecation warnings."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            import spec_orca

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            # Filter out any warnings not from our code
            our_warnings = [x for x in deprecation_warnings if "spec_" in str(x.message)]
            assert len(our_warnings) == 0
            assert spec_orca.__version__ == "0.1.0"

    def test_spec_orca_cli_no_warning(self) -> None:
        """spec-orca CLI does not emit deprecation warnings."""
        proc = subprocess.run(
            [sys.executable, "-m", "spec_orca.cli", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert proc.returncode == 0
        # No deprecation warning in stderr
        assert "WARNING" not in proc.stderr
        assert "deprecated" not in proc.stderr.lower()
        # Help should work
        assert "spec-orca" in proc.stdout
