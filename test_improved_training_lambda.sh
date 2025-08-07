#!/bin/bash

# Test the Improved Training Image Generator Lambda Function
# This script tests the deployed function with a small test case

set -e

echo "🧪 Testing Improved Training Image Generator Lambda Function..."

# Test payload
TEST_PAYLOAD='{
  "character_name": "Test Character",
  "character_description": "A beautiful blonde woman, 25 years old, blue eyes, professional photo style",
  "character_id": "test-char-123",
  "num_images": 3
}'

echo "📝 Test Payload:"
echo "$TEST_PAYLOAD" | jq .

echo ""
echo "🚀 Invoking Lambda function..."

# Invoke the Lambda function
RESULT=$(aws lambda invoke \
  --function-name "ai-influencer-system-dev-training-image-generator" \
  --region us-east-1 \
  --payload "$TEST_PAYLOAD" \
  --log-type Tail \
  response.json \
  2>&1)

echo "📄 Lambda Response:"
echo "$RESULT"

echo ""
echo "📋 Response Body:"
if [ -f response.json ]; then
    cat response.json | jq .
    rm response.json
else
    echo "No response file created"
fi

echo ""
echo "🔍 Checking DynamoDB for job status..."

# Wait a moment for DynamoDB update
sleep 2

# Query the most recent job from DynamoDB
LATEST_JOB=$(aws dynamodb scan \
  --table-name "ai-influencer-training-jobs" \
  --region us-east-1 \
  --filter-expression "character_name = :name" \
  --expression-attribute-values '{":name": {"S": "Test Character"}}' \
  --query 'Items | sort_by(@, &created_at.S) | [-1]' \
  --output json)

if [ "$LATEST_JOB" != "null" ] && [ -n "$LATEST_JOB" ]; then
    echo "📊 Latest Job Status:"
    echo "$LATEST_JOB" | jq '{
      job_id: .job_id.S,
      status: .status.S,
      total_images: .total_images.N,
      completed_images: .completed_images.N,
      current_attempt: .current_attempt.N,
      max_attempts: .max_attempts.N,
      success_rate: .success_rate.N,
      created_at: .created_at.S
    }'
else
    echo "❌ No job found in DynamoDB"
fi

echo ""
echo "✅ Test completed! Check the Lambda logs for detailed execution info."
echo ""
echo "🔧 Next Steps:"
echo "  1. Check AWS CloudWatch Logs for the Lambda function execution details"
echo "  2. If successful, the improved features are working correctly"
echo "  3. Test through your frontend UI to see real-time progress updates"
