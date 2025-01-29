from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum

class TransactionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Transaction(BaseModel):
    transaction_id: str = Field(..., description="Unique identifier for the transaction")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    amount: float = Field(..., gt=0, description="Transaction amount")
    card_number: str = Field(..., min_length=13, max_length=19)
    merchant: str = Field(..., min_length=1)
    status: TransactionStatus = Field(default=TransactionStatus.PENDING)
    
    class Config:
        json_schema_extra = {
            "example": {
                "transaction_id": "123e4567-e89b-12d3-a456-426614174000",
                "timestamp": "2024-01-16T12:00:00Z",
                "amount": 100.50,
                "card_number": "4532756279624589",
                "merchant": "Example Store",
                "status": "pending"
            }
        }

class TransactionResponse(BaseModel):
    transaction_id: str
    status: str
    message: str

class TransactionError(BaseModel):
    transaction_id: str
    error_message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)