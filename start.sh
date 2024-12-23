#!/bin/bash

# Step 1: Start Elasticsearch service
echo "Starting Elasticsearch..."
docker compose up -d elasticsearch

# Step 2: Check if Elasticsearch service is running
echo "Checking Elasticsearch service status..."
docker ps | grep elasticsearch_container > /dev/null
if [ $? -ne 0 ]; then
    echo "Elasticsearch service failed to start. Exiting."
    exit 1
fi

# Step 3: Wait for Elasticsearch to be ready
echo "Waiting for Elasticsearch to be ready..."
while ! curl -s -o /dev/null -w "%{http_code}" -u elastic:admin1234 http://localhost:9200 | grep -q 200; do
    echo "Elasticsearch is not ready yet. Retrying in 5 seconds..."
    sleep 5
done
echo "Elasticsearch is ready."

# Step 4: Set Kibana system user password and generate token
ES_CONTAINER="elasticsearch_container"
echo "Setting Kibana system user password and generating token..."
TOKEN_VALUE=$(docker exec -i $ES_CONTAINER sh -c '
  curl -s -X POST -u elastic:admin1234 -H "Content-Type: application/json" http://localhost:9200/_security/user/kibana_system/_password -d "{\"password\":\"kibana\"}" > /dev/null
  sleep 5
  bin/elasticsearch-service-tokens create elastic/kibana jobber-kibana | grep "SERVICE_TOKEN" | awk -F " = " "{print \$2}"
')

if [ -z "$TOKEN_VALUE" ]; then
    echo "Failed to retrieve the token from Elasticsearch. Exiting."
    exit 1
else
    echo "Kibana token retrieved: $TOKEN_VALUE"
fi

# Step 5: Update docker-compose.yaml with the new Kibana token
echo "Updating docker-compose.yaml with the new Kibana token..."
if grep -q "ELASTICSEARCH_SERVICEACCOUNT_TOKEN=" docker-compose.yaml; then
  sed -i "s|ELASTICSEARCH_SERVICEACCOUNT_TOKEN=.*|ELASTICSEARCH_SERVICEACCOUNT_TOKEN=$TOKEN_VALUE|" docker-compose.yaml
  echo "Updated ELASTICSEARCH_SERVICEACCOUNT_TOKEN in docker-compose.yaml."
else
  sed -i "/environment:/a\      - ELASTICSEARCH_SERVICEACCOUNT_TOKEN=$TOKEN_VALUE" docker-compose.yaml
  echo "Added ELASTICSEARCH_SERVICEACCOUNT_TOKEN to docker-compose.yaml."
fi

# Validate the update
if grep -q "ELASTICSEARCH_SERVICEACCOUNT_TOKEN=$TOKEN_VALUE" docker-compose.yaml; then
  echo "docker-compose.yaml updated successfully."
else
  echo "Failed to update docker-compose.yaml with the new Kibana token. Exiting."
  exit 1
fi

# Step 6: Start Kibana service
echo "Starting Kibana..."
docker compose up -d kibana
if [ $? -eq 0 ]; then
    echo "Kibana service started successfully."
else
    echo "Failed to start Kibana service. Exiting."
    exit 1
fi

echo "Script completed successfully."
