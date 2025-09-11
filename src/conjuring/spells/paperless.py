"""[Paperless](https://github.com/paperless-ngx/paperless-ngx): maintenance, renamer, sanity, delete duplicates."""

from __future__ import annotations

import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, cast

import requests
import typer
from invoke import Context, task

from conjuring.constants import DOT_DS_STORE, DOWNLOADS_DIR
from conjuring.grimoire import ask_user_prompt, lazy_env_variable, print_error, print_success, print_warning, run_lines
from conjuring.spells import media

if TYPE_CHECKING:
    from collections.abc import Sequence

# keep-sorted start
COUNT_PAIR = 2
COUNT_PARTS = 4
DOWNLOAD_DESTINATION_DIR = DOWNLOADS_DIR / __name__.rsplit(".")[-1]
DUPLICATE_OF = " It is a duplicate of "
ORPHAN_ARCHIVE = "archive"
ORPHAN_ORIGINALS = "originals"
ORPHAN_THUMBNAILS = "thumbnails"
REGEX_TITLE_WITH_ID = re.compile(r"(?P<name>.*) ?\(#(?P<id>\d+)\)")
SHOULD_PREFIX = True
STARTING_YEAR = 1900
USR_SRC_DOCUMENTS = "/usr/src/paperless/media/documents/"
# keep-sorted end


def paperless_cmd(instance: str = "") -> str:
    """Command to run Paperless with Docker."""
    value = lazy_env_variable("PAPERLESS_COMPOSE_YAML", "path to the Paperless Docker compose YAML file")
    yaml_file = Path(value).expanduser()
    if not yaml_file.exists():
        msg = f"Paperless compose YAML file doesn't exist: {yaml_file}"
        raise FileNotFoundError(msg)

    suffix = f"_{instance}" if instance else ""
    return f"docker compose -f {yaml_file} exec webserver{suffix}"


def paperless_root_dir(instance: str = "") -> Path:
    """Root directory for Paperless."""
    value = lazy_env_variable("PAPERLESS_ROOT_DIR", "root directory for Paperless")
    subdir = "paperless_" + instance
    root_dir = Path(value).expanduser() / subdir
    if not root_dir.exists():
        msg = f"Paperless root directory doesn't exist: {root_dir}"
        raise FileNotFoundError(msg)
    return root_dir


def paperless_url() -> str:
    """URL where Paperless is running."""
    return lazy_env_variable("PAPERLESS_URL", "URL where Paperless is running")


def paperless_token() -> str:
    """Auth token to access Paperless API."""
    return lazy_env_variable("PAPERLESS_TOKEN", "auth token to access Paperless API")


@task
def maintenance(
    c: Context,
    instance: str,
    reindex: bool = True,
    optimize: bool = True,
    thumbnails: bool = True,
) -> None:
    """Reindex all docs and optionally optimize them.

    https://docs.paperless-ngx.com/administration/#index
    https://docs.paperless-ngx.com/administration/#thumbnails
    """
    if reindex:
        c.run(f"{paperless_cmd(instance)} document_index reindex")
    if optimize:
        c.run(f"{paperless_cmd(instance)} document_index optimize")
    if thumbnails:
        c.run(f"{paperless_cmd(instance)} document_thumbnails")


@task
def rename(c: Context, instance: str) -> None:
    """Rename files.

    https://docs.paperless-ngx.com/administration/#renamer
    """
    c.run(f"{paperless_cmd(instance)} document_renamer")


@dataclass
class Document:
    """A paperless document."""

    document_id: int
    title: str
    errors: list = field(default_factory=list, init=False)

    @property
    def url(self) -> str:
        """Return the URL to the document details page."""
        return f"{paperless_url()}/documents/{self.document_id}/details"

    def __repr__(self) -> str:
        """Return a string representation of the document."""
        return f"Document(document_id={self.document_id}, title='{self.title}', url='{self.url}', errors={self.errors})"


@dataclass
class OrphanFile:
    """A paperless orphan file."""

    source: Path
    destination: Path

    def __lt__(self, other: OrphanFile) -> bool:
        return self.source < other.source


