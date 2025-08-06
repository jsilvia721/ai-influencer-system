# MVP AWS Infrastructure for AI Social Media Influencer System
# Ultra cost-optimized version focusing on essential features only

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.1"
    }
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Owner       = var.owner
    }
  }
}

# Variables
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "ai-influencer-mvp"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "owner" {
  description = "Project owner/team"
  type        = string
  default     = "ai-team"
}

variable "notification_email" {
  description = "Email address for notifications"
  type        = string
  default     = "admin@example.com"
}

# Data sources
data "aws_caller_identity" "current" {}

# Random suffix for unique naming
resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

# Local values
locals {
  name_prefix = "${var.project_name}-${var.environment}"
  resource_suffix = random_string.suffix.result
  
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Owner       = var.owner
  }
}

# =============================================================================
# STORAGE - Just basic S3 bucket (no CloudFront for MVP)
# =============================================================================

resource "aws_s3_bucket" "content" {
  bucket = "${local.name_prefix}-content-${local.resource_suffix}"
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-content-bucket"
  })
}

resource "aws_s3_bucket_versioning" "content" {
  bucket = aws_s3_bucket.content.id
  versioning_configuration {
    status = "Disabled"  # Save costs
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "content" {
  bucket = aws_s3_bucket.content.id
  
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "content" {
  bucket = aws_s3_bucket.content.id
  
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Simple lifecycle policy to save costs
resource "aws_s3_bucket_lifecycle_configuration" "content" {
  bucket = aws_s3_bucket.content.id
  
  rule {
    id     = "cost_optimization"
    status = "Enabled"
    
    filter {}
    
    expiration {
      days = 90  # Delete files after 90 days
    }
    
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
  }
}

# =============================================================================
# DATABASE - DynamoDB tables for characters and content jobs
# =============================================================================

# Characters table
resource "aws_dynamodb_table" "characters" {
  name           = "ai-influencer-characters"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "id"

  attribute {
    name = "id"
    type = "S"
  }

  tags = local.common_tags
}

# Content jobs table
resource "aws_dynamodb_table" "content_jobs" {
  name           = "ai-influencer-content-jobs"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "job_id"

  attribute {
    name = "job_id"
    type = "S"
  }

  tags = local.common_tags
}

# Training jobs table (for backward compatibility)
resource "aws_dynamodb_table" "training_jobs" {
  name           = "ai-influencer-training-jobs"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "job_id"

  attribute {
    name = "job_id"
    type = "S"
  }

  tags = local.common_tags
}

# Lambda function for database operations (legacy, keeping for compatibility)
resource "aws_lambda_function" "database" {
  filename         = "database.zip"
  function_name    = "${local.name_prefix}-database"
  role            = aws_iam_role.lambda_role.arn
  handler         = "index.handler"
  runtime         = "python3.9"
  timeout         = 30
  memory_size     = 512
  
  environment {
    variables = {
      S3_BUCKET = aws_s3_bucket.content.bucket
      CHARACTERS_TABLE_NAME = aws_dynamodb_table.characters.name
      CONTENT_JOBS_TABLE_NAME = aws_dynamodb_table.content_jobs.name
      TRAINING_JOBS_TABLE_NAME = aws_dynamodb_table.training_jobs.name
    }
  }
  
  tags = local.common_tags
}

# =============================================================================
# API GATEWAY - Single API for all endpoints
# =============================================================================

resource "aws_api_gateway_rest_api" "main" {
  name        = "${local.name_prefix}-api"
  description = "AI Influencer MVP API"
  
  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

# Proxy resource to handle all paths
resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "{proxy+}"
}

# Root method for root path
resource "aws_api_gateway_method" "root" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_rest_api.main.root_resource_id
  http_method   = "ANY"
  authorization = "NONE"
}

# Proxy method for all other paths
resource "aws_api_gateway_method" "proxy" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.proxy.id
  http_method   = "ANY"
  authorization = "NONE"
}

# Root integration
resource "aws_api_gateway_integration" "root" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_rest_api.main.root_resource_id
  http_method             = aws_api_gateway_method.root.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.api_handler.invoke_arn
}

# Proxy integration
resource "aws_api_gateway_integration" "proxy" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.proxy.id
  http_method             = aws_api_gateway_method.proxy.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.api_handler.invoke_arn
}

