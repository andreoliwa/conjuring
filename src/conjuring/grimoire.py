from typing import List

from invoke import Context

from conjuring.constants import COLOR_LIGHT_RED, COLOR_NONE


def join_pieces(*pieces: str):
    """Join pieces, ignoring empty strings."""
    return " ".join(str(piece) for piece in pieces if str(piece).strip())


def run_command(c: Context, *pieces: str, warn: bool = False, hide: bool = False, dry: bool = None):
    """Build command from pieces, ignoring empty strings."""
    kwargs = {"dry": dry} if dry is not None else {}
    return c.run(join_pieces(*pieces), warn=warn, hide=hide, **kwargs)


def run_stdout(c: Context, *pieces: str, hide=True) -> str:
    """Run a (hidden) command and return the stripped stdout."""
    return c.run(join_pieces(*pieces), hide=hide, pty=False).stdout.strip()


def run_lines(c: Context, *pieces: str) -> List[str]:
    """Run a (hidden) command and return the result as lines."""
    return run_stdout(c, *pieces).splitlines()


def print_error(*message: str):
    """Print an error message."""
    all_messages = " ".join(message)
    print(f"{COLOR_LIGHT_RED}{all_messages}{COLOR_NONE}")


def run_with_fzf(c: Context, *pieces: str, query="") -> str:
    """Run a command with fzf and return the chosen entry."""
    fzf_pieces = ["| fzf --reverse --select-1 --height 40%"]
    if query:
        fzf_pieces.append(f"-q '{query}'")
    return run_stdout(c, *pieces, *fzf_pieces, hide=False)
