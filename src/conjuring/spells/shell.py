"""Shell: completions, hostname, and process management."""

from __future__ import annotations

import os
import platform
import shlex
import uuid
from enum import Enum
from pathlib import Path

from invoke import Context, task

from conjuring.grimoire import (
    ask_yes_no,
    join_pieces,
    print_error,
    print_success,
    print_warning,
    run_command,
    run_stdout,
)

SHOULD_PREFIX = True

COMPAT_DIR = "$BASH_COMPLETION_COMPAT_DIR/"
USER_DIR = "$BASH_COMPLETION_USER_DIR/completions/"
COMPLETION_DIRS = (COMPAT_DIR, USER_DIR)

_SUBCOMMAND_COMPLETION = "completion"
_SUBCOMMAND_COMPLETIONS = "completions"
_SHEBANG_PREFIX = "#"

_TYPER_SHELLS = frozenset({"bash", "fish", "zsh"})


class Shell(str, Enum):
    """Shells supported by completion generators."""

    BASH = "bash"
    ELVISH = "elvish"
    FISH = "fish"
    POWERSHELL = "powershell"
    ZSH = "zsh"

    def __str__(self) -> str:
        """Return the plain value, not 'Shell.BASH'."""
        return self.value


_DEFAULT_SHELL = Shell.BASH


def _probe(c: Context, *pieces: str) -> str:
    """Run a command silently for detection purposes; never print errors."""
    result = c.run(join_pieces(*pieces), hide=True, warn=True, pty=False)
    return str(result.stdout).strip() if result.ok else ""


def _detect_current_shell() -> Shell | None:
    """Return the current Shell from $SHELL, or None if unrecognized."""
    name = Path(os.environ.get("SHELL", "")).name.lower()
    return next((s for s in Shell if s.value == name), None)


def _clap_completion(c: Context, app: str, shell: Shell) -> str:
    """Return a completion generator command for a Clap (Rust) binary.

    Clap-based tools expose either `<app> completions <shell>` or
    `<app> completion <shell>` (both are common spellings in the ecosystem).

    Detection heuristic: try both subcommand spellings and take whichever
    produces non-empty output.

    References:
    - https://docs.rs/clap_complete/

    """
    for subcommand in (_SUBCOMMAND_COMPLETIONS, _SUBCOMMAND_COMPLETION):
        output = _probe(c, shlex.quote(app), subcommand, shell)
        if output:
            return shlex.join((app, subcommand, shell.value))
    return ""


def _cobra_completion(c: Context, app: str, shell: Shell) -> str:
    """Return a completion generator command for a Cobra (Go) binary.

    Cobra exposes `<app> completion <shell>` automatically on every binary.
    Detection: we probe `<app> completion <shell>` and accept the result only
    when it starts with a shebang line, which Cobra scripts always have but
    Click output does not.

    References:
    - https://cobra.dev/docs/how-to-guides/shell-completion/

    """
    output = _probe(c, shlex.quote(app), _SUBCOMMAND_COMPLETION, shell)
    if output and output.startswith(_SHEBANG_PREFIX):
        return shlex.join((app, _SUBCOMMAND_COMPLETION, shell.value))
    return ""


def _typer_completion(c: Context, app: str, shell: Shell) -> str:
    """Return a completion generator command for a Typer (Python) binary.

    Detection: `--show-completion` appears in the `--help` output of every
    Typer app that has completion enabled (the default).  We set NO_COLOR=1
    to prevent Rich from injecting ANSI escape sequences that would break
    the substring search when invoke runs without a real TTY.

    References:
    - https://typer.tiangolo.com/tutorial/options-autocompletion/

    """
    help_output = _probe(c, f"NO_COLOR=1 {shlex.quote(app)}", "--help")
    if "--show-completion" not in help_output:
        return ""
    if shell.value not in _TYPER_SHELLS:
        return ""
    return shlex.join((app, "--show-completion", shell.value))


def _click_completion(c: Context, app: str, shell: Shell) -> str:
    """Return a completion generator command for a Click (Python) binary.

    Click uses the env-var protocol `_{APP}_COMPLETE=<shell>_source <app>`.

    References:
    - https://click.palletsprojects.com/en/8.0.x/shell-completion/

    """
    env_var = f"_{app.upper()}_COMPLETE"
    env_value = f"{shell}_source"
    if _probe(c, f"{env_var}={env_value} {shlex.quote(app)}"):
        return f"{env_var}={env_value} {shlex.quote(app)}"
    return ""


# Ordered list of (name, detector_fn).  Add new frameworks here.
# Each function receives (c, app, shell) and returns the completion script
# as a string, or "" when it cannot handle that binary.
_DETECTORS: list[tuple[str, object]] = [
    ("clap (Rust)", _clap_completion),
    ("cobra (Go)", _cobra_completion),
    ("typer (Python)", _typer_completion),
    ("click (Python)", _click_completion),
]


