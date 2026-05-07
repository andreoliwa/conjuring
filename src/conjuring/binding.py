"""Binding between Invoke tasks and Click/Typer commands."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Callable

import click
from invoke import Config, Context

_CLICK_NATIVE_TYPES = (str, int, float, bool)

if TYPE_CHECKING:
    from invoke import Task


def invoke_context(dry_run: bool = False) -> Context:
    """Construct a fresh Invoke Context, loading shell env and optional dry-run flag."""
    config = Config()
    config.load_shell_env()
    config.run.dry = dry_run
    return Context(config)


def invoke_to_click(task: Task, ctx_factory: Callable[..., Context]) -> click.Command:
    """Wrap an Invoke task as a Click command.

    Parameter mapping rules:
    - param in task.iterable → click.Option(multiple=True)
    - bool default           → click.Option(is_flag=True)
    - any other default      → click.Option(default=...)
    - no default             → click.Argument()
    """
    sig = inspect.signature(task.body)
    task_help: dict[str, str] = task.help or {}
    iterable: list[str] = task.iterable or []

    click_params: list[click.Parameter] = []
    for param_name, param in sig.parameters.items():
        if param_name == "c":
            continue
        help_text = task_help.get(param_name, "")
        has_default = param.default is not inspect.Parameter.empty

        if param_name in iterable:
            click_params.append(
                click.Option(
                    [f"--{param_name}"],
                    multiple=True,
                    help=help_text,
                )
            )
        elif has_default and isinstance(param.default, bool):
            click_params.append(
                click.Option(
                    [f"--{param_name}/--no-{param_name}"],
                    default=param.default,
                    is_flag=True,
                    help=help_text,
                )
            )
        elif has_default:
            annotation = param.annotation if param.annotation is not inspect.Parameter.empty else None
            click_type = (
                annotation if isinstance(annotation, type) and issubclass(annotation, _CLICK_NATIVE_TYPES) else None
            )
            click_params.append(
                click.Option(
                    [f"--{param_name}"],
                    default=param.default,
                    type=click_type,
                    help=help_text,
                )
            )
        else:
            click_params.append(click.Argument([param_name]))

    def callback(**kwargs: object) -> None:
        ctx = ctx_factory()
        task.body(ctx, **kwargs)

    return click.Command(
        name=task.name,
        callback=callback,
        params=click_params,
        help=inspect.getdoc(task.body),
    )
