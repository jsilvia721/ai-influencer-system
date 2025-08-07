#!/bin/bash

# Check Current Configuration Script
echo "🔍 Current Configuration Status:"
echo ""

# Check environment files
echo "📋 Environment Configuration:"
echo "  .env.local file exists: $([ -f ai-influencer-ui/.env.local ] && echo '✅ Yes' || echo '❌ No')"

if [ -f ai-influencer-ui/.env.local ]; then
    echo ""
    echo "📄 Current .env.local contents:"
    cat ai-influencer-ui/.env.local | sed 's/^/    /'
    echo ""
fi

# Check if mock API is disabled
if grep -q "REACT_APP_USE_MOCK_API=false" ai-influencer-ui/.env.local 2>/dev/null; then
    echo "🎯 Mock API Status: ✅ DISABLED (will use real backend)"
else
    echo "🎯 Mock API Status: ⚠️  ENABLED (using mock data)"
fi

echo ""
echo "🚀 Backend Status:"
# Check if Lambda function exists
if aws lambda get-function --function-name "ai-influencer-system-dev-training-image-generator" --region us-east-1 --query 'Configuration.FunctionName' --output text >/dev/null 2>&1; then
    echo "  Lambda Function: ✅ Deployed and Active"
    LAST_MODIFIED=$(aws lambda get-function --function-name "ai-influencer-system-dev-training-image-generator" --region us-east-1 --query 'Configuration.LastModified' --output text)
    echo "  Last Updated: $LAST_MODIFIED"
else
    echo "  Lambda Function: ❌ Not found or not accessible"
fi

echo ""
echo "📡 API Gateway:"
echo "  URL: https://9fkbuxy8g6.execute-api.us-east-1.amazonaws.com/dev"

echo ""
echo "🔧 To Apply Changes:"
echo "  1. If your React dev server is running, stop it (Ctrl+C)"
echo "  2. Start it again with: cd ai-influencer-ui && npm start"
echo "  3. The UI will now use the real backend instead of mock data"
echo ""
echo "🧪 To Test:"
echo "  1. Open the Character Management page"
echo "  2. Go to 'Generate Training Images' tab"
echo "  3. Fill in character details and click 'Generate Training Images'"
echo "  4. Watch for real-time progress updates from the backend"
echo ""
echo "💡 Signs It's Working:"
echo "  - Progress updates should come from real DynamoDB data"
echo "  - Success rates and attempt counts will be realistic"
echo "  - Generated images will be stored in S3"
echo "  - No more 'mock' console messages"
