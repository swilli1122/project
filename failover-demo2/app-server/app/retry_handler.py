import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class RetryHandler:
    def __init__(self, kafka_handler, mongo_handler, settings):
        self.kafka_handler = kafka_handler
        self.mongo_handler = mongo_handler
        self.settings = settings
        self.retry_queue = asyncio.Queue()
        self.is_running = False
        self._retry_task = None
        
        # Retry configuration
        self.max_retries = settings.MAX_RETRIES
        self.retry_delay = settings.RETRY_DELAY
        self.retry_backoff = 2  # Exponential backoff multiplier
        
    async def start(self):
        """Start the retry handler."""
        self.is_running = True
        self._retry_task = asyncio.create_task(self._process_retry_queue())
        logger.info("Retry handler started")
        
        # Load any existing failed transactions from MongoDB
        await self._load_failed_transactions()
    
    async def stop(self):
        """Stop the retry handler."""
        self.is_running = False
        if self._retry_task:
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass
        logger.info("Retry handler stopped")
    
    async def add_failed_transaction(self, transaction: Dict[str, Any], retry_count: int = 0):
        """Add a failed transaction to the retry queue."""
        retry_item = {
            'transaction': transaction,
            'retry_count': retry_count,
            'next_retry': datetime.utcnow() + timedelta(
                seconds=self.retry_delay * (self.retry_backoff ** retry_count)
            )
        }
        await self.retry_queue.put(retry_item)
        logger.info(f"Added transaction {transaction['transaction_id']} to retry queue (attempt {retry_count + 1})")
    
    async def _load_failed_transactions(self):
        """Load failed transactions from MongoDB into the retry queue."""
        try:
            failed_transactions = await self.mongo_handler.get_failed_transactions()
            for transaction in failed_transactions:
                retry_count = transaction.get('retry_count', 0)
                if retry_count < self.max_retries:
                    await self.add_failed_transaction(transaction, retry_count)
                    
            logger.info(f"Loaded {len(failed_transactions)} failed transactions into retry queue")
        except Exception as e:
            logger.error(f"Error loading failed transactions: {str(e)}")
    
    async def _process_retry_queue(self):
        """Process transactions in the retry queue."""
        while self.is_running:
            try:
                retry_item = await self.retry_queue.get()
                if datetime.utcnow() >= retry_item['next_retry']:
                    transaction = retry_item['transaction']
                    retry_count = retry_item['retry_count']

                    success = await self._retry_transaction(transaction, retry_count)
                    if not success and retry_count + 1 < self.max_retries:
                        await self.add_failed_transaction(transaction, retry_count + 1)
                    elif not success:
                        await self._mark_permanently_failed(transaction)
                else:
                    await self.retry_queue.put(retry_item)

                # Small delay for retries
                await asyncio.sleep(self.retry_delay)
            except Exception as e:
                logger.error(f"Error in retry queue processing: {str(e)}")
                await asyncio.sleep(self.retry_delay)

    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def _retry_transaction(self, transaction: Dict[str, Any], retry_count: int) -> bool:
        """Attempt to process a failed transaction."""
        try:
            logger.info(f"Retrying transaction {transaction['transaction_id']} (attempt {retry_count + 1})")
            
            # Update retry count and status in transaction
            transaction['retry_count'] = retry_count + 1
            transaction['status'] = 'retrying'
            transaction['last_retry'] = datetime.utcnow().isoformat()
            
            # Save updated status to MongoDB
            await self.mongo_handler.save_transaction(transaction)
            
            # Attempt to process through Kafka again
            await self.kafka_handler.send_message(
                self.settings.KAFKA_TOPIC,
                transaction
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Retry failed for transaction {transaction['transaction_id']}: {str(e)}")
            return False
    
    async def _mark_permanently_failed(self, transaction: Dict[str, Any]):
        """Mark a transaction as permanently failed after all retries exhausted."""
        try:
            transaction['status'] = 'permanently_failed'
            transaction['failed_at'] = datetime.utcnow().isoformat()
            await self.mongo_handler.save_transaction(transaction)
            
            logger.warning(
                f"Transaction {transaction['transaction_id']} marked as permanently failed "
                f"after {transaction.get('retry_count', 0)} retries"
            )
        except Exception as e:
            logger.error(f"Error marking transaction as permanently failed: {str(e)}")