#!/bin/bash
set -e

echo "===== Grand River Current Cleanup Script ====="
echo ""

# Check CloudFront distribution status
echo "1. Checking CloudFront distribution status..."
STATUS=$(aws cloudfront get-distribution --id E2GSP9KUBIH3QL --query 'Distribution.Status' --output text 2>/dev/null || echo "NotFound")

if [ "$STATUS" = "NotFound" ]; then
    echo "   ✓ CloudFront distribution already deleted"
elif [ "$STATUS" = "Deployed" ]; then
    echo "   Distribution is deployed and ready to delete"
    echo "   Fetching current ETag..."
    ETAG=$(aws cloudfront get-distribution --id E2GSP9KUBIH3QL --query 'ETag' --output text)
    echo "   Deleting CloudFront distribution E2GSP9KUBIH3QL..."
    aws cloudfront delete-distribution --id E2GSP9KUBIH3QL --if-match "$ETAG"
    echo "   ✓ CloudFront distribution deleted"
else
    echo "   ⚠ Distribution status: $STATUS"
    echo "   Please wait for deployment to complete, then run this script again"
    exit 1
fi

echo ""
echo "2. Deleting SSL certificate for current.quest..."
CERT_ARN="arn:aws:acm:us-east-1:821891894512:certificate/1135563e-147a-4605-b2d0-faa618324d87"
aws acm delete-certificate --certificate-arn "$CERT_ARN" --region us-east-1 2>/dev/null && echo "   ✓ Certificate deleted" || echo "   ⚠ Certificate may be in use or already deleted"

echo ""
echo "3. Checking for CloudFront Functions to clean up..."
# Note: CloudFront Functions can be shared across distributions, so we won't auto-delete them
# Let's just list them for manual review
echo "   Current CloudFront Functions:"
aws cloudfront list-functions --query 'FunctionList.Items[*].Name' --output text

echo ""
echo "4. Summary of remaining AWS resources:"
echo "   S3 Buckets:"
aws s3 ls
echo ""
echo "   CloudFront Distributions:"
aws cloudfront list-distributions --query 'DistributionList.Items[*].[Id,Comment]' --output table
echo ""
echo "   Lambda Functions:"
aws lambda list-functions --query 'Functions[*].FunctionName' --output text

echo ""
echo "===== Cleanup Complete ====="
echo "The website at current.quest should no longer be accessible."
echo ""
echo "Note: DNS records at your domain registrar (if any) should be removed manually."
