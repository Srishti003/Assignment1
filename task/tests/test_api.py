import asyncio
import time
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as app_db
from app.database import Base, get_db
from app.main import app
from app.config import settings

# Test database in memory
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database_and_config(monkeypatch):
    # Set fast processing delay for test execution
    original_delay = settings.PROCESSING_DELAY_SECONDS
    settings.PROCESSING_DELAY_SECONDS = 0.05
    # Ensure background worker uses testing session
    monkeypatch.setattr(app_db, "SessionLocal", TestingSessionLocal)

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    settings.PROCESSING_DELAY_SECONDS = original_delay


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_check(client):
    """Verify GET / returns HEALTHY status and current_time in ISO UTC format."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert "current_time" in data
    assert data["current_time"].endswith("Z")


def test_webhook_fast_response_and_202(client):
    """Verify webhook returns 202 Accepted quickly."""
    payload = {
        "transaction_id": "txn_perf_001",
        "source_account": "acc_user_1",
        "destination_account": "acc_merchant_1",
        "amount": 1500.0,
        "currency": "INR",
    }
    start = time.perf_counter()
    response = client.post("/v1/webhooks/transactions", json=payload)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert response.status_code == 202
    assert elapsed_ms < 500, f"Response took {elapsed_ms}ms"
    data = response.json()
    assert data["status"] == "ACCEPTED"
    assert data["transaction_id"] == "txn_perf_001"


def test_idempotency_duplicate_webhooks(client):
    """
    Verify duplicate webhooks with same transaction_id:
    - Return 202 Accepted without failure
    - Do not create duplicate rows or duplicate tasks
    """
    payload = {
        "transaction_id": "txn_dup_100",
        "source_account": "acc_user_1",
        "destination_account": "acc_merchant_1",
        "amount": 500.0,
        "currency": "INR",
    }

    # First delivery
    res1 = client.post("/v1/webhooks/transactions", json=payload)
    assert res1.status_code == 202

    # Duplicate delivery (same transaction_id)
    res2 = client.post("/v1/webhooks/transactions", json=payload)
    assert res2.status_code == 202
    assert "already received" in res2.json()["message"]

    # Verify query returns single transaction
    query_res = client.get(f"/v1/transactions/{payload['transaction_id']}")
    assert query_res.status_code == 200
    records = query_res.json()
    assert len(records) == 1
    assert records[0]["transaction_id"] == "txn_dup_100"


def test_transaction_lifecycle_processing_to_processed(client):
    """
    Verify transaction status transitions from PROCESSING to PROCESSED.
    """
    payload = {
        "transaction_id": "txn_lifecycle_01",
        "source_account": "acc_alice",
        "destination_account": "acc_bob",
        "amount": 250.75,
        "currency": "USD",
    }

    post_res = client.post("/v1/webhooks/transactions", json=payload)
    assert post_res.status_code == 202

    # Immediate status should be PROCESSING
    get_res_processing = client.get("/v1/transactions/txn_lifecycle_01")
    assert get_res_processing.status_code == 200
    assert get_res_processing.json()[0]["status"] == "PROCESSING"

    # Allow background coroutine (0.05s) to complete
    time.sleep(0.1)

    # Post-delay status should be PROCESSED
    get_res_processed = client.get("/v1/transactions/txn_lifecycle_01")
    assert get_res_processed.status_code == 200
    data = get_res_processed.json()
    assert len(data) == 1
    txn = data[0]
    assert txn["transaction_id"] == "txn_lifecycle_01"
    assert txn["status"] == "PROCESSED"
    assert txn["created_at"].endswith("Z")
    assert txn["processed_at"] is not None
    assert txn["processed_at"].endswith("Z")


def test_transaction_not_found_returns_404(client):
    """Querying an unknown transaction_id returns 404."""
    response = client.get("/v1/transactions/txn_non_existent")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_invalid_payload_validation(client):
    """Verify invalid payloads (missing fields, negative amount) are rejected with 422."""
    invalid_payload = {
        "transaction_id": "txn_invalid",
        "amount": -50.0,
    }
    response = client.post("/v1/webhooks/transactions", json=invalid_payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_immediate_async_response_before_processing_completes():
    """
    Test using AsyncClient: verify the response is returned immediately (< 500ms)
    while the background task is dispatched.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "transaction_id": "txn_async_immediate_01",
            "source_account": "acc_x",
            "destination_account": "acc_y",
            "amount": 999.0,
            "currency": "INR",
        }
        start = time.perf_counter()
        response = await ac.post("/v1/webhooks/transactions", json=payload)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert response.status_code == 202
        assert elapsed_ms < 500, f"Async post took {elapsed_ms}ms"