resource "aws_api_gateway_deployment" "main" {
  depends_on = [
    aws_api_gateway_method.root,
    aws_api_gateway_integration.root,
    aws_api_gateway_method.proxy,
    aws_api_gateway_integration.proxy
  ]
  
  rest_api_id = aws_api_gateway_rest_api.main.id
  stage_name  = var.environment
}

# =============================================================================
# LAMBDA FUNCTIONS - Serverless compute (pay per use)
# =============================================================================

# Main API handler
resource "aws_lambda_function" "api_handler" {
  filename         = "api_handler.zip"
  function_name    = "${local.name_prefix}-api-handler"
  role            = aws_iam_role.lambda_role.arn
  handler         = "api_handler.lambda_handler"
  runtime         = "python3.9"
  timeout         = 30
  memory_size     = 512
  
  environment {
    variables = {
      S3_BUCKET_NAME = aws_s3_bucket.content.bucket
      CHARACTERS_TABLE_NAME = aws_dynamodb_table.characters.name
      CONTENT_JOBS_TABLE_NAME = aws_dynamodb_table.content_jobs.name
      TRAINING_JOBS_TABLE_NAME = aws_dynamodb_table.training_jobs.name
      TRAINING_IMAGE_GENERATOR_FUNCTION_NAME = aws_lambda_function.training_image_generator.function_name
      CONTENT_GENERATION_SERVICE_FUNCTION_NAME = aws_lambda_function.content_generation_service.function_name
      SYNC_REPLICATE_FUNCTION_NAME = aws_lambda_function.sync_replicate_jobs.function_name
      REPLICATE_WEBHOOK_HANDLER_FUNCTION_NAME = aws_lambda_function.replicate_webhook_handler.function_name
      LORA_TRAINER_FUNCTION_NAME = aws_lambda_function.lora_training_service.function_name
    }
  }
  
  tags = local.common_tags
}

# Social media poster
resource "aws_lambda_function" "social_poster" {
  filename         = "social_poster.zip"
  function_name    = "${local.name_prefix}-social-poster"
  role            = aws_iam_role.lambda_role.arn
  handler         = "index.handler"
  runtime         = "python3.9"
  timeout         = 300
  memory_size     = 256
  
  environment {
    variables = {
      S3_BUCKET = aws_s3_bucket.content.bucket
      DATABASE_LAMBDA = aws_lambda_function.database.function_name
    }
  }
  
  tags = local.common_tags
}

# Character Model Manager - LoRA training and character management
resource "aws_lambda_function" "character_model_manager" {
  filename         = "character_model_manager.zip"
  function_name    = "${local.name_prefix}-character-model-manager"
  role            = aws_iam_role.lambda_role.arn
  handler         = "character_model_manager.handler"
  runtime         = "python3.9"
  timeout         = 300
  memory_size     = 512
  
  environment {
    variables = {
      S3_BUCKET_NAME = aws_s3_bucket.content.bucket
      LORA_TRAINING_SERVICE_FUNCTION = aws_lambda_function.lora_training_service.function_name
    }
  }
  
  tags = local.common_tags
}

# Character Media Generator - Flux + Kling integration
resource "aws_lambda_function" "character_media_generator" {
  filename         = "character_media_generator.zip"
  function_name    = "${local.name_prefix}-character-media-generator"
  role            = aws_iam_role.lambda_role.arn
  handler         = "character_media_generator.handler"
  runtime         = "python3.9"
  timeout         = 900  # 15 minutes for video generation
  memory_size     = 1024
  
  environment {
    variables = {
      S3_BUCKET_NAME = aws_s3_bucket.content.bucket
    }
  }
  
  tags = local.common_tags
}

