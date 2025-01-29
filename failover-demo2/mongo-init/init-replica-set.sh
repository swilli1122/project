#!/bin/bash
set -e

# Helper function to wait for MongoDB readiness
wait_for_mongo() {
    local host=$1
    echo "$(date) - Waiting for MongoDB at $host..."
    while true; do
        if mongosh --host "$host" --eval "db.runCommand({ ping: 1 }).ok" | grep -q "1"; then
            echo "$(date) - MongoDB at $host is ready."
            break
        else
            echo "$(date) - MongoDB at $host not ready. Retrying..."
            sleep 5
        fi
    done
}

# Wait for both MongoDB nodes
wait_for_mongo "mongo-1:27017"
wait_for_mongo "mongo-2:27017"
sleep 10

# Initialize replica set
echo "$(date) - Initializing replica set on mongo-1:27017..."
mongosh --host "mongo-1:27017" <<EOF
rs.initiate({
    _id: "rs0",
    members: [
        { _id: 0, host: "mongo-1:27017" },
        { _id: 1, host: "mongo-2:27017" }
    ]
});
EOF

echo "$(date) - Replica set initialization complete."