@task(
    help={
        "hide": "Hide progress bar of sanity command",
        "orphans": "Show orphan files",
        "thumbnails": "Show thumbnail files",
        "documents": "Show documents with issues",
        "unknown": "Show unknown lines from the log",
        "errors": "Show documents with specific errors (comma-separated list)",
        "together": f"Keep {ORPHAN_ORIGINALS} and {ORPHAN_ARCHIVE} in the same output directory",
        "fix": "Fix broken files by copying/moving them to the downloads dir",
        "move": "Move files instead of copying",
    },
)
def sanity(  # noqa: PLR0913
    c: Context,
    instance: str,
    hide: bool = False,
    orphans: bool = False,
    thumbnails: bool = False,
    documents: bool = False,
    unknown: bool = True,
    errors: str = "",
    together: bool = False,
    fix: bool = False,
    move: bool = False,
) -> None:
    """Sanity checker. Optionally fix orphan files (copies or movies them to the download dir).

    https://docs.paperless-ngx.com/administration/#sanity-checker
    """
    # Fail fast if the env var is not set
    documents_dir = paperless_root_dir(instance) / "media/documents"
    if documents_dir and not documents_dir.exists():
        msg = f"Documents directory doesn't exist: {documents_dir}"
        raise RuntimeError(msg)

    # TODO: fix(paperless): implement dry-run mode with dry=False and actually avoid files being copied/moved
    lines = run_lines(c, paperless_cmd(instance), "document_sanity_checker", hide=hide, warn=True, pty=True)

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
            continue

        msg = "Orphaned file in media dir: "
        if msg in line:
            partial_path = Path(line.split(msg)[1].replace(USR_SRC_DOCUMENTS, ""))
            _process_orphans(partial_path, documents_dir, original_or_archive_files, orphan_files, thumbnail_files)
            continue

        msg = "Detected following issue(s) with document #"
        if msg in line:
            # Append the previous document
            if current_document:
                documents_with_issues.append(current_document)

            # Extract document ID and title from the line
            # Format: "Detected following issue(s) with document #123, titled Title"
            rest_of_line = line.split(msg)[1]
            document_id, title = rest_of_line.split(", titled ")

            current_document = Document(int(document_id), title)
            continue

        if current_document:
            _, error = line.split("[paperless.sanity_checker] ")
            current_document.errors.append(error)
            continue

        unknown_lines.append(line)

    _split_matched_unmatched(original_or_archive_files, matched_files, unmatched_files, together)

    _handle_items(fix, move, orphans, "Matched originals/archive pairs", matched_files)
    _handle_items(fix, move, orphans, "Unmatched originals/archive files", unmatched_files)
    _handle_items(False, move, orphans, "Other orphaned files", orphan_files)
    # TODO: feat(paperless): move thumbnail files to downloads dir
    _handle_items(fix, move, thumbnails, "Orphaned thumbnail files", thumbnail_files)
    _handle_items(False, move, documents, "Documents with issues", documents_with_issues, errors)
    _handle_items(False, move, unknown, "Unknown lines", unknown_lines)


def _process_orphans(
    partial_path: Path,
    documents_dir: Path | None,
    original_or_archive_files: dict[str, list[OrphanFile]],
    orphan_files: list[str],
    thumbnail_files: list[str],
) -> None:
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
    original_or_archive_files: dict[str, list[OrphanFile]],
    partial_path: Path,
    documents_dir: Path | None = None,
) -> None:
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
        if not (
            part.isnumeric()
            and len(part) == COUNT_PARTS
            and int(part) > STARTING_YEAR
            and partial_path.stem.startswith(part)
        )
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
) -> None:
    for single_or_pair in original_or_archive_files.values():
        if len(single_or_pair) == COUNT_PAIR:
            originals_first = sorted(single_or_pair, reverse=True)
            if together:
                for orphan_file in originals_first:
                    match_path = orphan_file.destination
                    file_without_first_part = Path("/".join(match_path.parts[1:]))
                    if str(match_path).startswith(ORPHAN_ARCHIVE):
                        # Append ORPHAN_ARCHIVE to the file stem
                        orphan_file.destination = file_without_first_part.with_stem(
                            f"{match_path.stem}-{ORPHAN_ARCHIVE}",
                        )
                    else:
                        orphan_file.destination = file_without_first_part
                    matched_files.append(orphan_file)
            else:
                matched_files.extend(originals_first)
        else:
            unmatched_files.extend(single_or_pair)


