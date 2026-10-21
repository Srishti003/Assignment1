from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models import Transaction
from app.schemas import WebhookPayload


def get_transaction_by_id(db: Session, transaction_id: str) -> Optional[Transaction]:
    """Retrieve transaction by unique transaction_id."""
    return db.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()


def create_transaction(db: Session, payload: WebhookPayload) -> tuple[Optional[Transaction], bool]:
    """
    Attempt to create a transaction record in PROCESSING status.
    Returns:
        (transaction, is_new):
        - if created successfully: (transaction, True)
        - if already existed (or duplicate conflict): (existing_or_none, False)
    """
    # 1. First-line check
    existing = get_transaction_by_id(db, payload.transaction_id)
    if existing:
        return existing, False

    # 2. Insert with unique constraint protection
    new_txn = Transaction(
        transaction_id=payload.transaction_id,
        source_account=payload.source_account,
        destination_account=payload.destination_account,
        amount=payload.amount,
        currency=payload.currency,
        status="PROCESSING",
        created_at=datetime.now(timezone.utc),
        processed_at=None,
    )
    try:
        db.add(new_txn)
        db.commit()
        db.refresh(new_txn)
        return new_txn, True
    except IntegrityError:
        # Concurrent request inserted the same transaction_id at the same time
        db.rollback()
        existing = get_transaction_by_id(db, payload.transaction_id)
        return existing, False


def mark_transaction_processed(db: Session, transaction_id: str) -> Optional[Transaction]:
    """Transition status from PROCESSING to PROCESSED and set processed_at."""
    txn = get_transaction_by_id(db, transaction_id)
    if txn:
        # Idempotent: only update if still PROCESSING
        if txn.status == "PROCESSING":
            txn.status = "PROCESSED"
            txn.processed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(txn)
    return txn
