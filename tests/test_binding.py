import click
from click.testing import CliRunner
from invoke import Context, task

from conjuring.binding import invoke_context, invoke_to_click


def test_invoke_context_returns_context():
    ctx = invoke_context()
    assert isinstance(ctx, Context)


def test_invoke_context_loads_shell_env(monkeypatch):
    monkeypatch.setenv("INVOKE_RUN_ECHO", "1")
    ctx = invoke_context()
    # load_shell_env() maps INVOKE_RUN_ECHO → config.run.echo
    assert ctx.config.run.echo is True


def test_invoke_context_pty(monkeypatch):
    monkeypatch.setenv("INVOKE_RUN_PTY", "1")
    ctx = invoke_context()
    assert ctx.config.run.pty is True


def test_invoke_context_dry_run_false():
    ctx = invoke_context(dry_run=False)
    assert ctx.config.run.dry is False


def test_invoke_context_dry_run_true():
    ctx = invoke_context(dry_run=True)
    assert ctx.config.run.dry is True


def test_invoke_to_click_bool_param_is_flag():
    @task
    def mytask(c, verbose=False):
        """My task."""

    cmd = invoke_to_click(mytask, invoke_context)
    opt = next(p for p in cmd.params if p.name == "verbose")
    assert isinstance(opt, click.Option)
    assert opt.is_flag is True


def test_invoke_to_click_str_param_is_option_with_default():
    @task
    def mytask(c, name="world"):
        """My task."""

    cmd = invoke_to_click(mytask, invoke_context)
    opt = next(p for p in cmd.params if p.name == "name")
    assert isinstance(opt, click.Option)
    assert opt.default == "world"


def test_invoke_to_click_no_default_is_argument():
    @task
    def mytask(c, filename):
        """My task."""

    cmd = invoke_to_click(mytask, invoke_context)
    arg = next(p for p in cmd.params if p.name == "filename")
    assert isinstance(arg, click.Argument)


def test_invoke_to_click_iterable_param_is_multiple():
    @task(iterable=["tags"])
    def mytask(c, tags=None):
        """My task."""

    cmd = invoke_to_click(mytask, invoke_context)
    opt = next(p for p in cmd.params if p.name == "tags")
    assert isinstance(opt, click.Option)
    assert opt.multiple is True


def test_invoke_to_click_help_from_task_help_dict():
    @task(help={"name": "The name to greet"})
    def mytask(c, name="world"):
        """My task."""

    cmd = invoke_to_click(mytask, invoke_context)
    opt = next(p for p in cmd.params if p.name == "name")
    assert opt.help == "The name to greet"


def test_invoke_to_click_docstring_becomes_command_help():
    @task
    def mytask(c):
        """Greet the world."""

    cmd = invoke_to_click(mytask, invoke_context)
    assert cmd.help == "Greet the world."


def test_invoke_to_click_calls_task_body():
    called_with = {}

    @task
    def mytask(c, name="world"):
        """My task."""
        called_with["ctx"] = c
        called_with["name"] = name

    cmd = invoke_to_click(mytask, invoke_context)
    runner = CliRunner()
    result = runner.invoke(cmd, ["--name", "Alice"])
    assert result.exit_code == 0, result.output
    assert called_with["name"] == "Alice"
    assert isinstance(called_with["ctx"], Context)


def test_invoke_to_click_typed_param_uses_annotation():
    @task
    def mytask(c, count: int = 0):
        """My task."""

    cmd = invoke_to_click(mytask, invoke_context)
    runner = CliRunner()
    result = runner.invoke(cmd, ["--count", "3"])
    assert result.exit_code == 0, result.output
