"""[Docker](https://www.docker.com/): remove containers and volumes."""
from invoke import Context, task

from conjuring.grimoire import print_error, run_command

SHOULD_PREFIX = True


@task(
    help={
        "container": "Container name to remove (regexp)",
        "all_": "All containers",
        "exited": "Exited containers",
    },
)
def rm_containers(c: Context, container: str = "", all_: bool = False, exited: bool = False) -> None:
    """Remove Docker containers."""
    cmd = []
    if all_:
        cmd = ["docker ps -a"]
    elif exited:
        cmd = ["docker ps -a -f status=exited"]
    elif container:
        cmd = ["docker ps -a | grep -e", container]
    if not cmd:
        print_error("Choose one argument. Run with --help to see available argument")
        return

    run_command(c, *cmd, dry=False)
    run_command(c, *cmd, "| tail +2 | awk '{print $1}' | xargs docker rm -f")
    run_command(c, *cmd)


@task(help=({"dangling": "Dangling volumes"}))
def rm_volumes(c: Context, dangling: bool = False) -> None:
    """Remove Docker volumes."""
    cmd = ""
    if dangling:
        cmd = 'docker volume ls -f "dangling=true"'
    if not cmd:
        print_error("Choose one argument. Run with --help to see available argument")
        return

    run_command(c, cmd, dry=False)
    run_command(c, f"docker volume rm $({cmd} -q)")
    run_command(c, cmd)
