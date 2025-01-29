import random
import time
from datetime import datetime
from faker import Faker
from prometheus_client import start_http_server, Counter, Histogram
import requests
import json

# Prometheus metrics
TRANSACTIONS_GENERATED = Counter('transactions_generated_total', 'Number of transactions generated')
TRANSACTION_LATENCY = Histogram('transaction_latency_seconds', 'Time spent processing transaction')
TRANSACTION_ERRORS = Counter('transaction_errors_total', 'Number of failed transactions')

class TransactionGenerator:
    def __init__(self, load_balancer_url):
        self.fake = Faker()
        self.load_balancer_url = load_balancer_url

    def generate_transaction(self):
        """Generate a realistic credit card transaction."""
        return {
            "transaction_id": str(self.fake.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "amount": round(random.uniform(1.0, 1000.0), 2),
            "card_number": self.fake.credit_card_number(card_type=None),
            "merchant": self.fake.company(),
            "status": "pending"
        }

    def send_transaction(self, transaction):
        """Send transaction to load balancer."""
        try:
            with TRANSACTION_LATENCY.time():
                response = requests.post(
                    f"{self.load_balancer_url}/transaction",
                    json=transaction,
                    timeout=15
                )
                response.raise_for_status()
                TRANSACTIONS_GENERATED.inc()
                return True
        except Exception as e:
            TRANSACTION_ERRORS.inc()
            print(f"Error sending transaction: {e}")
            return False

def main():
    # Start Prometheus metrics server
    start_http_server(8000)

    generator = TransactionGenerator("http://nginx:80")

    # Continuous transaction generation
    while True:
        transaction = generator.generate_transaction()
        generator.send_transaction(transaction)
        # Enforce a 2-second interval between transactions
        time.sleep(2)

if __name__ == "__main__":
    main()
