#!/bin/bash

REPORT="TEST_REPORT.md"
TIMESTAMP=$(date)

echo "# Grand River Current: System Health Report" > $REPORT
echo "**Timestamp:** $TIMESTAMP" >> $REPORT
echo "" >> $REPORT
echo "| Category | Test | Status | Details |" >> $REPORT
echo "| :--- | :--- | :--- | :--- |" >> $REPORT

# 1. Frontend
echo "Checking Frontend..."
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://grand-river-current-1767823978.s3-website-us-east-1.amazonaws.com)
if [ "$FRONTEND_STATUS" == "200" ]; then
    echo "| Frontend | S3 Hosting | ✅ PASS | HTTP 200 |" >> $REPORT
else
    echo "| Frontend | S3 Hosting | ❌ FAIL | HTTP $FRONTEND_STATUS |" >> $REPORT
fi

# 2. API Reader
echo "Checking API..."
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://dke47c3cr49qs.cloudfront.net?stop_id=1001")
if [ "$API_STATUS" == "200" ]; then
    echo "| API | Reader Response | ✅ PASS | HTTP 200 |" >> $REPORT
else
    echo "| API | Reader Response | ❌ FAIL | HTTP $API_STATUS |" >> $REPORT
fi

# 3. Ingest Heartbeat
echo "Checking Ingest Heartbeat..."
UPDATED_AT=$(aws dynamodb get-item --table-name GRT_Bus_State --key '{"PK": {"S": "BUS_ALL"}}' --query 'Item.updated_at.N' --output text)
NOW=$(date +%s)
AGE=$((NOW - UPDATED_AT))
if [ "$AGE" -lt 300 ]; then
    echo "| Ingest | Heartbeat (Live) | ✅ PASS | Data Age: ${AGE}s |" >> $REPORT
else
    echo "| Ingest | Heartbeat (Live) | ❌ FAIL | Data Age: ${AGE}s (Old) |" >> $REPORT
fi

# 4. Database Static Data
echo "Checking Database Integrity..."
STOP_COUNT=$(aws dynamodb query --table-name GRT_Bus_State --key-condition-expression "PK = :pk" --expression-attribute-values '{":pk": {"S": "STOP#1001"}}' --select "COUNT" --query "Count" --output text)
if [ "$STOP_COUNT" -gt 0 ]; then
    echo "| Database | Static Stops | ✅ PASS | Stop 1001 Found |" >> $REPORT
else
    echo "| Database | Static Stops | ❌ FAIL | Stop 1001 Missing |" >> $REPORT
fi

# 5. History Logging
echo "Checking History Logging..."
# We use a limited scan to see if any BUS_HISTORY# exists
HISTORY_FOUND=$(aws dynamodb scan --table-name GRT_Bus_State --limit 20 --filter-expression "begins_with(PK, :prefix)" --expression-attribute-values '{":prefix": {"S": "BUS_HISTORY#"}}' --query "Count" --output text)
if [ "$HISTORY_FOUND" -gt 0 ]; then
    echo "| History | Unique Record Creation | ✅ PASS | Recent History Found |" >> $REPORT
else
    echo "| History | Unique Record Creation | ❌ FAIL | No Recent History Found |" >> $REPORT
fi

# 6. Logger API
echo "Checking Logger..."
LOGGER_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST https://q3racsvshuvureikmjutrb4fci0lsaom.lambda-url.us-east-1.on.aws/ -H "Content-Type: application/json" -d '{"message": "SystemHealthCheck"}')
if [ "$LOGGER_STATUS" == "202" ]; then
    echo "| Logger | API Acceptance | ✅ PASS | HTTP 202 |" >> $REPORT
else
    echo "| Logger | API Acceptance | ❌ FAIL | HTTP $LOGGER_STATUS |" >> $REPORT
fi

echo "Report generated: $REPORT"
cat $REPORT
