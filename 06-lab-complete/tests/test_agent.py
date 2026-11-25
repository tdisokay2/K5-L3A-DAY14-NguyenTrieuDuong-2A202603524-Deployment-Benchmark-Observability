"""Behavior tests with an explicitly simulated Redis, not deployment evidence."""
import json
import logging
import secrets
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import fakeredis
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import auth, config, cost_guard, main, rate_limiter, redis_client


@pytest.fixture
def agent(monkeypatch):
    settings = replace(config.settings, agent_api_key=secrets.token_hex(24),
                       rate_limit_per_minute=5, daily_budget_usd=1, monthly_budget_usd=10)
    server = fakeredis.FakeServer()
    store = fakeredis.FakeRedis(server=server, decode_responses=True)
    store.test_server = server
    for module in (auth, cost_guard, rate_limiter):
        monkeypatch.setattr(module, "settings", settings)
    for module in (redis_client, cost_guard, rate_limiter, main):
        monkeypatch.setattr(module, "r", store)
    monkeypatch.setattr(main, "llm_ask", lambda question: "Mock answer")
    with TestClient(main.app) as client:
        yield client, store, settings


def test_auth_validation_and_outage(agent):
    client, store, settings = agent
    headers = {"X-API-Key": settings.agent_api_key}
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200
    for supplied in ({}, {"X-API-Key": "invalid"}):
        assert client.post("/ask", json={"question": "Hello"}, headers=supplied).status_code == 401
    for body in ({}, {"question": ""}, {"question": "x" * 2001}):
        assert client.post("/ask", json=body, headers=headers).status_code == 422
    response = client.post("/ask", json={"question": "Hello"}, headers=headers)
    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    assert response.json()["usage"]["cost_usd"] > 0
    store.test_server.connected = False
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 503
    assert client.post("/ask", json={"question": "Hello"}, headers=headers).status_code == 503


def test_atomic_limit_shared_by_clients_and_expires(agent, monkeypatch):
    _, store, settings = agent
    def attempt(_):
        try:
            rate_limiter.check_rate_limit(settings.agent_api_key)
            return 200
        except HTTPException as exc:
            assert int(exc.headers["Retry-After"]) >= 1
            return exc.status_code
    with ThreadPoolExecutor(max_workers=20) as pool:
        codes = list(pool.map(attempt, range(30)))
    assert codes.count(200) == 5
    assert codes.count(429) == 25
    other_client = fakeredis.FakeRedis(server=store.test_server,
                                      decode_responses=True)
    monkeypatch.setattr(rate_limiter, "r", other_client)
    assert attempt(0) == 429
    key = store.keys("rate:*")[0]
    assert settings.agent_api_key not in key
    for member in store.zrange(key, 0, -1):
        store.zadd(key, {member: 0})
    assert attempt(0) == 200


def test_daily_and_monthly_budget_shared_and_expiring(agent):
    client, store, settings = agent
    assert cost_guard.record_cost(1000, 1000) == pytest.approx(0.00075)
    periods = cost_guard._periods()
    for key, _, _ in periods:
        assert int(store.get(key)) == 750000
        assert store.ttl(key) > 0
    for key, _, budget in periods:
        previous = store.get(key)
        store.set(key, round(budget * cost_guard.NANO_USD))
        response = client.post("/ask", json={"question": "Hello"},
                               headers={"X-API-Key": settings.agent_api_key})
        assert response.status_code == 402
        store.set(key, previous)


def test_concurrent_accounting_does_not_lose_updates(agent):
    _, store, _ = agent
    with ThreadPoolExecutor(max_workers=10) as pool:
        list(pool.map(lambda _: cost_guard.record_cost(100, 50), range(40)))
    assert all(int(store.get(key)) == 40 * (100 * 150 + 50 * 600)
               for key, _, _ in cost_guard._periods())


def test_log_json_escapes_special_characters():
    record = logging.LogRecord("test", logging.INFO, "", 0, 'quote " and newline\n', (), None)
    formatted = main.JsonFormatter().format(record)
    assert len(formatted.splitlines()) == 1
    assert json.loads(formatted)["event"] == record.getMessage()


def test_environment_configuration(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "7")
    monkeypatch.setenv("PORT", "8123")
    settings = config.Settings()
    assert (settings.environment, settings.rate_limit_per_minute, settings.port) == ("staging", 7, 8123)
    monkeypatch.setenv("DAILY_BUDGET_USD", "nan")
    with pytest.raises(ValueError):
        config.Settings()
