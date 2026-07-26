"""Tests for shell completion helpers."""

from __future__ import annotations

from conjuring.spells.shell import _completion_loader


def test_completion_loader_evaluates_the_generator_at_shell_startup() -> None:
    generator = "vessel --show-completion bash"

    assert _completion_loader(generator) == 'eval "$(vessel --show-completion bash)"\n'
