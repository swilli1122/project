from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from contextlib import asynccontextmanager
import logging

from .config import Settings
from .models import Transaction, TransactionResponse
from .kafka_handler import KafkaHandler
from .mongo_handler import MongoDBHandler
from .retry_handler import RetryHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load settings
settings = Settings()

# Initialize handlers
kafka_handler = KafkaHandler(settings)
mongo_handler = MongoDBHandler(settings)
retry_handler = RetryHandler(kafka_handler, mongo_handler, settings)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up application...")

    # Initialize MongoDB first
    await mongo_handler.connect()

    # Initialize Kafka and set MongoDB handler
    await kafka_handler.start()
    kafka_handler.set_mongo_handler(mongo_handler)

    # Start retry handler
    await retry_handler.start()

    yield

    # Shutdown
    logger.info("Shutting down application...")
    await retry_handler.stop()
    await kafka_handler.stop()
    await mongo_handler.close()

app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Prometheus metrics
Instrumentator().instrument(app).expose(app)

@app.get("/metrics/retries")
async def get_retry_metrics():
    """Get metrics about transaction retries."""
    return await mongo_handler.get_retry_metrics()

@app.get("/health", response_model=dict)
async def health_check():
    is_mongo_healthy = await mongo_handler.is_healthy()
    is_kafka_healthy = await kafka_handler.is_healthy()
    return {
        "mongo": is_mongo_healthy,
        "kafka": is_kafka_healthy,
        "status": "ok" if is_mongo_healthy and is_kafka_healthy else "degraded"
    }


@app.post("/transaction", response_model=TransactionResponse)
async def process_transaction(transaction: Transaction, background_tasks: BackgroundTasks):
    """Process incoming transaction."""
    try:
        # Log transaction receipt
        logger.info(f"Received transaction: {transaction.transaction_id}")

        # Send to Kafka in background
        background_tasks.add_task(
            kafka_handler.send_message,
            "transactions",
            transaction.model_dump()
        )

        return TransactionResponse(
            transaction_id=transaction.transaction_id,
            status="accepted",
            message="Transaction is being processed"
        )

    except Exception as e:
        logger.error(f"Error processing transaction: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing transaction: {str(e)}"
        )

@app.get("/transactions/{transaction_id}")
async def get_transaction(transaction_id: str):
    """Retrieve transaction by ID."""
    transaction = await mongo_handler.get_transaction(transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction