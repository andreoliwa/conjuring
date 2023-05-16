"""Tasks to interact with https://myrepos.branchable.com/."""
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import Optional

from invoke import Context, task

from conjuring.grimoire import run_stdout, run_with_fzf

MRCONFIG_FILE = ".mrconfig"

SHOULD_PREFIX = True


@dataclass
class MyRepos:
    context: Context

    def find_configs(self, partial_name: str, echo=False) -> list[Path]:
        """Find config files in the current dir or dirs above."""
        lower_partial_name = partial_name.lower()
        if not lower_partial_name:
            glob_pattern = MRCONFIG_FILE
        else:
            glob_pattern = f"{MRCONFIG_FILE}*{lower_partial_name}*"
        config_dir = self._find_dir_with_mrconfigs(glob_pattern)
        if not config_dir:
            msg = f"No {MRCONFIG_FILE}* file was found in {Path.cwd()} or its parents"
            raise FileNotFoundError(msg)

        if not lower_partial_name:
            return [config_dir / MRCONFIG_FILE]

        with self.context.cd(str(config_dir)):
            chosen = run_with_fzf(
                self.context,
                "ls -1",
                f"{MRCONFIG_FILE}*",
                query=lower_partial_name,
                multi=True,
                echo=echo,
                hide=not echo,
            )
        return sorted({config_dir / c for c in chosen})

    @staticmethod
    def _find_dir_with_mrconfigs(glob_pattern) -> Optional[Path]:
        for dir_ in chain([Path.cwd()], Path.cwd().parents):
            for _ in dir_.glob(glob_pattern):
                # Exit loop on the first file found; fzf will handle the rest
                return dir_
        return None


@task(
    help={
        "config": f"Specific config file to use. Use fzf if multiple are found. Default: {MRCONFIG_FILE}",
        "echo": "Echo the commands being executed, for debugging purposes. Default: False",
    }
)
def grep(c, search_text, config="", echo=False):
    """Grep mr repositories with a seacrh text and print the directories in which the text was found.

    Needs mr to be preconfigured with files starting with the ".mrconfig" prefix.
    """
    for chosen in MyRepos(c).find_configs(config, echo=echo):
        # For some reason, using run_command() prints a "\r" char at the end of each line;
        # the solution is to get output as a string and use print().
        output_without_linefeed = run_stdout(
            c,
            "mr -c",
            str(chosen),
            "-m grep",
            search_text,
            "| rg --color=never 'mr grep: (.+)$' --replace '$1'",
            echo=echo,
        )
        print(output_without_linefeed)
