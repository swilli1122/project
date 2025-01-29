from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from typing import Dict, Any, Optional
import logging
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class MongoDBHandler:
    def __init__(self, settings):
        self.settings = settings
        self.client = None
        self.db = None
        self.collection = None
    
    async def is_healthy(self) -> bool:
        """Check if MongoDB is healthy."""
        try:
            await self.client.admin.command('ping')
            return True
        except Exception as e:
            logger.error(f"MongoDB health check failed: {str(e)}")
            return False

    async def connect(self):
        """Connect to MongoDB."""
        try:
            self.client = AsyncIOMotorClient(
                self.settings.MONGODB_URI,
                serverSelectionTimeoutMS=self.settings.MONGODB_CONNECT_TIMEOUT,
                maxPoolSize=self.settings.MONGODB_MAX_POOL_SIZE
            )
            
            self.db = self.client[self.settings.MONGODB_DATABASE]
            self.collection = self.db[self.settings.MONGODB_COLLECTION]
            
            # Create indexes
            await self.collection.create_index("transaction_id", unique=True)
            await self.collection.create_index("timestamp")
            await self.collection.create_index("status")
            
            logger.info("Connected to MongoDB successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise

    async def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("Closed MongoDB connection")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def save_transaction(self, transaction: Dict[str, Any]) -> bool:
        """Save transaction to MongoDB."""
        try:
            result = await self.collection.update_one(
                {"transaction_id": transaction["transaction_id"]},
                {"$set": {**transaction, "updated_at": datetime.utcnow()}},
                upsert=True
            )
            logger.info(f"Saved transaction: {transaction['transaction_id']}")
            return True
        except Exception as e:
            logger.error(f"Failed to save transaction: {str(e)}")
            return False

    async def get_transaction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve transaction by ID."""
        try:
            transaction = await self.collection.find_one(
                {"transaction_id": transaction_id},
                {"_id": 0}
            )
            return transaction
        except Exception as e:
            logger.error(f"Failed to retrieve transaction: {str(e)}")
            return None
            
    async def get_failed_transactions(self, limit: int = 1000):
        """Retrieve failed transactions that haven't exceeded retry limit."""
        try:
            failed_transactions = []
            cursor = self.collection.find({
                "status": "failed",
                "$or": [
                    {"retry_count": {"$exists": False}},
                    {"retry_count": {"$lt": self.settings.MAX_RETRIES}}
                ]
            }).limit(limit)
            
            async for doc in cursor:
                doc['_id'] = str(doc['_id'])  # Convert ObjectId to string
                failed_transactions.append(doc)
            
            return failed_transactions
            
        except Exception as e:
            logger.error(f"Failed to retrieve failed transactions: {str(e)}")
            return []
            
        async def get_retry_metrics(self):
            """Get metrics about retry attempts."""
            try:
                pipeline = [
                    {
                        "$group": {
                            "_id": "$status",
                            "count": {"$sum": 1},
                            "avg_retries": {
                                "$avg": {
                                    "$cond": [
                                        {"$exists": ["$retry_count"]},
                                        "$retry_count",
                                        0
                                    ]
                                }
                            }
                        }
                    }
                ]
                
                result = await self.collection.aggregate(pipeline).to_list(None)
                return {doc["_id"]: {
                    "count": doc["count"],
                    "avg_retries": round(doc["avg_retries"], 2)
                } for doc in result}
                
            except Exception as e:
                logger.error(f"Failed to get retry metrics: {str(e)}")
                return {}
            
    async def update_transaction_status(self, transaction_id: str, status: str) -> bool:
        """Update transaction status."""
        try:
            result = await self.collection.update_one(
                {"transaction_id": transaction_id},
                {
                    "$set": {
                        "status": status,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to update transaction status: {str(e)}")
            return False

    async def get_processed_count(self) -> int:
        """Get count of processed transactions."""
        try:
            return await self.collection.count_documents({"status": "completed"})
        except Exception as e:
            logger.error(f"Failed to get processed count: {str(e)}")
            return 0

    async def get_failed_count(self) -> int:
        """Get count of failed transactions."""
        try:
            return await self.collection.count_documents({"status": "failed"})
        except Exception as e:
            logger.error(f"Failed to get failed count: {str(e)}")
            return 0

    async def get_average_processing_time(self) -> float:
        """Get average transaction processing time."""
        try:
            pipeline = [
                {
                    "$match": {
                        "status": "completed"
                    }
                },
                {
                    "$project": {
                        "processing_time": {
                            "$subtract": ["$updated_at", "$timestamp"]
                        }
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "average_time": {
                            "$avg": "$processing_time"
                        }
                    }
                }
            ]

            result = await self.collection.aggregate(pipeline).to_list(length=1)
            return result[0]["average_time"] if result else 0.0
        except Exception as e:
            print(f"Error calculating average processing time: {e}")
            return 0.0
