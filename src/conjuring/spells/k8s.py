"""Kubernetes."""
from invoke import task

from conjuring.grimoire import run_command, run_lines, run_with_fzf

SHOULD_PREFIX = True


def fzf_deployment(c, partial_name: str = None) -> str:
    """Select a k8s deployment from a partial profile name using fzf."""
    return run_with_fzf(
        c,
        """kubectl get deployments.apps -o jsonpath='{range .items[*]}{.metadata.name}{"\\n"}{end}'""",
        query=partial_name,
    )


@task()
def validate_score(c):
    """Validate and score files that were changed from the master branch."""
    # TODO: handle branches named "main"
    # Continue even if there are errors
    c.run("git diff master.. --name-only | xargs kubeval", warn=True)
    c.run("git diff master.. --name-only | xargs kubectl score")


@task(help={"rg": "Filter results with rg"})
def config_map(c, app, rg=""):
    """Show the config map for an app."""
    chosen_app = fzf_deployment(c, app)
    run_command(
        c,
        f"kubectl get deployment/{chosen_app} -o json",
        "| jq -r .spec.template.spec.containers[].envFrom[].configMapRef.name",
        "| rg -v null | xargs -I % kubectl get configmap/% -o json | jq -r .data",
        f"| rg {rg}" if rg else "",
    )


@task(help={"replica_set": "Show the replica sets for an app"})
def pods(c, app, replica_set=False):
    """Show the pods and replica sets for an app."""
    chosen_app = fzf_deployment(c, app)
    run_command(c, f"kubectl get pods -l app={chosen_app}")

    if replica_set:
        replica_set_names = run_lines(
            c,
            f"kubectl get pods -l app={chosen_app}",
            """-o jsonpath='{range .items[*]}{.metadata.ownerReferences[0].name}{"\\n"}{end}'""",
            "| sort -u",
        )
        for name in replica_set_names:
            run_command(c, f"kubectl get replicaset {name}")
