from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import auth_headers
from .test_analysis_feedback import _trace_with_analysis


def _trace_with_feedback(client: TestClient, email: str) -> tuple[dict[str, str], str]:
    headers, trace_id = _trace_with_analysis(client, email)
    client.post(
        f"/v1/traces/{trace_id}/feedback",
        headers=headers,
        json={"decision": "confirmed", "comment": "Root cause looks right"},
    )
    return headers, trace_id


def test_create_list_get_delete_eval_case(run_client: TestClient) -> None:
    headers, trace_id = _trace_with_feedback(run_client, "eval_own@example.com")
    created = run_client.post(
        "/v1/evaluations",
        headers=headers,
        json={"trace_id": trace_id},
    )
    assert created.status_code == 201
    case_id = created.json()["id"]
    assert created.json()["human_decision"] == "confirmed"
    assert created.json()["feedback_id"]

    listed = run_client.get("/v1/evaluations", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    got = run_client.get(f"/v1/evaluations/{case_id}", headers=headers)
    assert got.status_code == 200

    assert run_client.delete(f"/v1/evaluations/{case_id}", headers=headers).status_code == 204
    assert run_client.get(f"/v1/evaluations/{case_id}", headers=headers).status_code == 404


def test_cannot_create_eval_without_feedback(run_client: TestClient) -> None:
    headers, trace_id = _trace_with_analysis(run_client, "eval_nofb@example.com")
    assert (
        run_client.post(
            "/v1/evaluations",
            headers=headers,
            json={"trace_id": trace_id},
        ).status_code
        == 400
    )


def test_user_cannot_access_other_users_eval_case(run_client: TestClient) -> None:
    h_a = auth_headers(run_client, "eval_cross_a@example.com")
    _, trace_id = _trace_with_feedback(run_client, "eval_cross_b@example.com")
    case = run_client.post(
        "/v1/evaluations",
        headers=auth_headers(run_client, "eval_cross_b@example.com"),
        json={"trace_id": trace_id},
    ).json()
    assert run_client.get(f"/v1/evaluations/{case['id']}", headers=h_a).status_code == 404
    assert (
        run_client.delete(f"/v1/evaluations/{case['id']}", headers=h_a).status_code == 404
    )


def test_regression_run_does_not_mutate_stored_analysis(run_client: TestClient) -> None:
    headers, trace_id = _trace_with_feedback(run_client, "eval_regress@example.com")
    case_id = run_client.post(
        "/v1/evaluations",
        headers=headers,
        json={"trace_id": trace_id},
    ).json()["id"]
    before = run_client.get(f"/v1/traces/{trace_id}/analysis", headers=headers).json()
    reg = run_client.post(f"/v1/evaluations/{case_id}/run", headers=headers)
    assert reg.status_code == 200
    body = reg.json()
    assert body["eval_case_id"] == case_id
    assert body["human_decision"] == "confirmed"
    assert "message" in body
    after = run_client.get(f"/v1/traces/{trace_id}/analysis", headers=headers).json()
    assert after == before


def test_analytics_summary_scoped_to_user(run_client: TestClient) -> None:
    headers, trace_id = _trace_with_feedback(run_client, "analytics_a@example.com")
    run_client.post("/v1/evaluations", headers=headers, json={"trace_id": trace_id})
    summary = run_client.get("/v1/analytics/summary", headers=headers)
    assert summary.status_code == 200
    data = summary.json()
    assert data["evaluation_cases"] >= 1
    assert data["feedback_confirmed"] >= 1
    assert data["total_documents"] >= 1
    assert data["total_runs"] >= 1

    other = run_client.get(
        "/v1/analytics/summary",
        headers=auth_headers(run_client, "analytics_b@example.com"),
    )
    assert other.status_code == 200
    assert other.json()["evaluation_cases"] == 0
