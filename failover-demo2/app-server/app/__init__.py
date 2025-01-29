"""
Transaction Processing Server
---------------------------
A FastAPI application for processing credit card transactions with Kafka and MongoDB integration.
"""

from .app import app
from .models import Transaction, TransactionResponse, TransactionStatus, TransactionError
from .config import Settings
from .kafka_handler import KafkaHandler
from .mongo_handler import MongoDBHandler

__version__ = "1.0.0"
__author__ = "Your Company"

# Export key components for easy importing
__all__ = [
    'app',
    'Transaction',
    'TransactionResponse',
    'TransactionStatus',
    'TransactionError',
    'Settings',
    'KafkaHandler',
    'MongoDBHandler',
]

# Initialize logging
import logging
logging.getLogger(__name__).addHandler(logging.NullHandler())

# Package metadata
metadata = {
    'name': 'transaction-processor',
    'version': __version__,
    'description': 'Transaction processing server with failover capabilities',
    'requires': [
        'fastapi',
        'uvicorn',
        'kafka-python',
        'motor',
        'prometheus-client',
        'pydantic'
    ]
}