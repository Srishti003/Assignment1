import asyncio
import logging
import app.database as db_module
from app.config import settings
from app.crud import mark_transaction_processed

logger = logging.getLogger(__name__)


async def process_transaction_background(transaction_id: str, delay_seconds: int = None) -> None:
    """
    Simulate asynchronous payment processing / external API call with configured delay (default 30s),
    then update transaction status to PROCESSED.
    
    Equivalent to BackgroundService / Queue Consumer in .NET.
    """
    if delay_seconds is None:
        delay_seconds = settings.PROCESSING_DELAY_SECONDS

    logger.info(f"[Worker] Received transaction {transaction_id}. Simulating external processing for {delay_seconds}s...")
    
    # Asynchronous non-blocking sleep (does not block HTTP thread/event loop)
    await asyncio.sleep(delay_seconds)

    # Use a new DB session scope for the background task
    db = db_module.SessionLocal()
    try:
        updated = mark_transaction_processed(db, transaction_id)
        if updated:
            logger.info(f"[Worker] Transaction {transaction_id} successfully marked as PROCESSED at {updated.processed_at}")
        else:
            logger.warning(f"[Worker] Transaction {transaction_id} not found during processing update.")
    except Exception as e:
        logger.error(f"[Worker] Error processing transaction {transaction_id}: {e}", exc_info=True)
    finally:
        db.close()
