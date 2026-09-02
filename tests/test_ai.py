# ruff: noqa: SLF001

from pathlib import Path

import pytest

from conjuring.spells import ai


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
    assert quick_rows == [("quick", "test", "draft", "")]


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
