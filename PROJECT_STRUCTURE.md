# AI Influencer System - Project Structure

## Core Components

### `/lambdas/` - AWS Lambda Functions (Clean, Production-Ready)
- `api_handler.py` - Main API Gateway handler (routes all endpoints)
- `content_generation_service.py` - Handles image/video generation via Replicate
- `lora_training_service.py` - Manages LoRA model training
- `training_image_generator.py` - Generates training images for LoRA
- `replicate_webhook_handler.py` - Processes Replicate webhooks

### `/ai-influencer-ui/` - React Frontend
- Next.js application for character management and content generation UI

### `/terraform/` - Infrastructure as Code
- `main.tf` - Complete AWS infrastructure definition
- Defines Lambda functions, API Gateway, S3, DynamoDB, Secrets Manager

### `/lambda/` - Dependencies & Build Artifacts
- Contains Python dependencies and build artifacts for Lambda deployment
- **Note**: This is a working directory, use `/lambdas/` for source code

## Configuration
- `/config/config.yaml` - Application configuration
- `.env.example` - Environment variables template
- `deploy_lambdas.sh` - Deployment script

## Key Architecture

### API Endpoints
- `GET /characters` - List all characters
- `POST /characters` - Create new character
- `POST /generate-content` - Generate images/videos
- `POST /train-lora` - Start LoRA training
- `GET /training-images` - View training images

### AWS Resources
- **API Gateway**: `ai-influencer-system-dev-api`
- **Lambda Functions**: 
  - `ai-influencer-system-dev-api-handler`
  - `ai-influencer-system-dev-character-media-generator`
  - `ai-influencer-system-dev-lora-training-service`
- **S3 Bucket**: `ai-influencer-system-dev-content-bkdeyg`
- **Secrets**: 
  - `replicate-api-token` (Replicate API key)
  - `ai-influencer-system-dev-api-keys-mvp` (Other API keys)

## Current Status
✅ Backend API fully functional
✅ LoRA training working
✅ Character-consistent image generation working
✅ Replicate integration working
🔄 Frontend UI needs updates
