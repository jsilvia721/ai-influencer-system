#!/bin/bash

# Configure Replicate API Token
# This script helps you set up your Replicate API token in AWS Secrets Manager

echo "🔑 Replicate API Token Configuration"
echo ""
echo "📋 Current Status:"

# Check current token
CURRENT_TOKEN=$(aws secretsmanager get-secret-value --secret-id "ai-influencer-system-dev-api-keys-mvp" --region us-east-1 --query 'SecretString' --output text | jq -r '.replicate_api_key // "not-found"')

if [ "$CURRENT_TOKEN" = "your-replicate-token" ] || [ "$CURRENT_TOKEN" = "placeholder-token-needs-to-be-updated" ] || [ "$CURRENT_TOKEN" = "not-found" ]; then
    echo "  ❌ Replicate API token is not configured (using placeholder)"
    echo ""
    echo "🔧 To Fix This:"
    echo ""
    echo "1. **Get your Replicate API token:**"
    echo "   - Go to https://replicate.com/account/api-tokens"
    echo "   - Sign in to your Replicate account (create one if needed)"
    echo "   - Create a new API token or copy an existing one"
    echo "   - It should look like: r8_ABC123def456... (starts with 'r8_')"
    echo ""
    echo "2. **Update the secret in AWS:**"
    echo "   Replace YOUR_ACTUAL_TOKEN below with your real token:"
    echo ""
    echo "   aws secretsmanager update-secret --secret-id \"ai-influencer-system-dev-api-keys-mvp\" \\"
    echo "     --region us-east-1 \\"
    echo "     --secret-string '{\"replicate_api_key\": \"YOUR_ACTUAL_TOKEN\"}'"
    echo ""
    echo "3. **Test the training system:**"
    echo "   ./test_webhook_training.sh"
    echo ""
    echo "💡 Example (replace with your actual token):"
    echo "   aws secretsmanager update-secret --secret-id \"ai-influencer-system-dev-api-keys-mvp\" \\"
    echo "     --region us-east-1 \\"
    echo "     --secret-string '{\"replicate_api_key\": \"r8_ABC123def456ghi789jkl012mno345\"}'"
    echo ""
else
    echo "  ✅ Replicate API token is configured"
    echo "  Token: ${CURRENT_TOKEN:0:10}... (showing first 10 chars)"
    echo ""
    echo "🧪 You can now test the training system:"
    echo "   ./test_webhook_training.sh"
fi

echo ""
echo "📊 Cost Information:"
echo "  - Flux Dev model costs ~$0.003 per image"
echo "  - Generating 15 training images costs ~$0.045"
echo "  - Much cheaper than the original Flux 1.1 Pro model!"
