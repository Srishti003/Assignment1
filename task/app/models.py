from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime
from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    transaction_id = Column(String(128), unique=True, index=True, nullable=False)
    source_account = Column(String(128), nullable=False)
    destination_account = Column(String(128), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(16), nullable=False)
    status = Column(String(32), nullable=False, default="PROCESSING")  # "PROCESSING" or "PROCESSED"
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<Transaction {self.transaction_id} status={self.status}>"
