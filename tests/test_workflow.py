"""Tests for sentinel.workflow."""
import pytest
from sentinel import workflow, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_list_workflows():
    workflows = workflow.list_workflows()
    assert len(workflows) >= 5


def test_get_workflow():
    wf = workflow.get_workflow("start_work_day")
    assert wf is not None
    assert "steps" in wf


def test_get_nonexistent():
    assert workflow.get_workflow("ghost") is None


def test_workflow_steps():
    steps = workflow.workflow_steps("start_work_day")
    assert len(steps) > 0


def test_count_workflows():
    assert workflow.count_workflows() >= 5


def test_search_workflows():
    results = workflow.search_workflows("focus")
    assert len(results) >= 1


def test_search_no_match():
    assert workflow.search_workflows("xyznomatch") == []


def test_create_custom_workflow(conn):
    wfid = workflow.create_custom_workflow(
        conn, "My Workflow", "Custom workflow",
        [{"action": "log_mood"}, {"action": "log_water"}])
    assert wfid > 0


def test_get_custom_workflows(conn):
    workflow.create_custom_workflow(conn, "W1", "", [])
    workflow.create_custom_workflow(conn, "W2", "", [])
    assert len(workflow.get_custom_workflows(conn)) == 2


def test_delete_custom_workflow(conn):
    wfid = workflow.create_custom_workflow(conn, "Del", "", [])
    workflow.delete_custom_workflow(conn, wfid)
    assert workflow.get_custom_workflows(conn) == []


def test_workflow_has_description():
    wf = workflow.get_workflow("deep_focus")
    assert wf["description"]


def test_all_workflows_have_steps():
    for wf in workflow.list_workflows():
        assert "steps" in wf
        assert isinstance(wf["steps"], list)
