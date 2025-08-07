#!/bin/bash

# Deploy Improved Training Image Generator Lambda Function
# This script updates the training image generator with the improved version

set -e

echo "🚀 Deploying Improved Training Image Generator Lambda Function..."

# Navigate to the terraform directory
cd /Users/josh/dev/ai-influencer-system/terraform

echo "📦 Creating training image generator deployment package..."

# Create training_image_generator.zip with the improved version
echo "  - Creating training_image_generator.zip with improved version"
cd ../lambda
zip -r ../terraform/training_image_generator.zip training_image_generator_improved.py

# Rename the file inside the zip to match expected name
cd ../terraform
mkdir -p temp_training_extract
cd temp_training_extract
unzip -q ../training_image_generator.zip
mv training_image_generator_improved.py training_image_generator.py
zip -r ../training_image_generator.zip training_image_generator.py
cd ..
rm -rf temp_training_extract

echo "🏗️  Applying Terraform changes..."

# Initialize terraform (if needed)
terraform init

# Plan the changes
echo "📋 Planning infrastructure changes..."
terraform plan -target=aws_lambda_function.training_image_generator

# Apply the changes (only target the training image generator function)
echo "🛠️  Applying infrastructure changes..."
terraform apply -auto-approve -target=aws_lambda_function.training_image_generator

echo "✅ Training Image Generator deployment completed successfully!"

# Get function information
FUNCTION_NAME=$(aws lambda get-function --function-name "ai-influencer-mvp-dev-training-image-generator" --query 'Configuration.FunctionName' --output text 2>/dev/null || echo "Function not found")

echo ""
echo "🌐 Deployment Summary:"
echo "  Lambda Function Name: $FUNCTION_NAME"
echo "  Handler: training_image_generator.lambda_handler"
echo "  Runtime: python3.9"
echo ""
echo "🔧 Features in Improved Version:"
echo "  ✅ Robust retry mechanism - continues until target images are generated"
echo "  ✅ Real-time progress tracking with current_attempt, max_attempts"
echo "  ✅ Success rate calculation and monitoring"
echo "  ✅ Dynamic max attempts calculation (num_images * 2 + 3, capped at 25)"
echo "  ✅ Better error handling and progress updates"
echo "  ✅ Compatible with frontend expectations (current_attempt, success_rate fields)"
echo ""
echo "🧪 Next Steps:"
echo "  1. Test the function through your frontend UI"
echo "  2. Monitor the DynamoDB table to see the improved progress tracking"
echo "  3. Verify that the frontend shows real-time progress updates"
echo "  4. Check that retry mechanism works by generating training images"
