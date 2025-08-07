#!/bin/bash

# Build and Prepare Frontend for Deployment
# This script builds the React frontend for production deployment

set -e

echo "🌟 Building AI Influencer Frontend for Production..."

# Navigate to frontend directory
cd /Users/josh/dev/ai-influencer-system/ai-influencer-ui

echo "📦 Installing/updating dependencies..."
npm install

echo "🏗️  Building production bundle..."

# Set production environment variable
export REACT_APP_USE_MOCK_API=false

# Build the production version
npm run build

echo "✅ Build completed successfully!"

echo ""
echo "📁 Build Output:"
ls -la build/

echo ""
echo "📊 Build Statistics:"
du -sh build/
echo "Static files:"
find build/static -type f -name "*.js" -o -name "*.css" | wc -l | xargs echo "  JS/CSS files:"
echo "  Total files:" $(find build/ -type f | wc -l)

echo ""
echo "🚀 Deployment Options:"
echo ""
echo "Option 1: Deploy to Vercel"
echo "  1. Install Vercel CLI: npm i -g vercel"
echo "  2. Run: vercel --prod"
echo "  3. Follow the prompts"
echo ""
echo "Option 2: Deploy to Netlify"
echo "  1. Upload the 'build' folder contents to Netlify"
echo "  2. Or use Netlify CLI: npm i -g netlify-cli && netlify deploy --prod --dir=build"
echo ""
echo "Option 3: Static File Hosting"
echo "  1. Copy the contents of the 'build' folder to your web server"
echo "  2. Ensure your server handles SPA routing correctly"
echo ""
echo "🔧 Environment Variables for Production:"
echo "  REACT_APP_USE_MOCK_API=false (already set in build)"
echo ""
echo "📋 Post-Deployment Checklist:"
echo "  - [ ] Verify frontend loads correctly"
echo "  - [ ] Test character management features"
echo "  - [ ] Test training image generation with real-time progress"
echo "  - [ ] Check that all API calls work correctly"
echo "  - [ ] Verify error handling works as expected"
