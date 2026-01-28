#!/bin/bash
set -e

BUCKET_NAME="grt-frontend-821891894512"
DISTRIBUTION_ID="E3AFTJDO0HZHQA"

echo "Syncing frontend to S3 bucket: $BUCKET_NAME..."
aws s3 sync src/frontend s3://$BUCKET_NAME --delete

echo "Invalidating CloudFront cache for distribution: $DISTRIBUTION_ID..."
aws cloudfront create-invalidation --distribution-id $DISTRIBUTION_ID --paths "/*"

echo "Deployment complete!"
