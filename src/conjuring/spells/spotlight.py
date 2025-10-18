"""MacOS Spotlight spells.

There is not much we can do.

There is NO programmatic way to exclude directories from Spotlight on modern macOS.
You have to do it manually through System Settings > Spotlight Privacy.

"It just works"!
"""

from __future__ import annotations

from invoke import Context, task

from conjuring.grimoire import ask_user_prompt, print_error, print_success, print_warning

SHOULD_PREFIX = True


@task
def status(c: Context) -> None:
    """Check Spotlight indexing status."""
    print("Checking Spotlight status...")
    c.run("mdutil -s /", warn=True)
    c.run("mdutil -s ~", warn=True)

    print("Monitoring Spotlight indexing activity (press Ctrl+C to stop)...")
    print("This shows which files are being indexed in real-time\n")
    c.run("sudo fs_usage -w -f filesys mds mdworker | grep -v CACHE_HIT", warn=True)


@task
def settings(c: Context) -> None:
    """Open Spotlight Privacy settings in System Settings."""
    print("Opening Spotlight Privacy settings...")
    print("You need to manually add directories to exclude from indexing.")
    c.run("open 'x-apple.systempreferences:com.apple.Spotlight-Settings.extension'", warn=True)


@task
def rebuild(c: Context, force: bool = False) -> None:
    """Rebuild the Spotlight index."""
    print_error("⚠️  WARNING: This will ERASE your entire Spotlight index!")
    print("This will take a while and may slow down your system temporarily")
    print("You will not be able to search for files until indexing completes (30min - several hours)")

    if not force:
        response = ask_user_prompt("Are you sure you want to rebuild the Spotlight index?", allowed_keys="yn")
        if response != "y":
            print_warning("Rebuild cancelled.")
            return

    print("\nRebuilding Spotlight index...")

    print("\nDisable, delete and re-enable Spotlight indexing")
    c.run("( sudo mdutil -a -i off ; sudo mdutil -E / ; sudo mdutil -a -i on )", warn=True)

    print_success("\nSpotlight index rebuild started!")
    print("Indexing will continue in the background.")
    print("You can check status with: invoke spotlight.status")
