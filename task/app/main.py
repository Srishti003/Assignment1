import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List

from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, Base, get_db
from app.models import Transaction
from app.schemas import (
    WebhookPayload,
    WebhookResponse,
    HealthResponse,
    TransactionResponse,
    format_iso_z,
)
from app.crud import get_transaction_by_id, create_transaction
from app.services import process_transaction_background

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("transaction-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events: initialize database schema on startup."""
    logger.info("Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized successfully.")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="Webhook processing service with rapid acknowledgment and asynchronous background processing.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get(
    "/",
    response_model=HealthResponse,
    summary="Health Check",
    tags=["Health"]
)
def health_check():
    """Returns service health status and current UTC time."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return HealthResponse(status="HEALTHY", current_time=now_utc)


@app.post(
    "/v1/webhooks/transactions",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=WebhookResponse,
    summary="Receive Transaction Webhook",
    tags=["Webhooks"]
)
async def receive_transaction_webhook(
    payload: WebhookPayload,
    db: Session = Depends(get_db)
):
    """
    Receives a transaction webhook from payment processors (e.g., RazorPay).
    - Returns HTTP 202 Accepted immediately (< 500ms).
    - Enforces idempotency: duplicate transactions are acknowledged without re-processing.
    - Dispatches 30-second processing to the background worker via asyncio task.
    """
    txn, is_new = create_transaction(db, payload)

    if is_new:
        logger.info(f"Accepted new transaction: {payload.transaction_id}")
        # Dispatch background worker as an unawaited task on event loop
        asyncio.create_task(process_transaction_background(payload.transaction_id))
        return WebhookResponse(
            status="ACCEPTED",
            message="Transaction received and queued for processing",
            transaction_id=payload.transaction_id
        )
    else:
        logger.info(f"Duplicate webhook received for {payload.transaction_id}. Gracefully skipped reprocessing.")
        return WebhookResponse(
            status="ACCEPTED",
            message="Transaction already received and acknowledged (idempotent)",
            transaction_id=payload.transaction_id
        )


@app.get(
    "/v1/transactions/{transaction_id}",
    response_model=List[TransactionResponse],
    summary="Get Transaction Status",
    tags=["Transactions"]
)
def get_transaction_status(
    transaction_id: str,
    db: Session = Depends(get_db)
):
    """
    Query endpoint to check the processing status and timing of a transaction.
    Matches specification array response format.
    """
    txn = get_transaction_by_id(db, transaction_id)
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{transaction_id}' not found"
        )

    response_item = TransactionResponse(
        transaction_id=txn.transaction_id,
        source_account=txn.source_account,
        destination_account=txn.destination_account,
        amount=txn.amount,
        currency=txn.currency,
        status=txn.status,
        created_at=format_iso_z(txn.created_at),
        processed_at=format_iso_z(txn.processed_at) if txn.processed_at else None,
    )
    return [response_item]
