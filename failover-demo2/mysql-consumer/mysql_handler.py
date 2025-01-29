import mysql.connector
import logging

logger = logging.getLogger(__name__)

class MySQLHandler:
    def __init__(self, host="mysql-db", user="kafkauser", password="kafkapassword", database="kafka_sink"):
        self.conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database
        )
        self.cursor = self.conn.cursor()
        self._create_table()

    def _create_table(self):
        """Create the transactions table if it does not exist."""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                transaction_id VARCHAR(255) UNIQUE,
                timestamp DATETIME,
                amount DECIMAL(10, 2),
                card_number VARCHAR(255),
                merchant VARCHAR(255),
                status VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def save_transaction(self, transaction_data):
        """Save transaction data to MySQL."""
        try:
            sql = """
                INSERT INTO transactions (
                    transaction_id, 
                    timestamp, 
                    amount, 
                    card_number, 
                    merchant, 
                    status 
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            values = (
                transaction_data["transaction_id"],
                transaction_data["timestamp"],
                transaction_data["amount"],
                transaction_data["card_number"],
                transaction_data["merchant"],
                transaction_data["status"]
            )
            self.cursor.execute(sql, values)
            self.conn.commit()
            return True
        except mysql.connector.Error as e:
            logger.error(f"Failed to save transaction to MySQL: {e}")
            return False

    def update_transaction_status(self, transaction_id, status):
        """Update transaction status."""
        try:
            sql = "UPDATE transactions SET status = %s WHERE transaction_id = %s"
            self.cursor.execute(sql, (status, transaction_id))
            self.conn.commit()
            return True
        except mysql.connector.Error as e:
            logger.error(f"Failed to update transaction status: {e}")
            return False

    def close(self):
        """Close database connections."""
        self.cursor.close()
        self.conn.close()