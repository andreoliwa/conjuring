"""Wrapper tasks for papaerless commands https://github.com/paperless-ngx/paperless-ngx."""
from __future__ import annotations

import os
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from invoke import task

from conjuring.constants import DOT_DS_STORE, DOWNLOADS_DIR
from conjuring.grimoire import print_error, print_success, run_lines

SHOULD_PREFIX = True

ENV_COMPOSE_YAML = "PAPERLESS_COMPOSE_YAML"
ENV_MEDIA_DOCUMENTS_DIR = "PAPERLESS_MEDIA_DOCUMENTS_DIR"
USR_SRC_DOCUMENTS = "/usr/src/paperless/media/documents/"
ORPHAN_ARCHIVE = "archive"
ORPHAN_ORIGINALS = "originals"
ORPHAN_THUMBNAILS = "thumbnails"
DOWNLOAD_DESTINATION_DIR = DOWNLOADS_DIR / __name__.rsplit(".")[-1]


def paperless_cmd() -> str:
    """Lazy evaluation of the docker compose command that runs paperless commands."""
    yaml_file = os.environ.get(ENV_COMPOSE_YAML)
    if not yaml_file:
        raise RuntimeError(
            "Paperless tasks can't be executed."
            f" Set the env variable {ENV_COMPOSE_YAML} with the path of paperless Docker compose file."
        )
    return f"docker compose -f {yaml_file} exec webserver"


def paperless_documents_dir() -> Path:
    """Lazy evaluation of the local media documents dir."""
    documents_dir = os.environ.get(ENV_MEDIA_DOCUMENTS_DIR)
    if not documents_dir:
        raise RuntimeError(
            "Paperless tasks can't be executed."
            f" Set the env variable {ENV_MEDIA_DOCUMENTS_DIR} with the dir where paperless stores documents."
        )
    return Path(documents_dir).expanduser()


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


@dataclass
class OrphanFile:
    source: Path
    destination: Path

    def __lt__(self, other: OrphanFile):
        return self.source < other.source


@task(
    help={
        "hide": "Hide progress bar of sanity command. Default: True",
        "orphans": "Show orphan files. Default: True",
        "thumbnails": "Show thumbnail files. Default: False",
        "documents": "Show documents with issues. Default: False",
        "unknown": "Show unknown lines from the log. Default: True",
        "together": f"Keep {ORPHAN_ORIGINALS} and {ORPHAN_ARCHIVE} in the same output directory",
        "fix": "Fix broken files by copying them to the downloads dir",
        # FIXME: flag to delete original files?
    }
)
def sanity(c, hide=True, orphans=True, thumbnails=False, documents=False, unknown=True, together=False, fix=False):
    """Sanity checker. Optionally fix orphan files (copies or movies them to the download dir).

    https://docs.paperless-ngx.com/administration/#sanity-checker
    """
    # Fail fast if the env var is not set
    documents_dir = paperless_documents_dir() if fix else None
    if documents_dir and not documents_dir.exists():
        raise RuntimeError(f"Documents directory doesn't exist: {documents_dir}")

    lines = run_lines(c, paperless_cmd(), "document_sanity_checker", hide=hide, warn=True, pty=True)

    progress_bar: list[str] = []
    original_or_archive_files: dict[str, list[OrphanFile]] = defaultdict(list)
    matched_files: list[OrphanFile] = []
    unmatched_files: list[OrphanFile] = []
    orphan_files: list[str] = []
    thumbnail_files: list[str] = []
    current_document: Document | None = None
    documents_with_issues: list[Document] = []
    unknown_lines = []
    for line in lines:
        if "it/s]" in line:
            progress_bar.append(line)
            continue

        if (msg := "Orphaned file in media dir: ") in line:
            partial_path = Path(line.split(msg)[1].replace(USR_SRC_DOCUMENTS, ""))
            _process_orphans(partial_path, documents_dir, original_or_archive_files, orphan_files, thumbnail_files)
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

    _split_matched_unmatched(original_or_archive_files, matched_files, unmatched_files, together)

    _handle_items(fix, orphans, "Matched files", matched_files)
    _handle_items(fix, orphans, "Unmatched files", unmatched_files)
    _handle_items(False, orphans, "Orphan files", orphan_files)
    _handle_items(fix, thumbnails, "Thumbnail files", thumbnail_files)
    _handle_items(False, documents, "Documents with issues", documents_with_issues)
    _handle_items(False, unknown, "Unknown lines", unknown_lines)


