#!/bin/bash

# Deploy Character-Consistent AI Influencer System with Replicate Integration
# This script packages and deploys all Lambda functions

set -e

echo "🚀 Deploying Character-Consistent AI Influencer System..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Clean up previous deployments
print_status "Cleaning up previous Lambda packages..."
rm -f *.zip

# Create Lambda function packages
create_lambda_package() {
    local function_name=$1
    local handler_file=$2
    
    print_status "Creating package for $function_name..."
    
    # Create temporary directory
    temp_dir=$(mktemp -d)
    
    # Copy the function file
    cp "lambda-functions/$handler_file" "$temp_dir/index.py"
    
    # Create the zip package
    cd "$temp_dir"
    zip -r "../$function_name.zip" .
    cd - > /dev/null
    
    # Clean up temp directory
    rm -rf "$temp_dir"
    
    print_success "Package created: $function_name.zip"
}

# Package all Lambda functions
print_status "Packaging Lambda functions..."

create_lambda_package "api_handler" "api_handler.py"
create_lambda_package "database" "database.py"
create_lambda_package "social_poster" "social_poster.py"
create_lambda_package "character_model_manager" "character_model_manager.py"
create_lambda_package "character_media_generator" "character_media_generator.py"
create_lambda_package "lora_training_service" "lora_training_service.py"
create_lambda_package "lora_training_optimizer" "lora_training_optimizer.py"

# Plan Terraform deployment
print_status "Planning Terraform deployment..."
terraform plan -out=tfplan

# Ask for confirmation
echo ""
print_warning "About to deploy the following components:"
echo "  • 8 Lambda functions (including character management)"
echo "  • S3 bucket with lifecycle policies"
echo "  • API Gateway with character endpoints"
echo "  • Secrets Manager for API keys"
echo "  • EventBridge for automated scheduling"
echo "  • IAM roles and policies"
echo ""
echo "Estimated monthly cost: $1-11 (scales with usage)"
echo ""

read -p "Do you want to proceed with deployment? (y/N): " confirm
if [[ $confirm != [yY] && $confirm != [yY][eE][sS] ]]; then
    print_warning "Deployment cancelled by user"
    exit 0
fi

# Deploy with Terraform
print_status "Deploying infrastructure with Terraform..."
terraform apply tfplan

# Get outputs
print_status "Retrieving deployment information..."
terraform output > deployment_info.txt

# Extract API Gateway URL (if available)
if terraform output mvp_infrastructure_summary > /dev/null 2>&1; then
    api_gateway_id=$(terraform output -json mvp_infrastructure_summary | jq -r '.api_gateway_url' | cut -d':' -f6)
    api_url="https://${api_gateway_id}.execute-api.us-east-1.amazonaws.com/dev"
    
    print_success "API Gateway URL: $api_url"
else
    print_warning "Could not retrieve API Gateway URL"
fi

# Clean up
rm -f tfplan

print_success "Deployment completed successfully!"

echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Update API Keys in AWS Secrets Manager:"
echo "   - Go to AWS Console > Secrets Manager"
echo "   - Find 'ai-influencer-mvp-api-keys-mvp'"
echo "   - Update with your actual API keys:"
echo "     • replicate_api_key (required for LoRA training)"
echo "     • kling_api_key (required for video generation)"
echo "     • openai_api_key (for content generation)"
echo ""
echo "2. Test the API endpoints:"
if [[ -n "$api_url" ]]; then
echo "   curl $api_url/"
echo "   curl $api_url/characters"
else
echo "   Check deployment_info.txt for API Gateway URL"
fi
echo ""
echo "3. Create your first character model:"
echo "   POST $api_url/characters"
echo "   {
  \"action\": \"create_character\",
  \"character_data\": {
    \"name\": \"Sofia\",
    \"personality\": \"Tech enthusiast and entrepreneur\",
    \"style_preferences\": {
      \"aesthetic\": \"modern, professional\",
      \"mood\": \"confident, approachable\"
    }
  },
  \"training_images\": [\"base64_encoded_image_1\", ...]
}"
echo ""
echo "4. Generate character-consistent images:"
echo "   POST $api_url/generate/image"
echo "   {
  \"character_id\": \"your-character-id\",
  \"prompt\": \"professional headshot in office setting\"
}"
echo ""
echo "💰 Cost Optimization Tips:"
echo "   • Each LoRA training costs ~$1.50 with Replicate"
echo "   • Image generation costs ~$0.01-0.05 per image"
echo "   • Video generation costs ~$0.10-0.50 per video"
echo "   • Total monthly cost should be $5-50 for typical usage"
echo ""
echo "📚 Documentation:"
echo "   • Replicate LoRA training: https://replicate.com/ostris/flux-dev-lora-trainer"
echo "   • Flux model: https://replicate.com/black-forest-labs/flux-schnell"
echo "   • API documentation: Check the root endpoint for available routes"
echo ""

print_success "Character-Consistent AI Influencer System is ready! 🎉"
