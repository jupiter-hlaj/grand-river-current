#!/bin/bash

echo "===== Monitoring CloudFront Distribution ====="
echo "Distribution ID: E2GSP9KUBIH3QL"
echo "Checking status every 30 seconds..."
echo ""

MAX_WAIT=1200  # 20 minutes max
ELAPSED=0
INTERVAL=30

while [ $ELAPSED -lt $MAX_WAIT ]; do
    STATUS=$(aws cloudfront get-distribution --id E2GSP9KUBIH3QL --query 'Distribution.Status' --output text 2>/dev/null || echo "NotFound")
    TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")
    
    echo "[$TIMESTAMP] Status: $STATUS"
    
    if [ "$STATUS" = "Deployed" ]; then
        echo ""
        echo "✓ Distribution is deployed! Starting cleanup..."
        echo ""
        ./cleanup_grt.sh
        exit 0
    elif [ "$STATUS" = "NotFound" ]; then
        echo ""
        echo "⚠ Distribution not found. It may have been deleted already."
        exit 1
    fi
    
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

echo ""
echo "⚠ Timeout reached after $MAX_WAIT seconds"
echo "The distribution is still deploying. Please run ./cleanup_grt.sh manually later."
exit 1