# LoRA Training Service - Replicate integration
resource "aws_lambda_function" "lora_training_service" {
  filename         = "lora_training_service.zip"
  function_name    = "${local.name_prefix}-lora-training-service"
  role            = aws_iam_role.lambda_role.arn
  handler         = "lora_training_service.handler"
  runtime         = "python3.9"
  timeout         = 300
  memory_size     = 512
  
  environment {
    variables = {
      S3_BUCKET_NAME = aws_s3_bucket.content.bucket
    }
  }
  
  tags = local.common_tags
}

# LoRA Training Cost Optimizer
resource "aws_lambda_function" "lora_training_optimizer" {
  filename         = "lora_training_optimizer.zip"
  function_name    = "${local.name_prefix}-lora-training-optimizer"
  role            = aws_iam_role.lambda_role.arn
  handler         = "lora_training_optimizer.handler"
  runtime         = "python3.9"
  timeout         = 60
  memory_size     = 256
  
  environment {
    variables = {
      S3_BUCKET_NAME = aws_s3_bucket.content.bucket
    }
  }
  
  tags = local.common_tags
}

# Training Image Generator - Generate 25 character training images using Flux
resource "aws_lambda_function" "training_image_generator" {
  filename         = "training_image_generator.zip"
  function_name    = "${local.name_prefix}-training-image-generator"
  role            = aws_iam_role.lambda_role.arn
  handler         = "training_image_generator.lambda_handler"
  runtime         = "python3.9"
  timeout         = 900  # 15 minutes for generating 25 images
  memory_size     = 512
  
  environment {
    variables = {
      S3_BUCKET_NAME = aws_s3_bucket.content.bucket
      REPLICATE_API_TOKEN = "${aws_secretsmanager_secret.api_keys.name}:replicate_api_key"
    }
  }
  
  tags = local.common_tags
}

# Content Generation Service - Handles image and video generation with LoRA
resource "aws_lambda_function" "content_generation_service" {
  filename         = "content_generation_service.zip"
  function_name    = "${local.name_prefix}-content-generation-service"
  role            = aws_iam_role.lambda_role.arn
  handler         = "content_generation_service.lambda_handler"
  runtime         = "python3.9"
  timeout         = 900  # 15 minutes for content generation
  memory_size     = 1024
  
  environment {
    variables = {
      S3_BUCKET_NAME = aws_s3_bucket.content.bucket
      CONTENT_JOBS_TABLE_NAME = aws_dynamodb_table.content_jobs.name
      CHARACTERS_TABLE_NAME = aws_dynamodb_table.characters.name
      REPLICATE_API_TOKEN_SECRET = aws_secretsmanager_secret.api_keys.name
    }
  }
  
  tags = local.common_tags
}

# Sync Replicate Jobs - Syncs job statuses with Replicate API
resource "aws_lambda_function" "sync_replicate_jobs" {
  filename         = "sync_replicate_jobs.zip"
  function_name    = "${local.name_prefix}-sync-replicate-jobs"
  role            = aws_iam_role.lambda_role.arn
  handler         = "sync_replicate_jobs.lambda_handler"
  runtime         = "python3.9"
  timeout         = 300  # 5 minutes for sync
  memory_size     = 512
  
  environment {
    variables = {
      CONTENT_JOBS_TABLE_NAME = aws_dynamodb_table.content_jobs.name
      REPLICATE_API_TOKEN_SECRET = aws_secretsmanager_secret.api_keys.name
    }
  }
  
  tags = local.common_tags
}

# Replicate Webhook Handler - Handles webhooks from Replicate
resource "aws_lambda_function" "replicate_webhook_handler" {
  filename         = "replicate_webhook_handler.zip"
  function_name    = "${local.name_prefix}-replicate-webhook-handler"
  role            = aws_iam_role.lambda_role.arn
  handler         = "replicate_webhook_handler.lambda_handler"
  runtime         = "python3.9"
  timeout         = 60  # 1 minute for webhook processing
  memory_size     = 256
  
  environment {
    variables = {
      CONTENT_JOBS_TABLE_NAME = aws_dynamodb_table.content_jobs.name
      CHARACTERS_TABLE_NAME = aws_dynamodb_table.characters.name
    }
  }
  
  tags = local.common_tags
}

