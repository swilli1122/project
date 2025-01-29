from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
from typing import Dict, Any
import json
import logging
import asyncio
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential
from mysql_handler import MySQLHandler

logger = logging.getLogger(__name__)

class KafkaHandler:
    def __init__(self, settings):
        """Initialize the KafkaHandler with configuration settings."""
        self.settings = settings
        self.producer = None
        self.consumer = None
        self.is_running = False
        self._consumer_task = None
        self.mongo_handler = None  # Placeholder for MongoDB handler
        self.mysql_handler = MySQLHandler()

    def set_mongo_handler(self, mongo_handler):
        """Set the MongoDB handler for persisting transactions."""
        self.mongo_handler = mongo_handler

    async def start(self):
        """Start the Kafka producer and consumer asynchronously."""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.settings.KAFKA_BOOTSTRAP_SERVERS.split(','),
                value_serializer=self.custom_serialize,
                acks='all',
                retries=3,
                max_in_flight_requests_per_connection=1
            )

            self.consumer = KafkaConsumer(
                self.settings.KAFKA_TOPIC,
                bootstrap_servers=self.settings.KAFKA_BOOTSTRAP_SERVERS.split(','),
                group_id=self.settings.KAFKA_CONSUMER_GROUP,
                auto_offset_reset=self.settings.KAFKA_AUTO_OFFSET_RESET,
                enable_auto_commit=self.settings.KAFKA_ENABLE_AUTO_COMMIT,
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )

            self.is_running = True
            self._consumer_task = asyncio.create_task(self._consume_messages())
            logger.info("Kafka handler started successfully")

        except KafkaError as e:
            logger.error(f"Failed to start Kafka handler: {e}")
            raise

    async def stop(self):
        """Stop the Kafka producer and consumer."""
        self.is_running = False
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

        if self.producer:
            self.producer.close()
        if self.consumer:
            self.consumer.close()

        logger.info("Kafka handler stopped")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def send_message(self, topic: str, message: Dict[str, Any]):
        """Send a message to the specified Kafka topic."""
        logger.debug(f"Sending message to Kafka: {message}")

        try:
            future = self.producer.send(topic, message)
            result = await asyncio.to_thread(future.get, timeout=10)
            logger.info(f"Message sent to topic {topic}: {message.get('transaction_id', 'unknown')}")
            return result

        except Exception as e:
            logger.error(f"Failed to send message to Kafka: {e}")
            raise

    async def _consume_messages(self):
        """Consume messages from the Kafka topic and process them."""
        while self.is_running:
            try:
                message_batch = await asyncio.to_thread(self.consumer.poll, timeout_ms=1000)

                for topic_partition, messages in message_batch.items():
                    for message in messages:
                        await self._process_message(message)

            except Exception as e:
                logger.error(f"Error consuming messages: {e}")
                await asyncio.sleep(1)

    async def _process_message(self, message):
        """Process a consumed message and persist it to MongoDB."""
        try:
            transaction_data = message.value

            if 'transaction_id' not in transaction_data:
                raise KeyError("'transaction_id' missing in message")

            logger.info(f"Processing transaction: {transaction_data['transaction_id']}")

            # Update transaction status to processing
            transaction_data['status'] = 'processing'

            if self.mongo_handler:
                saved = await self.mongo_handler.save_transaction(transaction_data)
                if saved:
                    await self.mongo_handler.update_transaction_status(
                        transaction_data['transaction_id'],
                        'completed'
                    )
                    logger.info(f"Transaction {transaction_data['transaction_id']} processed and saved")
                else:
                    await self.mongo_handler.update_transaction_status(
                        transaction_data['transaction_id'],
                        'failed'
                    )
                    logger.error(f"Failed to save transaction {transaction_data['transaction_id']}")
            else:
                logger.error("MongoDB handler not set - cannot persist transaction")
            
            if self.mysql_handler:
                saved = self.mysql_handler.save_transaction(transaction_data)
                if saved:
                    self.mysql_handler.update_transaction_status(transaction_data['transaction_id'], 'completed')
                    logger.info(f"Transaction {transaction_data['transaction_id']} processed and saved to MySQL")
                else:
                    self.mysql_handler.update_transaction_status(transaction_data['transaction_id'], 'failed')
                    logger.error(f"Failed to save transaction {transaction_data['transaction_id']} in MySQL")

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            if self.mongo_handler and 'transaction_id' in message.value:
                await self.mongo_handler.update_transaction_status(
                    message.value['transaction_id'], 'failed'
                )

    def custom_serialize(self, value: Dict[str, Any]) -> bytes:
        """Serialize messages to JSON format and encode to bytes."""
        def json_serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

        try:
            return json.dumps(value, default=json_serializer).encode('utf-8')
        except TypeError as e:
            logger.error(f"Serialization error: {e}")
            raise

    async def is_healthy(self) -> bool:
        """Check if Kafka connection is healthy."""
        try:
            if not self.producer or not self.consumer:
                return False

            test_message = {
                "transaction_id": "health-check",
                "health_check": True,
                "timestamp": datetime.utcnow().isoformat()
            }
            await self.send_message("health_checks", test_message)
            return True

        except Exception as e:
            logger.error(f"Kafka health check failed: {e}")
            return False
