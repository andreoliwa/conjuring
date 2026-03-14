"""Shell: install/uninstall completion."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

from invoke import Context, task

from conjuring.grimoire import ask_yes_no, join_pieces, print_error, print_success, print_warning

SHOULD_PREFIX = True

COMPAT_DIR = "$BASH_COMPLETION_COMPAT_DIR/"
USER_DIR = "$BASH_COMPLETION_USER_DIR/completions/"
COMPLETION_DIRS = (COMPAT_DIR, USER_DIR)

_SUBCOMMAND_COMPLETION = "completion"
_SUBCOMMAND_COMPLETIONS = "completions"
_SHEBANG_PREFIX = "#"

# Typer completion script templates (%(key)s format), sourced from
# typer._completion_shared._completion_scripts (typer 0.12+, stable since).
# Embedded here to avoid importing typer into the conjuring environment.
_TYPER_SCRIPTS: dict[str, str] = {
    "bash": (
        "\n%(complete_func)s() {\n"
        "    local IFS=$'\\n'\n"
        '    COMPREPLY=( $( env COMP_WORDS="${COMP_WORDS[*]}" \\\n'
        "                   COMP_CWORD=$COMP_CWORD \\\n"
        "                   %(autocomplete_var)s=complete_bash $1 ) )\n"
        "    return 0\n"
        "}\n\n"
        "complete -o default -F %(complete_func)s %(prog_name)s\n"
    ),
    "zsh": (
        "\n#compdef %(prog_name)s\n\n"
        "%(complete_func)s() {\n"
        '  eval $(env _TYPER_COMPLETE_ARGS="${words[1,$CURRENT]}"'
        " %(autocomplete_var)s=complete_zsh %(prog_name)s)\n"
        "}\n\n"
        "compdef %(complete_func)s %(prog_name)s\n"
    ),
    "fish": (
        "complete --command %(prog_name)s --no-files"
        ' --arguments "(env %(autocomplete_var)s=complete_fish'
        " _TYPER_COMPLETE_FISH_ACTION=get-args"
        ' _TYPER_COMPLETE_ARGS=(commandline -cp) %(prog_name)s)"'
        ' --condition "env %(autocomplete_var)s=complete_fish'
        " _TYPER_COMPLETE_FISH_ACTION=is-args"
        ' _TYPER_COMPLETE_ARGS=(commandline -cp) %(prog_name)s"'
    ),
}


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
    """Try to generate completions for a Clap (Rust) binary.

    Clap-based tools expose either `<app> completions <shell>` or
    `<app> completion <shell>` (both are common spellings in the ecosystem).

    Detection heuristic: try both subcommand spellings and take whichever
    produces non-empty output.

    References:
    - https://docs.rs/clap_complete/

    """
    for subcommand in (_SUBCOMMAND_COMPLETIONS, _SUBCOMMAND_COMPLETION):
        output = _probe(c, app, subcommand, shell)
        if output:
            return output
    return ""


def _cobra_completion(c: Context, app: str, shell: Shell) -> str:
    """Try to generate completions for a Cobra (Go) binary.

    Cobra exposes `<app> completion <shell>` automatically on every binary.
    Detection: we probe `<app> completion <shell>` and accept the result only
    when it starts with a shebang line, which Cobra scripts always have but
    Click output does not.

    References:
    - https://cobra.dev/docs/how-to-guides/shell-completion/

    """
    output = _probe(c, app, _SUBCOMMAND_COMPLETION, shell)
    if output and output.startswith(_SHEBANG_PREFIX):
        return output
    return ""


def _typer_completion(c: Context, app: str, shell: Shell) -> str:
    """Try to generate completions for a Typer (Python) binary.

    Typer does not expose completion scripts via the binary — the script is
    generated internally by `typer._completion_shared.get_completion_script()`.

    Detection: `--show-completion` appears in the `--help` output of every
    Typer app that has completion enabled (the default).  We set NO_COLOR=1
    to prevent Rich from injecting ANSI escape sequences that would break
    the substring search when invoke runs without a real TTY.

    References:
    - https://typer.tiangolo.com/tutorial/options-autocompletion/

    """
    help_output = _probe(c, f"NO_COLOR=1 {app}", "--help")
    if "--show-completion" not in help_output:
        return ""
    template = _TYPER_SCRIPTS.get(shell.value)
    if template is None:
        return ""
    complete_func = f"_{app.replace('-', '_')}_completion"
    complete_var = f"_{app.replace('-', '_').upper()}_COMPLETE"
    return template % {"complete_func": complete_func, "prog_name": app, "autocomplete_var": complete_var}


def _click_completion(c: Context, app: str, shell: Shell) -> str:
    """Try to generate completions for a Click (Python) binary.

    Click uses the env-var protocol `_{APP}_COMPLETE=<shell>_source <app>`.

    References:
    - https://click.palletsprojects.com/en/8.0.x/shell-completion/

    """
    env_var = f"_{app.upper()}_COMPLETE"
    env_value = f"{shell}_source"
    return _probe(c, f"{env_var}={env_value} {app}")


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
    """Probe each known framework and return (framework_name, completion_script)."""
    for framework_name, detector in _DETECTORS:
        script = detector(c, app, shell)  # type: ignore[operator]
        if script:
            return framework_name, script
    return "", ""


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

    framework, script = _generate_completion(c, app, shell)
    if not script:
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
    completion_file.write_text(script, encoding="utf-8")
    print_success(f"Installed: {completion_file}")
    c.run(f"eza -l {completion_file}")


@task
def completion_uninstall(c: Context, app: str) -> None:
    """Uninstall shell completion from both completion dirs."""
    for completion_dir in COMPLETION_DIRS:
        with c.cd(completion_dir):
            c.run(f"rm -v {app}*", warn=True)