# =============================================================================
# IAM ROLES AND POLICIES
# =============================================================================

resource "aws_iam_role" "lambda_role" {
  name = "${local.name_prefix}-lambda-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "${local.name_prefix}-lambda-policy"
  role = aws_iam_role.lambda_role.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:HeadObject"
        ]
        Resource = [
          aws_s3_bucket.content.arn,
          "${aws_s3_bucket.content.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_secretsmanager_secret.api_keys.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Scan",
          "dynamodb:Query"
        ]
        Resource = [
          aws_dynamodb_table.characters.arn,
          aws_dynamodb_table.content_jobs.arn,
          aws_dynamodb_table.training_jobs.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      }
    ]
  })
}

# =============================================================================
# LAMBDA PERMISSIONS
# =============================================================================

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*"
}

# =============================================================================
# EVENTBRIDGE SCHEDULER - For automated character content generation
# =============================================================================

resource "aws_cloudwatch_event_rule" "daily_content" {
  name                = "${local.name_prefix}-daily-content"
  description         = "Trigger daily character content generation"
  schedule_expression = "cron(0 8 * * ? *)"  # 8 AM daily
  
  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "character_media_generator" {
  rule      = aws_cloudwatch_event_rule.daily_content.name
  target_id = "CharacterMediaGeneratorTarget"
  arn       = aws_lambda_function.character_media_generator.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.character_media_generator.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_content.arn
}

# =============================================================================
# SECRETS MANAGER - For API keys
# =============================================================================

resource "aws_secretsmanager_secret" "api_keys" {
  name = "${local.name_prefix}-api-keys-mvp"
  description = "API keys for social media platforms and AI services"
  
  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "api_keys" {
  secret_id = aws_secretsmanager_secret.api_keys.id
  secret_string = jsonencode({
    # Social Media APIs
    openai_api_key = "your-openai-key-here"
    twitter_api_key = "your-twitter-key-here"
    twitter_api_secret = "your-twitter-secret-here"
    instagram_access_token = "your-instagram-token-here"
    
    # Character-consistent media generation APIs
    flux_api_key = "your-flux-api-key-here"
    kling_api_key = "your-kling-api-key-here"
    
    # LoRA training platform APIs
    replicate_api_key = "your-replicate-token-here"
    runpod_api_key = "your-runpod-api-key-here"
    runpod_endpoint_id = "your-runpod-lora-training-endpoint-id"
  })
}

# =============================================================================
# OUTPUTS
# =============================================================================

output "mvp_infrastructure_summary" {
  description = "Summary of Character-Consistent AI Influencer System"
  value = {
    api_gateway_url = aws_api_gateway_rest_api.main.execution_arn
    s3_bucket = aws_s3_bucket.content.bucket
    lambda_functions = {
      api_handler = aws_lambda_function.api_handler.function_name
      character_model_manager = aws_lambda_function.character_model_manager.function_name
      character_media_generator = aws_lambda_function.character_media_generator.function_name
      lora_training_service = aws_lambda_function.lora_training_service.function_name
      social_poster = aws_lambda_function.social_poster.function_name
      database = aws_lambda_function.database.function_name
    }
  }
}

output "mvp_cost_estimation" {
  description = "Estimated monthly costs for MVP"
  value = {
    lambda_compute = "$0-5/month (pay per execution)"
    s3_storage = "$0.50-2/month (depending on usage)"
    api_gateway = "$0-3/month (pay per request)"
    secrets_manager = "$0.40/month"
    eventbridge = "$0-1/month"
    total_estimated = "$1-11/month"
    note = "Costs scale with usage - could be as low as $1-3/month for development"
  }
}

output "next_steps" {
  description = "Next steps for MVP deployment"
  value = {
    step_1 = "Create Lambda deployment packages (zip files)"
    step_2 = "Update API keys in Secrets Manager"
    step_3 = "Test API endpoints"
    step_4 = "Deploy content generation logic"
    step_5 = "Set up social media integrations"
  }
}
