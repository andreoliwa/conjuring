# ruff: noqa: SLF001

import re
from io import StringIO
from pathlib import Path

import pytest
from invoke import MockContext, Result

from conjuring.spells import ai


def test_clean_llm_coauthor_keeps_subject_only() -> None:
    message = "feat: add spell\n\nCo-authored-by: Codex <noreply@openai.com>\n"

    assert ai._clean_llm_coauthor(message) == "feat: add spell\n"


@pytest.mark.parametrize(
    "trailer",
    [
        "Co-authored-by: Claude <noreply@anthropic.com>",
        "Co-authored-by: Claude Code <noreply@anthropic.com>",
        "Co-authored-by: Codex <noreply@openai.com>",
    ],
)
def test_clean_llm_coauthor_keeps_existing_body(trailer: str) -> None:
    message = f"feat: add spell\n\nUseful detail.\n\n{trailer}\n"

    assert ai._clean_llm_coauthor(message) == "feat: add spell\n\nUseful detail.\n"


def test_clean_only_rewrites_unpushed_commits_with_codex_trailers(capsys: pytest.CaptureFixture[str]) -> None:
    log = f"abc123|feat: add spell|Co-authored-by: Codex <noreply@openai.com>{ai._LOG_RECORD_SEP}"
    c = MockContext(
        run={
            re.compile(r"git branch --show-current"): Result("feature\n"),
            re.compile(r"git rev-parse --verify origin/feature"): Result(exited=1),
            re.compile(r"git rev-parse --verify origin/main"): Result(),
            re.compile(r"git log origin/main\.\.HEAD"): Result(log),
            re.compile(r"git status --porcelain"): Result(""),
            re.compile(r"FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch --force"): Result(),
        }
    )

    ai.clean(c)

    command = c.run.call_args_list[-1].args[0]
    assert "--msg-filter" in command
    assert "origin/main..HEAD" in command
    assert "feat: add spell" in capsys.readouterr().out


def test_plans_statuses_only_lists_valid_statuses(capsys: pytest.CaptureFixture[str]) -> None:
    ai.plans.body(MockContext(), [], statuses=True)

    assert capsys.readouterr().out == "draft\napproved\npartial\ncomplete\nsuperseded\ncanceled\n"


@pytest.mark.parametrize("status", ["complete", "canceled", "superseded"])
def test_hidden_statuses_are_consistent_for_plans_and_gsd(tmp_path: Path, status: str) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text("")

    plan_rows = ai._plan_rows([plan], {plan: {"status": status}}, tmp_path, ["status"], [], all_=False)
    phase_rows = ai._gsd_phase_rows(
        [{"number": "1", "name": "Test", "status": status, "plan_count": 1, "summary_count": 1}], all_=False
    )

    quick_dir = tmp_path / ".planning" / "quick" / "20260901-abc-test"
    quick_dir.mkdir(parents=True)
    (quick_dir / "SUMMARY.md").write_text(f"---\nstatus: {status}\n---\n")
    quick_rows = ai._quick_task_rows(tmp_path, all_=False)

    assert plan_rows == []
    assert phase_rows == []
    assert quick_rows == []


def test_non_hidden_status_is_shown_for_plans_and_gsd(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text("")

    plan_rows = ai._plan_rows([plan], {plan: {"status": "draft"}}, tmp_path, ["status"], [], all_=False)
    phase_rows = ai._gsd_phase_rows(
        [{"number": "1", "name": "Test", "status": "draft", "plan_count": 1, "summary_count": 0}], all_=False
    )

    quick_dir = tmp_path / ".planning" / "quick" / "20260901-abc-test"
    quick_dir.mkdir(parents=True)
    (quick_dir / "PLAN.md").write_text("---\nstatus: draft\n---\n")
    quick_rows = ai._quick_task_rows(tmp_path, all_=False)

    assert plan_rows == [("plan.md", ["draft"])]
    assert phase_rows == [("1", "Test", "draft", "0/1")]
    assert quick_rows == [("quick", "20260901-abc-test", "draft", "")]


def test_tree_plan_rows_groups_directories_and_keeps_metadata_on_files() -> None:
    rows = [
        ("docs/plans/z.md", ["draft", "2026-09-30"]),
        ("docs/plans/sub/b.md", ["partial", "2026-09-29"]),
        ("docs/plans/sub/a.md", ["approved", "2026-09-28"]),
    ]

    assert ai._tree_plan_rows(rows) == [
        ("docs/plans", ["", ""]),
        ("├─ sub", ["", ""]),
        ("│  ├─ a.md", ["approved", "2026-09-28"]),
        ("│  └─ b.md", ["partial", "2026-09-29"]),
        ("└─ z.md", ["draft", "2026-09-30"]),
    ]


def test_plans_table_folds_long_filename_without_ellipsis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from rich.console import Console

    output = StringIO()
    console = Console(width=48, file=output, force_terminal=False)
    monkeypatch.setattr("rich.console.Console", lambda: console)
    name = "2026-09-30-a-very-long-plan-filename-that-must-not-be-truncated.md"
    ai._render_plans_table(
        [tmp_path],
        {tmp_path: [(f"docs/plans/{name}", ["draft", "2026-09-30"])]},
        tmp_path,
        ["status", "last_updated"],
        all_=False,
    )

    rendered = output.getvalue()
    assert "…" not in rendered
    assert "..." not in rendered
    assert "Updated" in rendered
    assert "Last Updated" not in rendered
    file_cells = [line.split("│")[1].strip() for line in rendered.splitlines() if line.startswith("│")]
    assert name in "".join(file_cells).replace("└─", "").replace(" ", "")


def test_plans_table_renders_worktree_labels_and_indents_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from rich.console import Console

    output = StringIO()
    console = Console(width=90, file=output, force_terminal=False)
    monkeypatch.setattr("rich.console.Console", lambda: console)
    first = tmp_path / ".worktrees" / "first"
    second = tmp_path / ".worktrees" / "second"
    ai._render_plans_table(
        [tmp_path, first, second],
        {
            tmp_path: [("docs/plans/main.md", ["draft", "2026-09-30"])],
            first: [("docs/plans/first.md", ["partial", "2026-09-29"])],
            second: [("docs/plans/second.md", ["approved", "2026-09-28"])],
        },
        tmp_path,
        ["status", "last_updated"],
        all_=False,
    )

    rendered = output.getvalue()
    assert "│ .worktrees/first" in rendered
    assert "│ .worktrees/second" in rendered
    assert "├─ .worktrees" not in rendered
    assert "└─ .worktrees" not in rendered
    assert "   └─ docs/plans" in rendered
    assert "      └─ first.md" in rendered
    assert "      └─ second.md" in rendered
    assert "./.worktrees" not in rendered


def test_all_shows_hidden_gsd_statuses() -> None:
    phases = [
        {"number": str(index), "name": status, "status": status, "plan_count": 0, "summary_count": 0}
        for index, status in enumerate(("complete", "canceled", "superseded"), start=1)
    ]

    assert ai._gsd_phase_rows(phases, all_=True) == [
        ("1", "complete", "complete", "0/0"),
        ("2", "canceled", "canceled", "0/0"),
        ("3", "superseded", "superseded", "0/0"),
    ]
