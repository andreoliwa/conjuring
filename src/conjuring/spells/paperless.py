"""Wrapper tasks for papaerless commands https://github.com/paperless-ngx/paperless-ngx."""
import os
from dataclasses import dataclass, field
from typing import Optional

from invoke import task

from conjuring.grimoire import print_error, print_success, run_lines

PAPERLESS_COMPOSE_YAML = "CONJURING_PAPERLESS_COMPOSE_YAML"

SHOULD_PREFIX = True


def paperless_cmd() -> str:
    """Lazy evaluation of the docker compose command that runs paperless commands."""
    yaml_file = os.environ.get(PAPERLESS_COMPOSE_YAML)
    if not yaml_file:
        raise RuntimeError(
            "Paperless tasks can't be executed."
            f" Set the env variable {PAPERLESS_COMPOSE_YAML} with the path of paperless Docker compose file."
        )
    return f"docker compose -f {yaml_file} exec webserver"


@task
def maintenance(c, reindex=True, optimize=True, thumbnails=True):
    """Reindex all docs and optionally optimize them.

    https://docs.paperless-ngx.com/administration/#index
    https://docs.paperless-ngx.com/administration/#thumbnails
    """
    if reindex:
        c.run(f"{paperless_cmd()} document_index reindex")
    if optimize:
        c.run(f"{paperless_cmd()} document_index optimize")
    if thumbnails:
        c.run(f"{paperless_cmd()} document_thumbnails")


@task
def rename(c):
    """Rename files.

    https://docs.paperless-ngx.com/administration/#renamer
    """
    c.run(f"{paperless_cmd()} document_renamer")


@dataclass
class Document:
    document_id: int
    title: str
    errors: list = field(default_factory=list, init=False)


@task(
    help={
        "hide": "Hide progress bar of sanity command. Default: True",
        "orphans": "Show orphan files. Default: True",
        "documents": "Show documents with issues. Default: False",
        "unknown": "Show unknown lines from the log. Default: True",
    }
)
def sanity(c, hide=True, orphans=True, documents=False, unknown=True):
    """Sanity checker.

    https://docs.paperless-ngx.com/administration/#sanity-checker
    """
    lines = run_lines(c, paperless_cmd(), "document_sanity_checker", hide=hide, warn=True, pty=True)

    progress_bar = []
    orphan_files = []
    current_document: Optional[Document] = None
    documents_with_issues: list[Document] = []
    unknown_lines = []
    for line in lines:
        if "it/s]" in line:
            progress_bar.append(line)
            continue

        if (msg := "Orphaned file in media dir: ") in line:
            orphan_files.append(line.split(msg)[1])
            continue

        if (msg := "Detected following issue(s) with document #") in line:
            # Append the previous document
            if current_document:
                documents_with_issues.append(current_document)

            document_id, title = line.split(msg)[1].split(", titled ")
            current_document = Document(int(document_id), title)
            continue

        if current_document:
            _, error = line.split("[paperless.sanity_checker] ")
            current_document.errors.append(error)
            continue

        unknown_lines.append(line)

    # FIXME: match original and archive files

    # FIXME: --fix flag

    # FIXME: move matched pairs to ~/Downloads/matched

    # FIXME: move unmatched files to ~/Downloads/unmatched

    # FIXME: delete thumbnails
    if orphans:
        print_items("Orphan files", orphan_files)
    if documents:
        print_items("Documents with issues", documents_with_issues)
    if unknown:
        print_items("Unknown lines", unknown_lines)


def print_items(title: str, collection):
    length = len(collection)
    which_function = print_error if length else print_success
    which_function(f"{title} (count: {length})")
    for item in collection:
        print(item)
