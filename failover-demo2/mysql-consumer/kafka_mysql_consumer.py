import json
import logging
from kafka import KafkaConsumer
from mysql_handler import MySQLHandler
import sys
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KafkaMySQLConsumer:
    def __init__(self, bootstrap_servers, topic, group_id):
        self.topic = topic
        retries = 0
        max_retries = 5
        
        # Initialize MySQL handler
        while retries < max_retries:
            try:
                self.mysql_handler = MySQLHandler()
                break
            except Exception as e:
                logger.error(f"Failed to connect to MySQL (attempt {retries + 1}/{max_retries}): {e}")
                retries += 1
                time.sleep(5)
        
        if retries == max_retries:
            logger.error("Could not connect to MySQL after maximum retries")
            sys.exit(1)

        # Initialize Kafka consumer with retry logic
        retries = 0
        while retries < max_retries:
            try:
                self.consumer = KafkaConsumer(
                    topic,
                    bootstrap_servers=bootstrap_servers,
                    group_id=group_id,
                    auto_offset_reset='earliest',
                    value_deserializer=lambda x: json.loads(x.decode('utf-8')),
                    enable_auto_commit=False
                )
                break
            except Exception as e:
                logger.error(f"Failed to connect to Kafka (attempt {retries + 1}/{max_retries}): {e}")
                retries += 1
                time.sleep(5)
        
        if retries == max_retries:
            logger.error("Could not connect to Kafka after maximum retries")
            sys.exit(1)

    def process_messages(self):
        try:
            logger.info(f"Starting to consume messages from topic: {self.topic}")
            for message in self.consumer:
                try:
                    transaction_data = message.value
                    logger.info(f"Received transaction: {transaction_data['transaction_id']}")
                    
                    # Save to MySQL
                    if self.mysql_handler.save_transaction(transaction_data):
                        logger.info(f"Successfully saved transaction {transaction_data['transaction_id']} to MySQL")
                        self.consumer.commit()
                    else:
                        logger.error(f"Failed to save transaction {transaction_data['transaction_id']}")
                
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    continue

        except Exception as e:
            logger.error(f"Consumer error: {e}")
        finally:
            self.close()

    def close(self):
        logger.info("Closing consumer connections")
        self.consumer.close()
        self.mysql_handler.close()

def main():
    # Configuration
    KAFKA_BOOTSTRAP_SERVERS = ['kafka-1:9092', 'kafka-2:9092']
    KAFKA_TOPIC = 'transactions'
    KAFKA_GROUP_ID = 'mysql-consumer-group'

    consumer = KafkaMySQLConsumer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        topic=KAFKA_TOPIC,
        group_id=KAFKA_GROUP_ID
    )
    
    consumer.process_messages()

if __name__ == "__main__":
    main()