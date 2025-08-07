#!/bin/bash

# Deploy Webhook-Enabled Training Image Generator
# This script deploys the improved training system with Replicate webhooks

set -e

echo "🚀 Deploying Webhook-Enabled Training Image Generator..."

# Navigate to the terraform directory
cd /Users/josh/dev/ai-influencer-system/terraform

echo "📦 Creating deployment packages..."

# Create training_image_generator.zip with the webhook version
echo "  - Creating training_image_generator.zip with webhook support"
cd ../lambda
zip -r ../terraform/training_image_generator.zip training_image_generator_webhook.py

# Rename the file inside the zip to match expected name
cd ../terraform
mkdir -p temp_training_extract
cd temp_training_extract
unzip -q ../training_image_generator.zip
mv training_image_generator_webhook.py training_image_generator.py
zip -r ../training_image_generator.zip training_image_generator.py
cd ..
rm -rf temp_training_extract

# Update the existing replicate webhook handler to support training images
echo "  - Updating replicate_webhook_handler.zip with training image support"
cd ../lambda
zip -r ../terraform/replicate_webhook_handler.zip training_webhook_handler.py

# Rename the file inside the zip to match expected name
cd ../terraform
mkdir -p temp_webhook_extract
cd temp_webhook_extract
unzip -q ../replicate_webhook_handler.zip
mv training_webhook_handler.py replicate_webhook_handler.py
zip -r ../replicate_webhook_handler.zip replicate_webhook_handler.py
cd ..
rm -rf temp_webhook_extract

echo "🏗️  Applying Terraform changes..."

# Initialize terraform (if needed)
terraform init

# Plan the changes for both functions
echo "📋 Planning infrastructure changes..."
terraform plan -target=aws_lambda_function.training_image_generator -target=aws_lambda_function.replicate_webhook_handler

# Apply the changes
echo "🛠️  Applying infrastructure changes..."
terraform apply -auto-approve -target=aws_lambda_function.training_image_generator -target=aws_lambda_function.replicate_webhook_handler

echo "✅ Webhook-enabled deployment completed successfully!"

echo ""
echo "🔧 Checking webhook endpoint availability..."

# Get the API Gateway URL for the webhook
API_GATEWAY_URL="https://9fkbuxy8g6.execute-api.us-east-1.amazonaws.com/dev"
WEBHOOK_URL="$API_GATEWAY_URL/replicate-webhook"

echo "  Webhook URL: $WEBHOOK_URL"

# Test if the webhook endpoint responds
echo "  Testing webhook endpoint..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$WEBHOOK_URL" -H "Content-Type: application/json" -d '{"test": true}' || echo "000")

if [ "$HTTP_STATUS" = "200" ] || [ "$HTTP_STATUS" = "400" ]; then
    echo "  ✅ Webhook endpoint is accessible (HTTP $HTTP_STATUS)"
else
    echo "  ⚠️  Webhook endpoint returned HTTP $HTTP_STATUS"
    echo "  This might be normal if signature verification is required"
fi

echo ""
echo "🌟 Webhook Features Deployed:"
echo "  ✅ Real-time image generation updates via webhooks"
echo "  ✅ No polling required - instant status updates"
echo "  ✅ Improved efficiency and cost savings"
echo "  ✅ Better error handling and progress tracking"
echo "  ✅ Automatic S3 upload when images are ready"
echo ""
echo "📡 Technical Details:"
echo "  - Training images submitted with webhook URL: $WEBHOOK_URL"
echo "  - Replicate will POST status updates to the webhook"
echo "  - DynamoDB updated in real-time as images complete"
echo "  - No more 2-minute polling delays!"
echo ""
echo "🧪 To Test:"
echo "  1. Restart your React dev server to pick up the webhook-enabled backend"
echo "  2. Generate training images through the UI"
echo "  3. Watch for real-time progress updates (should be much faster!)"
echo "  4. Check CloudWatch logs for webhook activity"
echo ""
echo "📊 Expected Behavior:"
echo "  - Images appear in UI as soon as they're generated (not after 2+ minutes)"
echo "  - Progress updates happen in real-time"
echo "  - Success rates are more accurate"
echo "  - Better error handling for failed generations"
