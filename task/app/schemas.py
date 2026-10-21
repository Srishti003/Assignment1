from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict


class WebhookPayload(BaseModel):
    transaction_id: str = Field(..., min_length=1, max_length=128, json_schema_extra={"example": "txn_abc123def456"})
    source_account: str = Field(..., min_length=1, max_length=128, json_schema_extra={"example": "acc_user_789"})
    destination_account: str = Field(..., min_length=1, max_length=128, json_schema_extra={"example": "acc_merchant_456"})
    amount: float = Field(..., gt=0, json_schema_extra={"example": 1500.0})
    currency: str = Field(..., min_length=3, max_length=3, json_schema_extra={"example": "INR"})


class HealthResponse(BaseModel):
    status: str = Field(default="HEALTHY", json_schema_extra={"example": "HEALTHY"})
    current_time: str = Field(..., json_schema_extra={"example": "2024-01-15T10:30:00Z"})


class WebhookResponse(BaseModel):
    status: str = Field(default="ACCEPTED", json_schema_extra={"example": "ACCEPTED"})
    message: str = Field(default="Transaction received and processing queued", json_schema_extra={"example": "Transaction received and processing queued"})
    transaction_id: str = Field(..., json_schema_extra={"example": "txn_abc123def456"})


def format_iso_z(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    # Ensure UTC timezone and format with trailing 'Z'
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class TransactionResponse(BaseModel):
    transaction_id: str
    source_account: str
    destination_account: str
    amount: float
    currency: str
    status: str
    created_at: str
    processed_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