def _generate_completion(c: Context, app: str, shell: Shell) -> tuple[str, str]:
    """Probe each known framework and return its completion generator command."""
    for framework_name, detector in _DETECTORS:
        generator = detector(c, app, shell)  # type: ignore[operator]
        if generator:
            return framework_name, generator
    return "", ""


def _completion_loader(generator: str) -> str:
    """Return a shell snippet that loads fresh completions from GENERATOR."""
    return f'eval "$({generator})"\n'


@task
def completion_list(c: Context) -> None:
    """List existing shell completions."""
    for var in COMPLETION_DIRS:
        c.run(f"eza -l {var}")


@task
def completion_install(c: Context, app: str) -> None:
    """Detect the CLI framework for APP and install shell completion into USER_DIR.

    Supported frameworks (auto-detected in order):
    - Clap / Rust   (subcommand: completions <shell> or completion <shell>)
    - Cobra / Go    (subcommand: completion <shell>, output starts with #)
    - Typer / Python  (--show-completion in --help; script via Python API)
    - Click / Python  (env-var: _{APP}_COMPLETE=<shell>_source)

    References:
    - https://docs.rs/clap_complete/
    - https://cobra.dev/docs/how-to-guides/shell-completion/
    - https://typer.tiangolo.com/tutorial/options-autocompletion/
    - https://click.palletsprojects.com/en/8.0.x/shell-completion/

    """
    shell = _detect_current_shell()
    if shell is None:
        print_warning(f"Unknown shell — defaulting to {_DEFAULT_SHELL.value}. Set $SHELL to override.")
        shell = _DEFAULT_SHELL

    framework, generator = _generate_completion(c, app, shell)
    if not generator:
        print_error(f"Could not detect CLI framework for '{app}'. Tried: {', '.join(n for n, _ in _DETECTORS)}")
        return

    print_success(f"Detected framework: {framework}")

    # Expand USER_DIR (it may contain env vars like $BASH_COMPLETION_USER_DIR).
    user_dir = Path(os.path.expandvars(USER_DIR.rstrip("/")))
    completion_file = user_dir / f"{app}.{shell}-completion"

    if completion_file.exists():
        c.run(f"eza -l {completion_file}")
        if not ask_yes_no(f"Completion already exists at {completion_file}. Replace it?"):
            return

    user_dir.mkdir(parents=True, exist_ok=True)
    completion_file.write_text(_completion_loader(generator), encoding="utf-8")
    print_success(f"Installed: {completion_file}")
    c.run(f"eza -l {completion_file}")


@task
def completion_uninstall(c: Context, app: str) -> None:
    """Uninstall shell completion from both completion dirs."""
    for completion_dir in COMPLETION_DIRS:
        with c.cd(completion_dir):
            c.run(f"rm -v {app}*", warn=True)


def _generate_hostname() -> str:
    """Generate an opaque hostname with an OS-based prefix."""
    suffix = str(uuid.uuid4())[:8]
    prefix = "Mac" if platform.system() == "Darwin" else "Host"
    return f"{prefix}-{suffix}"


@task
def hostname_set(c: Context, name: str = "") -> None:
    """Set the system hostname. Generates an opaque name when NAME is omitted."""
    dry = c.config.run.dry
    hostname = name or _generate_hostname()

    if platform.system() == "Darwin":
        commands = [
            f"sudo scutil --set ComputerName {hostname!r}",
            f"sudo scutil --set HostName {hostname!r}",
            f"sudo scutil --set LocalHostName {hostname!r}",
        ]
    else:
        commands = [f"sudo hostnamectl set-hostname {hostname!r}"]

    print_success(f"Hostname: {hostname}")
    for cmd in commands:
        if dry:
            print_warning(f"[dry run] {cmd}")
        else:
            c.run(cmd)


@task(
    help={
        "path": "Exact path to the binary to kill (e.g. /usr/local/bin/pocketbase)",
        "str": "Name fragment to match against the full command line (pkill -f)",
    },
)
def kill_process(c: Context, path: str = "", str: str = "") -> None:  # noqa: A002
    """Kill a process by binary path or command-line fragment."""
    if not path and not str:
        print_warning("Provide --path or --str")
        return
    if path:
        _kill_by_path(c, path)
    if str:
        _kill_by_fragment(c, str)


def _pgrep(c: Context, fragment: str) -> list[str]:
    return [p for p in run_stdout(c, "pgrep -f", fragment, dry=False).splitlines() if p.strip()]


def _kill_by_path(c: Context, binary_path: str) -> None:
    pids = _pgrep(c, binary_path)
    if not pids:
        print_success(f"  No process found for path: {binary_path}")
        return
    print_warning(f"  Killing {len(pids)} process(es) for {binary_path}: {', '.join(pids)}")
    run_command(c, "kill", "-9", *pids)


def _kill_by_fragment(c: Context, fragment: str) -> None:
    pids = _pgrep(c, fragment)
    if not pids:
        print_success(f"  No process found for fragment: {fragment}")
        return
    print_warning(f"  Killing {len(pids)} process(es) matching '{fragment}': {', '.join(pids)}")
    run_command(c, "kill", "-9", *pids)