def _process_orphans(partial_path, documents_dir, original_or_archive_files, orphan_files, thumbnail_files):
    if partial_path.name == DOT_DS_STORE:
        return

    first_part = partial_path.parts[0]
    if first_part == ORPHAN_THUMBNAILS:
        thumbnail_files.append(str(partial_path))
        return

    if first_part in (ORPHAN_ARCHIVE, ORPHAN_ORIGINALS):
        _split_original_archive(original_or_archive_files, partial_path, documents_dir)
        return

    orphan_files.append(str(partial_path))


def _split_original_archive(
    original_or_archive_files: dict[str, list[OrphanFile]], partial_path: Path, documents_dir: Path = None
):
    file_key = str(Path("/".join(partial_path.parts[1:])).with_suffix(""))
    expanded_parts = []
    for part in partial_path.parts[:-1]:
        if "," in part:
            expanded_parts.extend(sorted(part.split(",")))
        else:
            expanded_parts.append(part)

    # Skip directories with a year when the file name starts with it
    filtered_parts = [
        part
        for part in expanded_parts
        if not (part.isnumeric() and len(part) == 4 and int(part) > 1900 and partial_path.stem.startswith(part))
    ]

    file_name = partial_path.parts[-1]
    filtered_parts.append(file_name)

    orphan_dir = documents_dir or Path()
    orphan = OrphanFile(source=orphan_dir / partial_path, destination=Path("/".join(filtered_parts)))
    original_or_archive_files[file_key].append(orphan)


def _split_matched_unmatched(
    original_or_archive_files: dict[str, list[OrphanFile]],
    matched_files: list[OrphanFile],
    unmatched_files: list[OrphanFile],
    together: bool,
):
    for single_or_pair in original_or_archive_files.values():
        if len(single_or_pair) == 2:
            originals_first = sorted(single_or_pair, reverse=True)
            if together:
                for orphan_file in originals_first:
                    match_path = orphan_file.destination
                    file_without_first_part = Path("/".join(match_path.parts[1:]))
                    if str(match_path).startswith(ORPHAN_ARCHIVE):
                        # Append ORPHAN_ARCHIVE to the file stem
                        orphan_file.destination = file_without_first_part.with_stem(
                            f"{match_path.stem}-{ORPHAN_ARCHIVE}"
                        )
                    else:
                        orphan_file.destination = file_without_first_part
                    matched_files.append(orphan_file)
            else:
                matched_files.extend(originals_first)
        else:
            unmatched_files.extend(single_or_pair)


def _handle_items(fix: bool, show_details: bool, title: str, collection: list[str | OrphanFile]):
    length = len(collection)
    which_function = print_error if length else print_success
    which_function(f"{title} (count: {length})")
    if not show_details:
        return

    dest_dir = DOWNLOAD_DESTINATION_DIR / title
    for item in collection:
        if not isinstance(item, OrphanFile):
            print(str(item))
            continue

        if not fix:
            print(str(item.source))
            continue

        if not item.source.exists():
            print_error(f"Not found: {item.source}")
            continue

        dest_file = dest_dir / item.destination
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        print_success(f"Copying {item.source} to {dest_file}")

        # https://docs.python.org/3/library/shutil.html#shutil.copy2
        shutil.copy2(item.source, dest_file)
