#!/bin/bash

# Script to package and deploy Lambda functions
set -e

echo "Creating lambda directory if it doesn't exist..."
mkdir -p lambda

echo "Packaging API handler Lambda function..."
cd lambda
if [ -f "api_handler.zip" ]; then
    rm api_handler.zip
fi

# Create a simple zip with just the handler
zip api_handler.zip api_handler.py

echo "Deploying API handler Lambda function..."
aws lambda update-function-code \
    --function-name ai-influencer-system-dev-api-handler \
    --zip-file fileb://api_handler.zip \
    --region us-east-1

echo "Deployment completed successfully!"
