from invoke import task

__CONJURING_PREFIX__ = True


@task
def auto(c):
    """Autoupdate nitpick hook with the latest tag."""
    # Import locally to avoid task duplication when used by namespace.add_collection()
    from conjuring.spells.pre_commit import install

    c.run("pre-commit autoupdate --repo https://github.com/andreoliwa/nitpick")
    install(c, gc=True)


@task
def bleed(c):
    """Autoupdate nitpick hook with the latest commit."""
    # Import locally to avoid task duplication when used by namespace.add_collection()
    from conjuring.spells.pre_commit import install

    c.run("pre-commit autoupdate --bleeding-edge --repo https://github.com/andreoliwa/nitpick")
    install(c, gc=True)
