"""Fail-closed authentication for all agent endpoints, independent of client IP."""

import pytest


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("DEXTER_API_TOKEN", "test-api-token")
    from dexter_flask.app import create_app
    return create_app()


@pytest.mark.parametrize("route", ["run", "stream", "approval", "cancel"])
@pytest.mark.parametrize("header", [None, "", "Basic test-api-token", "Bearer", "Bearer wrong", "Bearer test-api-token extra", "Bearer ü"])
def test_agent_routes_reject_missing_or_invalid_tokens(app, route, header):
    headers = {} if header is None else {"Authorization": header}
    response = app.test_client().post(f"/api/agent/{route}", json={}, headers=headers)
    assert response.status_code == 401
    assert response.json == {"error": "unauthorized"}
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("token", [None, "", "   "])
@pytest.mark.parametrize("route", ["run", "stream", "approval", "cancel"])
def test_missing_configuration_disables_agent_api(monkeypatch, token, route):
    if token is None:
        monkeypatch.delenv("DEXTER_API_TOKEN", raising=False)
    else:
        monkeypatch.setenv("DEXTER_API_TOKEN", token)
    from dexter_flask.app import create_app
    response = create_app().test_client().post(
        f"/api/agent/{route}", json={}, headers={"Authorization": "Bearer test-api-token"}
    )
    assert response.status_code == 503
    assert response.json == {"error": "agent_api_not_configured"}


def test_authorized_request_runs_agent(app, monkeypatch):
    from dexter_flask.routes import agent_api
    monkeypatch.setattr(agent_api, "run_agent_for_message", lambda body: "ANSWER")
    response = app.test_client().post(
        "/api/agent/run", json={"query": "hello"},
        headers={"Authorization": "bEaReR test-api-token"},
    )
    assert response.status_code == 200
    assert response.json == {"answer": "ANSWER"}


def test_health_remains_public(app):
    app.config["DEXTER_API_TOKEN"] = ""
    assert app.test_client().get("/health").status_code == 200


def test_token_in_query_or_forwarded_headers_does_not_authorize(app):
    response = app.test_client().post(
        "/api/agent/run?token=test-api-token", json={},
        headers={"X-Forwarded-For": "127.0.0.1", "X-API-Key": "test-api-token"},
    )
    assert response.status_code == 401


def test_unauthorized_control_requests_do_not_mutate_run(app):
    from dexter_flask.routes import agent_api
    state = agent_api.ApprovalState()
    agent_api._approval_states["protected-run"] = state
    try:
        client = app.test_client()
        approval = client.post("/api/agent/approval", json={"runId": "protected-run", "decision": "allow-session"})
        cancel = client.post("/api/agent/cancel", json={"runId": "protected-run"})
        assert approval.status_code == cancel.status_code == 401
        assert not state.is_cancelled()
        assert state.wait_for_decision(timeout_s=0) == "deny"
    finally:
        agent_api._approval_states.pop("protected-run", None)
