"""[direnv](https://github.com/direnv/direnv)."""
from pathlib import Path

from invoke import Context, task

from conjuring.grimoire import bat, print_error

SHOULD_PREFIX = True

ENVRC = ".envrc"
SOURCE_UP_IF_EXISTS = "source_up_if_exists"
SOURCE_UP_IF_EXISTS_TEMPLATE = f"""
# https://direnv.net/man/direnv-stdlib.1.html#codesourceupifexists-ltfilenamegtcode
{SOURCE_UP_IF_EXISTS}
"""
DOTENV_IF_EXISTS = "dotenv_if_exists"
DOTENV_IF_EXISTS_TEMPLATE = f"""
# https://direnv.net/man/direnv-stdlib.1.html#codedotenvifexists-ltdotenvpathgtcode
{DOTENV_IF_EXISTS}
{DOTENV_IF_EXISTS} .env.local
"""


@task()
def init(c: Context, source_up: bool = False, dotenv: bool = False, all_: bool = False) -> None:
    """Configure direnv in the local dir."""
    if all_:
        source_up = dotenv = True
    if not (source_up or dotenv or all_):
        print_error("Choose one of the options: --source-up, --dotenv, --all")
        return

    envrc = Path(ENVRC)
    content = envrc.read_text() if envrc.exists() else ""

    if source_up and SOURCE_UP_IF_EXISTS not in content:
        content += SOURCE_UP_IF_EXISTS_TEMPLATE

    if dotenv and DOTENV_IF_EXISTS not in content:
        content += DOTENV_IF_EXISTS_TEMPLATE

    if content:
        envrc.write_text(content)
        c.run("direnv allow")

    bat(c, ".env*")
