from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    # Application settings
    APP_NAME: str = "transaction-processor"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8080
    
    # Kafka settings
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka-1:9092,kafka-2:9092")
    KAFKA_TOPIC: str = "transactions"
    KAFKA_CONSUMER_GROUP: str = "transaction-processor-group"
    KAFKA_AUTO_OFFSET_RESET: str = "earliest"
    KAFKA_ENABLE_AUTO_COMMIT: bool = True
    
    # MongoDB settings
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://mongo-1:27017,mongo-2:27017")
    MONGODB_DATABASE: str = "transactions_db"
    MONGODB_COLLECTION: str = "transactions"
    MONGODB_CONNECT_TIMEOUT: int = 5000
    MONGODB_MAX_POOL_SIZE: int = 10
    
    # Retry settings
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 1  # seconds
    
    class Config:
        env_file = ".env"