"""Kubernetes."""
from dataclasses import dataclass

from invoke import Context, Result, task

from conjuring.grimoire import run_command, run_lines, run_with_fzf

SHOULD_PREFIX = True


@dataclass
class Kubectl:
    """Kubectl commands."""

    context: Context

    def choose_apps(self, partial_app_name: str = None, *, multi=False) -> list[str]:
        """Select apps from Kubernetes deployments, using a partial app name and fzf."""
        return run_with_fzf(
            self.context,
            """kubectl get deployments.apps -o jsonpath='{range .items[*]}{.metadata.name}{"\\n"}{end}'""",
            query=partial_app_name,
            multi=multi,
        )

    @staticmethod
    def _app_selector(apps: list[str]) -> str:
        """Return the app selector for one or more apps."""
        sorted_unique_apps = sorted(set(apps))
        if len(sorted_unique_apps) == 1:
            return f"-l app={sorted_unique_apps[0]}"
        selector = f" in ({', '.join(sorted_unique_apps)})"
        return f"-l 'app{selector}'"

    def cmd_get(self, resource: str, apps: list[str]) -> str:
        """Return the kubectl get command for one or more apps."""
        return f"kubectl get {resource} {self._app_selector(apps)}"

    def run_get(self, resource: str, apps: list[str]) -> Result:
        """Run the kubectl get command for one or more apps."""
        return run_command(self.context, self.cmd_get(resource, apps))


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
    chosen_app = Kubectl(c).choose_apps(app)
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
    kubectl = Kubectl(c)
    chosen_apps = kubectl.choose_apps(app, multi=True)
    kubectl.run_get("pods", chosen_apps)

    if replica_set:
        replica_set_names = run_lines(
            c,
            kubectl.cmd_get("pods", chosen_apps),
            """-o jsonpath='{range .items[*]}{.metadata.ownerReferences[0].name}{"\\n"}{end}'""",
            "| sort -u",
        )
        for name in replica_set_names:
            run_command(c, f"kubectl get replicaset {name}")
