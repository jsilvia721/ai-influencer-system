#!/bin/bash

# Deploy Sync Lambda Function and Update Infrastructure
# This script creates missing Lambda deployment packages and applies Terraform changes

set -e

echo "🚀 Deploying Sync Lambda Function and Infrastructure Updates..."

# Navigate to the terraform directory
cd /Users/josh/dev/ai-influencer-system/terraform

echo "📦 Creating Lambda deployment packages..."

# Create sync_replicate_jobs.zip
echo "  - Creating sync_replicate_jobs.zip"
cd ../lambda
zip -r ../terraform/sync_replicate_jobs.zip sync_replicate_jobs.py
cd ../terraform

# Create content_generation_service.zip (placeholder)
echo "  - Creating content_generation_service.zip (placeholder)"
echo "print('Content generation service placeholder')" > temp_content_generation.py
zip content_generation_service.zip temp_content_generation.py
rm temp_content_generation.py

# Create replicate_webhook_handler.zip (placeholder)
echo "  - Creating replicate_webhook_handler.zip (placeholder)"
echo "print('Webhook handler placeholder')" > temp_webhook_handler.py
zip replicate_webhook_handler.zip temp_webhook_handler.py
rm temp_webhook_handler.py

# Update existing API handler with current code
echo "  - Updating api_handler.zip"
cd ../lambda
zip -r ../terraform/api_handler.zip api_handler.py
cd ../terraform

echo "🏗️  Applying Terraform changes..."

# Initialize terraform (if needed)
terraform init

# Plan the changes
echo "📋 Planning infrastructure changes..."
terraform plan

# Apply the changes
echo "🛠️  Applying infrastructure changes..."
terraform apply -auto-approve

echo "✅ Deployment completed successfully!"

# Get the API Gateway URL
API_URL=$(terraform output -raw mvp_infrastructure_summary | jq -r '.api_gateway_url' | sed 's|arn:aws:execute-api:|https://|' | sed 's|:us-east-1:[0-9]*:/|.execute-api.us-east-1.amazonaws.com/dev/|')

echo ""
echo "🌐 Infrastructure Summary:"
echo "  API Gateway URL: $API_URL"
echo "  Sync endpoint: $API_URL/sync-replicate"
echo ""
echo "🔧 Next Steps:"
echo "  1. Update secrets in AWS Secrets Manager with your Replicate API key"
echo "  2. Test the sync endpoint: curl -X POST $API_URL/sync-replicate"
echo "  3. The UI sync button should now work!"
