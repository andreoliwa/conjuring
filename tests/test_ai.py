# ruff: noqa: SLF001

import re
from io import StringIO
from pathlib import Path

import pytest
from invoke import Config, Context, MockContext, Result

from conjuring.spells import ai, media


def test_clean_llm_coauthor_keeps_subject_only() -> None:
    message = "feat: add spell\n\nCo-authored-by: Codex <noreply@openai.com>\n"

    assert ai._clean_llm_coauthor(message) == "feat: add spell\n"


def test_setup_initializes_openspec_writes_ignore_file_and_excludes_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    commands: list[str] = []
    excluded: list[list[str]] = []
    monkeypatch.setattr(ai, "_install_openspec_skills", lambda _c, _repo: None)
    monkeypatch.setattr(ai, "exclude", lambda _c, file: excluded.append(file))

    class Context:
        def run(self, command: str) -> None:
            commands.append(command)

    ai.setup.body(Context(), dir_=[str(repo)])

    assert commands == [f"cd {repo!s} && openspec init --tools codex,claude"]
    assert (repo / ".ignore").read_text().splitlines() == [
        "# Keep private planning documents discoverable through Codex @ mentions.",
        "# Git exclusion remains in .git/info/exclude.",
        "!docs/",
        "!docs/plans/",
        "!docs/superpowers/",
        "!openspec/",
        "!docs/plans/**",
        "!docs/superpowers/**",
        "!openspec/**",
    ]
    assert excluded == [["docs/plans/", "docs/superpowers/", "openspec/", ".openspec-target"]]


def test_setup_updates_existing_openspec_and_replaces_different_user_skills(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    skill = repo / ".agents" / "skills" / "openspec-test"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("new")
    (repo / "openspec").mkdir()
    user_skills = tmp_path / "user-skills"
    existing = user_skills / "openspec-test"
    existing.mkdir(parents=True)
    (existing / "SKILL.md").write_text("old")
    commands: list[str] = []
    monkeypatch.setattr(ai, "AGENTS_SKILLS_DIR", user_skills)
    monkeypatch.setattr(ai, "CLAUDE_SKILLS_DIR", tmp_path / "claude-skills")
    monkeypatch.setattr(ai, "CLAUDE_COMMANDS_DIR", tmp_path / "commands")
    monkeypatch.setattr(ai, "empty_dirs", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ai, "exclude", lambda *_args, **_kwargs: None)

    class Context:
        def run(self, command: str) -> None:
            commands.append(command)

    ai.setup.body(Context(), dir_=[str(repo)], ignore=False)

    assert commands == [f"cd {repo!s} && openspec update"]
    assert (user_skills / "openspec-test" / "SKILL.md").read_text() == "new"
    assert not skill.exists()
    assert "Replacing different OpenSpec skill" in capsys.readouterr().out


def test_setup_keeps_codex_and_claude_configured_after_globalizing_skills(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    (repo / "openspec").mkdir(parents=True)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "settings.local.json").write_text("{}")
    user_skills = tmp_path / "user-skills" / "openspec-test"
    user_skills.mkdir(parents=True)
    (user_skills / "SKILL.md").write_text("test")
    monkeypatch.setattr(ai, "AGENTS_SKILLS_DIR", user_skills.parent)
    monkeypatch.setattr(ai, "_install_openspec_skills", lambda *_args: None)
    monkeypatch.setattr(ai, "exclude", lambda *_args, **_kwargs: None)
    commands: list[str] = []

    class Context:
        def run(self, command: str) -> None:
            assert (repo / ".agents" / "skills" / ".openspec-target").read_text() == "codex\n"
            assert (repo / ".claude" / "skills" / ".openspec-target").read_text() == "claude\n"
            commands.append(command)

    ai.setup.body(Context(), dir_=[str(repo)], ignore=False)

    assert commands == [f"cd {repo} && openspec update"]


def test_setup_removes_identical_local_skills(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    skill = repo / ".claude" / "skills" / "openspec-test"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("same")
    user_skills = tmp_path / "user-skills"
    existing = user_skills / "openspec-test"
    existing.mkdir(parents=True)
    (existing / "SKILL.md").write_text("same")
    monkeypatch.setattr(ai, "CLAUDE_SKILLS_DIR", user_skills)
    monkeypatch.setattr(ai, "empty_dirs", lambda *_args, **_kwargs: None)

    ai._install_openspec_skills(MockContext(), repo)

    assert not skill.exists()
    assert (user_skills / "openspec-test" / "SKILL.md").read_text() == "same"


def test_install_openspec_skills_removes_empty_local_agent_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    skill = repo / ".agents" / "skills" / "openspec-test"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("new")
    cleaned: list[tuple[list[Path], bool, bool]] = []
    monkeypatch.setattr(ai, "AGENTS_SKILLS_DIR", tmp_path / "user-skills")

    def remove_nested_empty_dirs(_c: object, dirs: list[Path], delete: bool, delete_root: bool) -> None:
        cleaned.append((dirs, delete, delete_root))

    monkeypatch.setattr(ai, "empty_dirs", remove_nested_empty_dirs)

    ai._install_openspec_skills(MockContext(), repo)

    assert cleaned == [([repo / ".agents"], True, True)]


def test_install_openspec_skills_cleans_each_local_directory_separately(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    agent_skill = repo / ".agents" / "skills" / "openspec-agent"
    claude_skill = repo / ".claude" / "skills" / "openspec-claude"
    agent_skill.mkdir(parents=True)
    claude_skill.mkdir(parents=True)
    (agent_skill / "SKILL.md").write_text("agent")
    (claude_skill / "SKILL.md").write_text("claude")
    cleaned: list[list[Path]] = []
    monkeypatch.setattr(ai, "AGENTS_SKILLS_DIR", tmp_path / "user-agents")
    monkeypatch.setattr(ai, "CLAUDE_SKILLS_DIR", tmp_path / "user-claude")
    monkeypatch.setattr(ai, "empty_dirs", lambda _c, dirs, **_kwargs: cleaned.append(dirs))

    ai._install_openspec_skills(MockContext(), repo)

    assert cleaned == [[repo / ".agents", repo / ".claude"]]


@pytest.mark.parametrize(
    ("tool_dir", "tool_name", "user_skills_attr"),
    [
        (".agents", "codex", "AGENTS_SKILLS_DIR"),
        (".claude", "claude", "CLAUDE_SKILLS_DIR"),
    ],
)
def test_install_openspec_skills_preserves_openspec_target_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tool_dir: str, tool_name: str, user_skills_attr: str
) -> None:
    repo = tmp_path / "repo"
    skills_dir = repo / tool_dir / "skills"
    skills_dir.mkdir(parents=True)
    marker = skills_dir / ".openspec-target"
    marker.write_text(f"{tool_name}\n")
    skill = skills_dir / "openspec-test"
    skill.mkdir()
    (skill / "SKILL.md").write_text("test")
    user_skills = tmp_path / "user-skills"
    monkeypatch.setattr(ai, user_skills_attr, user_skills)
    monkeypatch.setattr(
        ai,
        "empty_dirs",
        lambda c, dirs, delete, delete_root: media.empty_dirs.body(
            c, dirs, delete=delete, delete_root=delete_root, fd=False
        ),
    )

    ai._install_openspec_skills(Context(Config(overrides={"run": {"in_stream": False}})), repo)

    assert (user_skills / "openspec-test" / "SKILL.md").read_text() == "test"
    assert marker.read_text() == f"{tool_name}\n"
    assert (repo / tool_dir).exists()


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
