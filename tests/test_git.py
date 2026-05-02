"""Tests for conjuring.spells.git helpers."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from invoke import MockContext, Result

if TYPE_CHECKING:
    from pathlib import Path


def test_placeholder() -> None:
    assert True


def test_find_release_workflow_returns_single_match(tmp_path: Path) -> None:
    from conjuring.spells.git import _find_release_workflow

    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)
    release_yml = workflows_dir / "release.yml"
    release_yml.write_text("name: Release\n")

    result = _find_release_workflow(MockContext(), tmp_path)
    assert result == release_yml


def test_find_release_workflow_returns_none_when_missing(tmp_path: Path) -> None:
    from conjuring.spells.git import _find_release_workflow

    result = _find_release_workflow(MockContext(), tmp_path)
    assert result is None


def test_extract_environment_name_found(tmp_path: Path) -> None:
    from conjuring.spells.git import _extract_environment_name

    workflow = tmp_path / "release.yml"
    workflow.write_text("jobs:\n  deploy:\n    environment: production\n")
    c = MockContext(run=Result("production\n"))
    assert _extract_environment_name(c, workflow) == "production"


def test_extract_environment_name_not_found(tmp_path: Path) -> None:
    from conjuring.spells.git import _extract_environment_name

    workflow = tmp_path / "release.yml"
    workflow.write_text("jobs:\n  build:\n    steps: []\n")
    c = MockContext(run=Result("\n"))
    assert _extract_environment_name(c, workflow) is None


def test_check_github_environment_exists() -> None:
    from conjuring.spells.git import _check_github_environment

    c = MockContext(
        run={
            re.compile(r"gh repo view.*--json"): Result("owner/repo\n"),
            re.compile(r"gh api.*environments.*production"): Result('{"name":"production"}'),
        }
    )
    assert _check_github_environment(c, "production") is True


def test_check_github_environment_missing_opens_browser() -> None:
    from conjuring.spells.git import _check_github_environment

    c = MockContext(
        run={
            re.compile(r"gh repo view.*--json"): Result("owner/repo\n"),
            re.compile(r"gh api.*environments.*staging"): Result(exited=1),
            re.compile(r"open https://.*"): Result(),
        }
    )
    assert _check_github_environment(c, "staging") is False


def test_uses_semantic_release_in_workflow(tmp_path: Path) -> None:
    from conjuring.spells.git import _uses_semantic_release

    workflow = tmp_path / "release.yml"
    workflow.write_text("uses: cycjimmy/semantic-release-action@v4\n")
    assert _uses_semantic_release(workflow, tmp_path) is True


def test_uses_semantic_release_in_package_json(tmp_path: Path) -> None:
    from conjuring.spells.git import _uses_semantic_release

    workflow = tmp_path / "release.yml"
    workflow.write_text("name: Release\n")
    (tmp_path / "package.json").write_text('{"devDependencies": {"semantic-release": "^21.0.0"}}')
    assert _uses_semantic_release(workflow, tmp_path) is True


def test_uses_semantic_release_in_pyproject(tmp_path: Path) -> None:
    from conjuring.spells.git import _uses_semantic_release

    workflow = tmp_path / "release.yml"
    workflow.write_text("name: Release\n")
    (tmp_path / "pyproject.toml").write_text("[tool.semantic_release]\nversion_toml = []\n")
    assert _uses_semantic_release(workflow, tmp_path) is True


def test_uses_semantic_release_not_found(tmp_path: Path) -> None:
    from conjuring.spells.git import _uses_semantic_release

    workflow = tmp_path / "release.yml"
    workflow.write_text("name: Release\nuses: softprops/action-gh-release@v2\n")
    assert _uses_semantic_release(workflow, tmp_path) is False


def test_uses_release_please_via_config_file(tmp_path: Path) -> None:
    from conjuring.spells.git import _uses_release_please

    workflow = tmp_path / "release.yml"
    workflow.write_text("name: Release\n")
    (tmp_path / "release-please-config.json").write_text('{"packages": {".": {}}}')
    assert _uses_release_please(workflow, tmp_path) is True


def test_uses_release_please_via_workflow(tmp_path: Path) -> None:
    from conjuring.spells.git import _uses_release_please

    workflow = tmp_path / "release.yml"
    workflow.write_text("uses: googleapis/release-please-action@v4\n")
    assert _uses_release_please(workflow, tmp_path) is True


def test_uses_release_please_not_found(tmp_path: Path) -> None:
    from conjuring.spells.git import _uses_release_please

    workflow = tmp_path / "release.yml"
    workflow.write_text("uses: commitizen-tools/commitizen-action@master\n")
    assert _uses_release_please(workflow, tmp_path) is False


def test_bootstrap_v0_tag_creates_tag() -> None:
    from conjuring.spells.git import _bootstrap_v0_tag

    first_sha = "abc1234"
    c = MockContext(
        run={
            re.compile(r"git tag -l v0\.0\.0"): Result(""),
            re.compile(r"git rev-list --max-parents=0 HEAD"): Result(f"{first_sha}\n"),
            re.compile(r"git tag -a v0\.0\.0"): Result(),
        }
    )
    _bootstrap_v0_tag(c)


def test_bootstrap_v0_tag_skips_if_exists() -> None:
    from conjuring.spells.git import _bootstrap_v0_tag

    c = MockContext(
        run={
            re.compile(r"git tag -l v0\.0\.0"): Result("v0.0.0\n"),
        }
    )
    _bootstrap_v0_tag(c)
    assert c.run.call_count == 1


def test_trigger_release_workflow_simple(tmp_path: Path) -> None:
    from conjuring.spells.git import _trigger_release_workflow

    workflow = tmp_path / "release.yml"
    workflow.write_text("on:\n  workflow_dispatch:\nname: Release\n")
    c = MockContext(
        run={
            re.compile(r"yq.*workflow_dispatch"): Result(""),
            re.compile(r"gh workflow run"): Result(),
            re.compile(r"gh run watch"): Result(),
            re.compile(r"gh run view.*--json"): Result('{"url":"https://github.com/owner/repo/actions/runs/1"}'),
        }
    )
    _trigger_release_workflow(c, workflow)


def test_trigger_release_workflow_with_inputs_opens_browser(tmp_path: Path) -> None:
    from conjuring.spells.git import _trigger_release_workflow

    workflow = tmp_path / "release.yml"
    workflow.write_text("on:\n  workflow_dispatch:\n    inputs:\n      version:\n        required: true\n")
    c = MockContext(
        run={
            re.compile(r"yq.*workflow_dispatch"): Result("version\n"),
            re.compile(r"gh repo view.*--json"): Result("owner/repo\n"),
            re.compile(r"open https://.*actions"): Result(),
        }
    )
    _trigger_release_workflow(c, workflow)


def test_merge_release_please_pr_merges_on_confirm() -> None:
    from conjuring.spells.git import _merge_release_please_pr

    pr_json = (
        '[{"number":42,"title":"chore(release): release v0.8.0",'
        '"url":"https://github.com/owner/repo/pull/42","body":"## Changelog\\n- feat: something"}]'
    )
    c = MockContext(
        run={
            re.compile(r"gh pr list.*autorelease"): Result(pr_json),
            re.compile(r"gh pr merge 42.*--squash"): Result(),
            re.compile(r"gh pr view 42.*--web"): Result(),
        }
    )
    with patch("conjuring.spells.git.ask_yes_no", return_value=True):
        _merge_release_please_pr(c)


def test_merge_release_please_pr_dry_run_does_not_merge() -> None:
    from invoke import Config

    from conjuring.spells.git import _merge_release_please_pr

    pr_json = '[{"number":42,"title":"chore(release): release v0.8.0","url":"https://github.com/owner/repo/pull/42","body":""}]'
    config = Config(overrides={"run": {"dry": True}})
    c = MockContext(
        config=config,
        run={
            re.compile(r"gh pr list.*autorelease"): Result(pr_json),
            re.compile(r"gh pr merge 42.*--squash"): Result(),
        },
    )
    _merge_release_please_pr(c)


def test_merge_release_please_pr_aborts_when_none_found() -> None:
    from conjuring.spells.git import _merge_release_please_pr

    c = MockContext(
        run={
            re.compile(r"gh pr list.*autorelease"): Result("[]"),
        }
    )
    with pytest.raises(SystemExit):
        _merge_release_please_pr(c)


def test_preview_changelog_prints_output(tmp_path: Path) -> None:
    from conjuring.spells.git import _preview_changelog

    cliff_config = tmp_path / "cliff.toml"
    cliff_config.write_text("[changelog]\n")
    cliff_output = "## What's Changed\n\n### Features\n- add something\n"
    c = MockContext(run=Result(cliff_output))
    _preview_changelog(c, cliff_config)


def test_preview_changelog_skips_when_no_cliff_config(tmp_path: Path) -> None:
    from conjuring.spells.git import _preview_changelog

    # MockContext with no run= raises NotImplementedError if run() is called unexpectedly
    c = MockContext()
    _preview_changelog(c, tmp_path / "cliff.toml")  # must not call c.run()


def test_release_sanity_aborts_when_no_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from conjuring.spells.git import release

    monkeypatch.chdir(tmp_path)
    c = MockContext(
        run={
            re.compile(r"git rev-parse --show-toplevel"): Result(str(tmp_path)),
        }
    )
    with pytest.raises(SystemExit):
        release(c, sanity=True)
