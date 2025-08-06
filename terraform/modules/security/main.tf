# Security Module
# Creates security groups, IAM roles, and security policies

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where security groups will be created"
  type        = string
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access resources"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# Security Group for API Gateway and Load Balancer
resource "aws_security_group" "api" {
  name_prefix = "${var.name_prefix}-api-"
  vpc_id      = var.vpc_id
  description = "Security group for API Gateway and Load Balancer"

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-api-sg"
    Type = "API"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# Security Group for Compute Resources (ECS, EC2)
resource "aws_security_group" "compute" {
  name_prefix = "${var.name_prefix}-compute-"
  vpc_id      = var.vpc_id
  description = "Security group for compute resources"

  # SSH access for debugging
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  # Application ports
  ingress {
    description     = "HTTP from API"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.api.id]
  }

  # Internal communication
  ingress {
    description = "Internal communication"
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    self        = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-compute-sg"
    Type = "Compute"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# Security Group for Database
resource "aws_security_group" "database" {
  name_prefix = "${var.name_prefix}-database-"
  vpc_id      = var.vpc_id
  description = "Security group for RDS database"

  ingress {
    description     = "PostgreSQL"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.compute.id]
  }

  # Allow Lambda functions to connect
  ingress {
    description     = "PostgreSQL from Lambda"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-database-sg"
    Type = "Database"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# Security Group for Lambda Functions
resource "aws_security_group" "lambda" {
  name_prefix = "${var.name_prefix}-lambda-"
  vpc_id      = var.vpc_id
  description = "Security group for Lambda functions"

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-lambda-sg"
    Type = "Lambda"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# IAM Role for ECS Tasks
resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.name_prefix}-ecs-task-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# IAM Role for ECS Tasks (Application)
resource "aws_iam_role" "ecs_task" {
  name = "${var.name_prefix}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "ecs_task_policy" {
  name = "${var.name_prefix}-ecs-task-policy"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = ["*"]  # Will be restricted to specific bucket in main module
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:SendMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = ["*"]  # Will be restricted to specific queues in main module
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = ["*"]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = ["*"]
      }
    ]
  })
}

# IAM Role for EC2 Instances (GPU training)
resource "aws_iam_role" "ec2_instance" {
  name = "${var.name_prefix}-ec2-instance"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_instance_profile" "ec2_instance" {
  name = "${var.name_prefix}-ec2-instance-profile"
  role = aws_iam_role.ec2_instance.name

  tags = var.tags
}

resource "aws_iam_role_policy" "ec2_instance_policy" {
  name = "${var.name_prefix}-ec2-instance-policy"
  role = aws_iam_role.ec2_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = ["*"]
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = ["*"]
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = ["*"]
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:SendMessage"
        ]
        Resource = ["*"]
      }
    ]
  })
}

# KMS Key for encryption
resource "aws_kms_key" "main" {
  description             = "KMS key for AI Influencer System"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-kms-key"
  })
}

resource "aws_kms_alias" "main" {
  name          = "alias/${var.name_prefix}-key"
  target_key_id = aws_kms_key.main.key_id
}

# Secrets Manager for API keys
resource "aws_secretsmanager_secret" "api_keys" {
  name                    = "${var.name_prefix}-api-keys"
  description             = "API keys for AI services"
  kms_key_id              = aws_kms_key.main.arn
  recovery_window_in_days = 7

  tags = var.tags
}

# Placeholder secret version (to be updated with actual API keys)
resource "aws_secretsmanager_secret_version" "api_keys" {
  secret_id = aws_secretsmanager_secret.api_keys.id
  secret_string = jsonencode({
    flux_api_key              = "PLACEHOLDER_FLUX_API_KEY"
    kling_api_key            = "PLACEHOLDER_KLING_API_KEY"
    lora_training_api_key    = "PLACEHOLDER_LORA_TRAINING_API_KEY"
    openai_api_key           = "PLACEHOLDER_OPENAI_API_KEY"
    claude_api_key           = "PLACEHOLDER_CLAUDE_API_KEY"
    instagram_access_token   = "PLACEHOLDER_INSTAGRAM_ACCESS_TOKEN"
    instagram_app_secret     = "PLACEHOLDER_INSTAGRAM_APP_SECRET"
    trend_api_key            = "PLACEHOLDER_TREND_API_KEY"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Database credentials
resource "aws_secretsmanager_secret" "database" {
  name                    = "${var.name_prefix}-database-credentials"
  description             = "Database credentials"
  kms_key_id              = aws_kms_key.main.arn
  recovery_window_in_days = 7

  tags = var.tags
}

# Outputs
output "api_security_group_id" {
  description = "ID of the API security group"
  value       = aws_security_group.api.id
}

output "compute_security_group_id" {
  description = "ID of the compute security group"
  value       = aws_security_group.compute.id
}

output "database_security_group_id" {
  description = "ID of the database security group"
  value       = aws_security_group.database.id
}

output "lambda_security_group_id" {
  description = "ID of the Lambda security group"
  value       = aws_security_group.lambda.id
}

output "ecs_task_execution_role_arn" {
  description = "ARN of the ECS task execution role"
  value       = aws_iam_role.ecs_task_execution.arn
}

output "ecs_task_role_arn" {
  description = "ARN of the ECS task role"
  value       = aws_iam_role.ecs_task.arn
}

output "ec2_instance_profile_name" {
  description = "Name of the EC2 instance profile"
  value       = aws_iam_instance_profile.ec2_instance.name
}

output "kms_key_id" {
  description = "ID of the KMS key"
  value       = aws_kms_key.main.key_id
}

output "kms_key_arn" {
  description = "ARN of the KMS key"
  value       = aws_kms_key.main.arn
}

output "api_keys_secret_arn" {
  description = "ARN of the API keys secret"
  value       = aws_secretsmanager_secret.api_keys.arn
}

output "database_secret_arn" {
  description = "ARN of the database credentials secret"
  value       = aws_secretsmanager_secret.database.arn
}
