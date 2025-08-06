#!/bin/bash

# Deploy MVP AI Influencer System Infrastructure
# Ultra cost-optimized version

echo "🚀 Deploying AI Influencer MVP Infrastructure..."
echo "💰 Target cost: $1-11/month (vs $56-225/month for full version)"
echo ""

# Check if zip files exist
if [ ! -f "api_handler.zip" ] || [ ! -f "database.zip" ] || [ ! -f "content_generator.zip" ] || [ ! -f "social_poster.zip" ]; then
    echo "❌ Lambda zip files not found. Creating them now..."
    cd lambda-functions
    zip -r ../api_handler.zip api_handler.py
    zip -r ../database.zip database.py
    zip -r ../content_generator.zip content_generator.py
    zip -r ../social_poster.zip social_poster.py
    cd ..
    echo "✅ Lambda zip files created"
fi

# Destroy existing infrastructure first (optional)
read -p "🤔 Do you want to destroy the existing infrastructure first? (y/N): " destroy_existing
if [[ $destroy_existing =~ ^[Yy]$ ]]; then
    echo "🧹 Destroying existing infrastructure..."
    terraform destroy -auto-approve
    echo "✅ Existing infrastructure destroyed"
fi

# Deploy MVP infrastructure
echo "🏗️ Deploying MVP infrastructure..."
terraform init
terraform plan -var-file="mvp.tfvars" -out=mvp.plan -target module.storage -target module.database -target module.networking
if [ $? -eq 0 ]; then
    echo "✅ Terraform plan successful"
    
    read -p "🚀 Do you want to apply the MVP infrastructure? (Y/n): " apply_infra
    if [[ ! $apply_infra =~ ^[Nn]$ ]]; then
        terraform apply -var-file="mvp.tfvars" mvp.plan
        if [ $? -eq 0 ]; then
            echo ""
            echo "🎉 MVP Infrastructure deployed successfully!"
            echo ""
            echo "📊 Cost Summary:"
            echo "  • Lambda functions: $0-5/month (pay per execution)"
            echo "  • S3 storage: $0.50-2/month"
            echo "  • API Gateway: $0-3/month (pay per request)"
            echo "  • Secrets Manager: $0.40/month"
            echo "  • EventBridge: $0-1/month"
            echo "  • Total: $1-11/month"
            echo ""
            echo "🔗 Next steps:"
            echo "  1. Update API keys in AWS Secrets Manager"
            echo "  2. Test the API endpoints"
            echo "  3. Add your AI content generation logic"
            echo "  4. Set up social media platform integrations"
            echo ""
            terraform output
        else
            echo "❌ Terraform apply failed"
            exit 1
        fi
    else
        echo "❌ Deployment cancelled"
    fi
else
    echo "❌ Terraform plan failed"
    exit 1
fi
