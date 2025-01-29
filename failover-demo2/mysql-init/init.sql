-- Create the transactions table
CREATE TABLE IF NOT EXISTS transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    transaction_id VARCHAR(255) UNIQUE,
    timestamp DATETIME,
    amount DECIMAL(10, 2),
    card_number VARCHAR(255),
    merchant VARCHAR(255),
    status VARCHAR(50),
    raw_data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for frequently accessed columns
CREATE INDEX idx_transaction_id ON transactions(transaction_id);
CREATE INDEX idx_status ON transactions(status);
CREATE INDEX idx_timestamp ON transactions(timestamp);

-- Set character set and collation
ALTER DATABASE kafka_sink CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE transactions CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;