def _handle_items(  # noqa: PLR0913
    fix: bool,
    move: bool,
    show_details: bool,
    title: str,
    collection: Sequence[str | OrphanFile | Document],
    errors: str = "",
) -> None:
    length = len(collection)
    which_function = print_error if length else print_success

    # Special handling for documents to show error counts
    if collection and isinstance(collection[0], Document):
        doc_collection = cast("list[Document]", collection)
        _display_documents_with_error_counts(title, doc_collection, show_details, errors)
        return

    which_function(f"{title} (count: {length})")
    if not (show_details or fix):
        return

    # https://docs.python.org/3/library/shutil.html#shutil.copy2
    msg = "Moving" if move else "Copying"

    dest_dir = DOWNLOAD_DESTINATION_DIR / title
    for item in collection:
        if not isinstance(item, OrphanFile):
            typer.echo(str(item))
            continue

        if not fix:
            typer.echo(str(item.source))
            continue

        if not item.source.exists():
            print_error(f"Not found: {item.source}")
            continue

        dest_file = dest_dir / item.destination
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        print_success(f"{msg} {item.source} to {dest_file}")

        if move:
            shutil.move(item.source, dest_file)
        else:
            shutil.copy2(item.source, dest_file)


def _display_documents_with_error_counts(  # noqa: C901
    title: str,
    documents: Sequence[Document],
    show_details: bool,
    errors: str = "",
) -> None:
    """Display documents with error counts grouped by error type."""
    error_list = errors.split(",")

    def display_count() -> None:
        length = len(documents)
        which_function = print_error if length else print_success
        which_function(f"{title} (count: {length})")

    error_counts: dict[str, int] = Counter()
    docs_by_error: dict[str, list[Document]] = defaultdict(list)
    for doc in documents:
        for error in doc.errors:
            error_counts[error] += 1
            docs_by_error[error].append(doc)

    display_count()
    if error_counts:
        typer.echo("Error breakdown:")
        for error, count in sorted(error_counts.items()):
            display_error = False
            if error_list:
                for err in error_list:
                    if err in error:
                        display_error = True
                        break

            listed_below = " (documents listed below)" if show_details and display_error else ""
            print_error(f"- {error} = {count}{listed_below}")

            if show_details and display_error:
                for doc in docs_by_error[error]:
                    typer.echo(f"  - {doc}")


@task
def delete_failed_duplicates(c: Context, max_delete: int = 100) -> None:
    """Delete records marked as duplicate but that cannot be downloaded. So the PDF files can be reimported."""
    session = requests.Session()
    session.headers.update({"authorization": f"token {paperless_token()}"})

    delete_count = 0
    req_tasks = session.get(f"{paperless_url()}/api/tasks/?format=json")
    for obj in req_tasks.json():
        if obj["status"] != "FAILURE":
            continue

        raw_line = obj["result"]
        if DUPLICATE_OF not in raw_line:
            print_error(f"Unknown error: {raw_line}")
            continue

        clean_line = raw_line.replace(" Not consuming ", "").replace(DUPLICATE_OF, "")
        first, second, duplicate_with_id = clean_line.split(":", maxsplit=2)
        if first != second:
            print_error(f"Files are different: {first=} / {second=}")
        match = REGEX_TITLE_WITH_ID.match(duplicate_with_id)
        if not match:
            print_error(f"Line doesn't match regex {duplicate_with_id=}", clean_line)
            continue

        data = match.groupdict()
        document_id = data["id"]

        api_document_url = f"{paperless_url()}/api/documents/{document_id}/"
        document_url = f"{paperless_url()}/documents/{document_id}"
        url = f"{api_document_url}download/"
        req_download = session.head(url)
        if req_download.status_code != HTTPStatus.NOT_FOUND:
            print_success(document_url, f"Document exists {req_download.status_code=}", clean_line)
            continue

        req_document = session.head(api_document_url)
        if req_document.status_code == HTTPStatus.NOT_FOUND:
            print_warning(document_url, "Document already deleted before", clean_line)
            continue

        req_delete = session.delete(api_document_url)
        if req_delete.status_code == HTTPStatus.NO_CONTENT:
            print_success(document_url, f"Document deleted #{delete_count}", clean_line)
            delete_count += 1
            if delete_count >= max_delete:
                raise SystemExit
            continue

        print_error(document_url, clean_line, f"Something wrong: {req_delete.status_code=}")
        c.run(f"open {document_url}")


@task
def empty_consume_dir(c: Context, instance: str) -> None:
    """Empty the consume dir."""
    consume_dir = paperless_root_dir(instance) / "consume-into-paperless"
    print_success(str(consume_dir))

    fd_cmd = f"fd -uu -t f . {consume_dir}"
    if not c.run(fd_cmd).stdout:
        print_success("Consume dir is already empty.")
        return

    if ask_user_prompt("Delete files above?", allowed_keys="yn") != "y":
        raise SystemExit

    c.run(fd_cmd + " -0 | xargs -0 -r -n 1 rm -v")

    media.empty_dirs(c, [consume_dir], delete=True)
    c.run(f"ls -l {consume_dir}")
