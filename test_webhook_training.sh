#!/bin/bash

# Test Webhook-Enabled Training Image Generator
# This script tests the webhook-enabled system with real Replicate integration

set -e

echo "🧪 Testing Webhook-Enabled Training Image Generator..."

# Test payload - small number for quick testing
TEST_PAYLOAD='{
  "character_name": "Test Webhook Character",
  "character_description": "A beautiful woman with long dark hair, 25 years old, professional photo style",
  "character_id": "webhook-test-123",
  "num_images": 2
}'

echo "📝 Test Payload (webhook-enabled):"
echo "$TEST_PAYLOAD" | jq .

echo ""
echo "🚀 Invoking webhook-enabled Lambda function..."

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
    RESPONSE_BODY=$(cat response.json)
    echo "$RESPONSE_BODY" | jq .
    
    # Extract job ID for monitoring
    JOB_ID=$(echo "$RESPONSE_BODY" | jq -r '.job_id // .body | fromjson | .job_id // empty' 2>/dev/null || echo "")
    
    if [ -n "$JOB_ID" ] && [ "$JOB_ID" != "null" ]; then
        echo ""
        echo "🔍 Monitoring job: $JOB_ID"
        
        # Monitor the job for up to 2 minutes
        MAX_WAIT=120
        WAIT_TIME=0
        POLL_INTERVAL=5
        
        echo "  Monitoring webhook updates for up to $MAX_WAIT seconds..."
        
        while [ $WAIT_TIME -lt $MAX_WAIT ]; do
            sleep $POLL_INTERVAL
            WAIT_TIME=$((WAIT_TIME + POLL_INTERVAL))
            
            # Query DynamoDB for job status
            JOB_STATUS=$(aws dynamodb get-item \
              --table-name "ai-influencer-training-jobs" \
              --region us-east-1 \
              --key "{\"job_id\": {\"S\": \"$JOB_ID\"}}" \
              --query 'Item' \
              --output json 2>/dev/null || echo "null")
            
            if [ "$JOB_STATUS" != "null" ] && [ -n "$JOB_STATUS" ]; then
                # Parse the status
                STATUS=$(echo "$JOB_STATUS" | jq -r '.status.S // "unknown"')
                COMPLETED=$(echo "$JOB_STATUS" | jq -r '.completed_images.N // "0"')
                TOTAL=$(echo "$JOB_STATUS" | jq -r '.total_images.N // "0"')
                PREDICTIONS=$(echo "$JOB_STATUS" | jq -r '.replicate_predictions // []' 2>/dev/null || echo "[]")
                
                # Count predictions by status
                SUBMITTED=$(echo "$PREDICTIONS" | jq '[.[] | select(.status == "submitted")] | length' 2>/dev/null || echo "0")
                SUCCEEDED=$(echo "$PREDICTIONS" | jq '[.[] | select(.status == "succeeded")] | length' 2>/dev/null || echo "0")
                FAILED=$(echo "$PREDICTIONS" | jq '[.[] | select(.status == "failed")] | length' 2>/dev/null || echo "0")
                
                echo "    [$WAIT_TIME s] Status: $STATUS | Images: $COMPLETED/$TOTAL | Predictions: $SUCCEEDED succeeded, $FAILED failed, $SUBMITTED submitted"
                
                if [ "$STATUS" = "completed" ]; then
                    echo "  ✅ Job completed!"
                    break
                fi
            else
                echo "    [$WAIT_TIME s] Job not found in DynamoDB yet..."
            fi
        done
        
        if [ $WAIT_TIME -ge $MAX_WAIT ]; then
            echo "  ⏰ Monitoring timeout reached"
        fi
        
        # Final status check
        echo ""
        echo "📊 Final Job Status:"
        aws dynamodb get-item \
          --table-name "ai-influencer-training-jobs" \
          --region us-east-1 \
          --key "{\"job_id\": {\"S\": \"$JOB_ID\"}}" \
          --query 'Item' \
          --output json | jq '{
            job_id: .job_id.S,
            status: .status.S,
            total_images: .total_images.N,
            completed_images: .completed_images.N,
            current_attempt: .current_attempt.N,
            max_attempts: .max_attempts.N,
            success_rate: .success_rate.N,
            webhook_predictions: (.replicate_predictions | length),
            created_at: .created_at.S,
            updated_at: .updated_at.S
        }' 2>/dev/null || echo "Could not retrieve final status"
        
    else
        echo "❌ Could not extract job ID from response"
    fi
    
    rm response.json
else
    echo "❌ No response file created"
fi

echo ""
echo "🔧 Check CloudWatch Logs:"
echo "  Training Generator: /aws/lambda/ai-influencer-system-dev-training-image-generator"
echo "  Webhook Handler: /aws/lambda/ai-influencer-system-dev-replicate-webhook-handler"
echo ""
echo "✅ Webhook test completed!"
echo ""
echo "💡 Expected Webhook Behavior:"
echo "  - Predictions submitted immediately to Replicate with webhook URL"
echo "  - Replicate POSTs back to webhook as images complete"
echo "  - DynamoDB updated in real-time via webhook handler"
echo "  - No polling delays - instant status updates!"
echo ""
echo "🐞 If images aren't completing:"
echo "  1. Check Replicate API token in AWS Secrets Manager"
echo "  2. Verify webhook endpoint is accessible from Replicate"
echo "  3. Check CloudWatch logs for webhook activity"
