from __future__ import annotations

from fastapi.testclient import TestClient

from forensics.models import RootCauseAnalysis

from .conftest import auth_headers, upload_txt


def _trace_with_analysis(client: TestClient, email: str) -> tuple[dict[str, str], str]:
    headers = auth_headers(client, email)
    doc_id = upload_txt(client, headers, "fb.txt", b"billing issue $10")
    run = client.post(f"/v1/documents/{doc_id}/runs", headers=headers).json()
    trace_id = run["trace_id"]
    assert trace_id
    store = client.app.state.app_state.store
    store.save_analysis(
        RootCauseAnalysis(
            trace_id=trace_id,
            judge_model="gpt-4o",
            critiques=[],
            root_cause_explanation="test root cause",
        )
    )
    return headers, trace_id


def test_submit_and_get_feedback_for_own_trace(run_client: TestClient) -> None:
    headers, trace_id = _trace_with_analysis(run_client, "fb_own@example.com")
    post = run_client.post(
        f"/v1/traces/{trace_id}/feedback",
        headers=headers,
        json={"decision": "confirmed", "comment": "Looks correct"},
    )
    assert post.status_code == 200
    body = post.json()
    assert body["trace_id"] == trace_id
    assert body["decision"] == "confirmed"
    assert body["comment"] == "Looks correct"

    get = run_client.get(f"/v1/traces/{trace_id}/feedback", headers=headers)
    assert get.status_code == 200
    assert get.json()["decision"] == "confirmed"


def test_user_cannot_submit_feedback_for_other_users_trace(run_client: TestClient) -> None:
    h_a = auth_headers(run_client, "fb_cross_a@example.com")
    _, trace_id = _trace_with_analysis(run_client, "fb_cross_b@example.com")
    assert (
        run_client.post(
            f"/v1/traces/{trace_id}/feedback",
            headers=h_a,
            json={"decision": "confirmed"},
        ).status_code
        == 404
    )


def test_user_cannot_get_other_users_feedback(run_client: TestClient) -> None:
    h_a = auth_headers(run_client, "fb_get_a@example.com")
    h_b, trace_id = _trace_with_analysis(run_client, "fb_get_b@example.com")
    run_client.post(
        f"/v1/traces/{trace_id}/feedback",
        headers=h_b,
        json={"decision": "overridden"},
    )
    assert run_client.get(f"/v1/traces/{trace_id}/feedback", headers=h_a).status_code == 404


def test_invalid_decision_rejected(run_client: TestClient) -> None:
    headers, trace_id = _trace_with_analysis(run_client, "fb_invalid@example.com")
    r = run_client.post(
        f"/v1/traces/{trace_id}/feedback",
        headers=headers,
        json={"decision": "maybe"},
    )
    assert r.status_code == 422


def test_feedback_without_analysis_rejected(run_client: TestClient) -> None:
    headers = auth_headers(run_client, "fb_no_analysis@example.com")
    doc_id = upload_txt(run_client, headers, "na.txt", b"text")
    run = run_client.post(f"/v1/documents/{doc_id}/runs", headers=headers).json()
    trace_id = run["trace_id"]
    assert trace_id
    assert (
        run_client.post(
            f"/v1/traces/{trace_id}/feedback",
            headers=headers,
            json={"decision": "confirmed"},
        ).status_code
        == 404
    )


def test_feedback_upsert_updates_existing(run_client: TestClient) -> None:
    headers, trace_id = _trace_with_analysis(run_client, "fb_upsert@example.com")
    run_client.post(
        f"/v1/traces/{trace_id}/feedback",
        headers=headers,
        json={"decision": "confirmed"},
    )
    run_client.post(
        f"/v1/traces/{trace_id}/feedback",
        headers=headers,
        json={"decision": "overridden", "comment": "Disagree"},
    )
    body = run_client.get(f"/v1/traces/{trace_id}/feedback", headers=headers).json()
    assert body["decision"] == "overridden"
    assert body["comment"] == "Disagree"


def test_feedback_does_not_change_stored_analysis(run_client: TestClient) -> None:
    headers, trace_id = _trace_with_analysis(run_client, "fb_stable@example.com")
    before = run_client.get(f"/v1/traces/{trace_id}/analysis", headers=headers).json()
    run_client.post(
        f"/v1/traces/{trace_id}/feedback",
        headers=headers,
        json={"decision": "overridden", "comment": "nope"},
    )
    after = run_client.get(f"/v1/traces/{trace_id}/analysis", headers=headers).json()
    assert after == before
