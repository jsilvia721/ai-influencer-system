# Compute Module
# Creates ECS cluster, auto-scaling groups, and GPU training instances

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where compute resources will be created"
  type        = string
}

variable "public_subnet_ids" {
  description = "List of public subnet IDs"
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs"
  type        = list(string)
}

variable "security_group_ids" {
  description = "List of security group IDs for compute resources"
  type        = list(string)
}

variable "key_pair_name" {
  description = "EC2 Key Pair name for SSH access"
  type        = string
}

variable "s3_bucket_name" {
  description = "S3 bucket name for content storage"
  type        = string
}

variable "max_characters" {
  description = "Maximum number of AI characters to support"
  type        = number
  default     = 5
}

variable "daily_posts_per_character" {
  description = "Number of posts per character per day"
  type        = number
  default     = 2
}

variable "gpu_instance_type" {
  description = "Instance type for GPU training"
  type        = string
  default     = "g4dn.xlarge"
}

variable "spot_max_price" {
  description = "Maximum spot price for GPU instances"
  type        = string
  default     = "0.50"
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# Data sources
data "aws_ami" "ecs_optimized" {
  most_recent = true
  owners      = ["amazon"]
  
  filter {
    name   = "name"
    values = ["amzn2-ami-ecs-hvm-*-x86_64-ebs"]
  }
  
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_ami" "deep_learning" {
  most_recent = true
  owners      = ["amazon"]
  
  filter {
    name   = "name"
    values = ["Deep Learning AMI GPU PyTorch * (Ubuntu 20.04) *"]
  }
  
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.name_prefix}-cluster"
  
  configuration {
    execute_command_configuration {
      logging = "OVERRIDE"
      
      log_configuration {
        cloud_watch_encryption_enabled = true
        cloud_watch_log_group_name     = aws_cloudwatch_log_group.ecs_cluster.name
      }
    }
  }
  
  tags = merge(var.tags, {
    Name = "${var.name_prefix}-ecs-cluster"
  })
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name = aws_ecs_cluster.main.name
  
  capacity_providers = [
    "FARGATE",
    "FARGATE_SPOT",
    aws_ecs_capacity_provider.main.name
  ]
  
  default_capacity_provider_strategy {
    base              = 1
    weight            = 100
    capacity_provider = "FARGATE_SPOT"
  }
}

# CloudWatch Log Group for ECS
resource "aws_cloudwatch_log_group" "ecs_cluster" {
  name              = "/aws/ecs/${var.name_prefix}-cluster"
  retention_in_days = 14
  
  tags = var.tags
}

# ECS Task Definitions for different processing types
resource "aws_ecs_task_definition" "image_generation" {
  family                   = "${var.name_prefix}-image-generation"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = var.ecs_task_execution_role_arn
  task_role_arn           = var.ecs_task_role_arn
  
  container_definitions = jsonencode([
    {
      name  = "image-generator"
      image = "${aws_ecr_repository.image_generation.repository_url}:latest"
      
      essential = true
      
      environment = [
        {
          name  = "S3_BUCKET"
          value = var.s3_bucket_name
        },
        {
          name  = "PROCESSING_TYPE"
          value = "image_generation"
        }
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/aws/ecs/${var.name_prefix}-image-generation"
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "ecs"
        }
      }
      
      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]
    }
  ])
  
  tags = var.tags
}

resource "aws_ecs_task_definition" "video_generation" {
  family                   = "${var.name_prefix}-video-generation"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 2048
  memory                   = 4096
  execution_role_arn       = var.ecs_task_execution_role_arn
  task_role_arn           = var.ecs_task_role_arn
  
  container_definitions = jsonencode([
    {
      name  = "video-generator"
      image = "${aws_ecr_repository.video_generation.repository_url}:latest"
      
      essential = true
      
      environment = [
        {
          name  = "S3_BUCKET"
          value = var.s3_bucket_name
        },
        {
          name  = "PROCESSING_TYPE"
          value = "video_generation"
        }
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/aws/ecs/${var.name_prefix}-video-generation"
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "ecs"
        }
      }
      
      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]
    }
  ])
  
  tags = var.tags
}

resource "aws_ecs_task_definition" "content_posting" {
  family                   = "${var.name_prefix}-content-posting"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = var.ecs_task_execution_role_arn
  task_role_arn           = var.ecs_task_role_arn
  
  container_definitions = jsonencode([
    {
      name  = "content-poster"
      image = "${aws_ecr_repository.content_posting.repository_url}:latest"
      
      essential = true
      
      environment = [
        {
          name  = "S3_BUCKET"
          value = var.s3_bucket_name
        },
        {
          name  = "PROCESSING_TYPE"
          value = "content_posting"
        }
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/aws/ecs/${var.name_prefix}-content-posting"
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "ecs"
        }
      }
      
      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]
    }
  ])
  
  tags = var.tags
}

# ECR Repositories
resource "aws_ecr_repository" "image_generation" {
  name                 = "${var.name_prefix}/image-generation"
  image_tag_mutability = "MUTABLE"
  
  image_scanning_configuration {
    scan_on_push = true
  }
  
  tags = var.tags
}

resource "aws_ecr_repository" "video_generation" {
  name                 = "${var.name_prefix}/video-generation"
  image_tag_mutability = "MUTABLE"
  
  image_scanning_configuration {
    scan_on_push = true
  }
  
  tags = var.tags
}

resource "aws_ecr_repository" "content_posting" {
  name                 = "${var.name_prefix}/content-posting"
  image_tag_mutability = "MUTABLE"
  
  image_scanning_configuration {
    scan_on_push = true
  }
  
  tags = var.tags
}

# ECS Services for each processing type
resource "aws_ecs_service" "image_generation" {
  count = var.max_characters
  
  name            = "${var.name_prefix}-image-gen-char-${count.index + 1}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.image_generation.arn
  desired_count   = 0  # Start with 0, scale based on queue depth
  
  capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight           = 100
  }
  
  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = var.security_group_ids
    assign_public_ip = false
  }
  
  service_registries {
    registry_arn = aws_service_discovery_service.image_generation[count.index].arn
  }
  
  tags = merge(var.tags, {
    Character = "character-${count.index + 1}"
    Service   = "ImageGeneration"
  })
}

resource "aws_ecs_service" "video_generation" {
  count = var.max_characters
  
  name            = "${var.name_prefix}-video-gen-char-${count.index + 1}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.video_generation.arn
  desired_count   = 0  # Start with 0, scale based on queue depth
  
  capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight           = 100
  }
  
  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = var.security_group_ids
    assign_public_ip = false
  }
  
  service_registries {
    registry_arn = aws_service_discovery_service.video_generation[count.index].arn
  }
  
  tags = merge(var.tags, {
    Character = "character-${count.index + 1}"
    Service   = "VideoGeneration"
  })
}

resource "aws_ecs_service" "content_posting" {
  count = var.max_characters
  
  name            = "${var.name_prefix}-posting-char-${count.index + 1}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.content_posting.arn
  desired_count   = 0  # Start with 0, scale based on queue depth
  
  capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight           = 100
  }
  
  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = var.security_group_ids
    assign_public_ip = false
  }
  
  service_registries {
    registry_arn = aws_service_discovery_service.content_posting[count.index].arn
  }
  
  tags = merge(var.tags, {
    Character = "character-${count.index + 1}"
    Service   = "ContentPosting"
  })
}

# Service Discovery
resource "aws_service_discovery_private_dns_namespace" "main" {
  name        = "${var.name_prefix}.local"
  description = "Service discovery namespace for AI Influencer System"
  vpc         = var.vpc_id
  
  tags = var.tags
}

resource "aws_service_discovery_service" "image_generation" {
  count = var.max_characters
  
  name = "image-gen-char-${count.index + 1}"
  
  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id
    
    dns_records {
      ttl  = 10
      type = "A"
    }
  }
  
  tags = merge(var.tags, {
    Character = "character-${count.index + 1}"
    Service   = "ImageGeneration"
  })
}

resource "aws_service_discovery_service" "video_generation" {
  count = var.max_characters
  
  name = "video-gen-char-${count.index + 1}"
  
  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id
    
    dns_records {
      ttl  = 10
      type = "A"
    }
  }
  
  tags = merge(var.tags, {
    Character = "character-${count.index + 1}"
    Service   = "VideoGeneration"
  })
}

resource "aws_service_discovery_service" "content_posting" {
  count = var.max_characters
  
  name = "posting-char-${count.index + 1}"
  
  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id
    
    dns_records {
      ttl  = 10
      type = "A"
    }
  }
  
  tags = merge(var.tags, {
    Character = "character-${count.index + 1}"
    Service   = "ContentPosting"
  })
}

# Application Load Balancer for API access
resource "aws_lb" "main" {
  name               = "${var.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = var.security_group_ids
  subnets            = var.public_subnet_ids
  
  enable_deletion_protection = false  # Set to true in production
  
  tags = var.tags
}

resource "aws_lb_target_group" "api" {
  name     = "${var.name_prefix}-api-tg"
  port     = 8000
  protocol = "HTTP"
  vpc_id   = var.vpc_id
  
  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 5
    interval            = 30
    path                = "/health"
    matcher             = "200"
  }
  
  tags = var.tags
}

resource "aws_lb_listener" "api" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"
  
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
  
  tags = var.tags
}

# Auto Scaling for ECS Services
resource "aws_appautoscaling_target" "image_generation" {
  count = var.max_characters
  
  max_capacity       = 10
  min_capacity       = 0
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.image_generation[count.index].name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "image_generation_scale_up" {
  count = var.max_characters
  
  name               = "${var.name_prefix}-image-gen-scale-up-${count.index + 1}"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.image_generation[count.index].resource_id
  scalable_dimension = aws_appautoscaling_target.image_generation[count.index].scalable_dimension
  service_namespace  = aws_appautoscaling_target.image_generation[count.index].service_namespace
  
  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = 70.0
  }
}

# GPU Training Infrastructure
resource "aws_launch_template" "gpu_training" {
  name_prefix   = "${var.name_prefix}-gpu-training-"
  image_id      = data.aws_ami.deep_learning.id
  instance_type = var.gpu_instance_type
  key_name      = var.key_pair_name
  
  vpc_security_group_ids = var.security_group_ids
  
  iam_instance_profile {
    name = var.ec2_instance_profile_name
  }
  
  block_device_mappings {
    device_name = "/dev/sda1"
    ebs {
      volume_size           = 100
      volume_type          = "gp3"
      delete_on_termination = true
      encrypted            = true
    }
  }
  
  user_data = base64encode(templatefile("${path.module}/user_data.sh", {
    s3_bucket = var.s3_bucket_name
    name_prefix = var.name_prefix
  }))
  
  tag_specifications {
    resource_type = "instance"
    tags = merge(var.tags, {
      Name = "${var.name_prefix}-gpu-training-instance"
      Type = "GPUTraining"
    })
  }
  
  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_autoscaling_group" "gpu_training" {
  name                = "${var.name_prefix}-gpu-training-asg"
  vpc_zone_identifier = var.private_subnet_ids
  min_size            = 0
  max_size            = 2
  desired_capacity    = 0  # Start with 0, scale up when needed
  
  mixed_instances_policy {
    launch_template {
      launch_template_specification {
        launch_template_id = aws_launch_template.gpu_training.id
        version           = "$Latest"
      }
    }
    
    instances_distribution {
      on_demand_percentage_above_base_capacity = 0
      spot_allocation_strategy                 = "lowest-price"
      spot_instance_pools                     = 2
      spot_max_price                          = var.spot_max_price
    }
  }
  
  tag {
    key                 = "Name"
    value               = "${var.name_prefix}-gpu-training-asg"
    propagate_at_launch = false
  }
  
  dynamic "tag" {
    for_each = var.tags
    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }
}

# Get current AWS region
data "aws_region" "current" {}

# Missing variables that need to be passed from security module
variable "ecs_task_execution_role_arn" {
  description = "ARN of the ECS task execution role"
  type        = string
}

variable "ecs_task_role_arn" {
  description = "ARN of the ECS task role"
  type        = string
}

variable "ec2_instance_profile_name" {
  description = "Name of the EC2 instance profile"
  type        = string
}

# ECS Capacity Provider
resource "aws_ecs_capacity_provider" "main" {
  name = "${var.name_prefix}-capacity-provider"
  
  auto_scaling_group_provider {
    auto_scaling_group_arn         = aws_autoscaling_group.gpu_training.arn
    managed_termination_protection = "DISABLED"
    
    managed_scaling {
      maximum_scaling_step_size = 2
      minimum_scaling_step_size = 1
      status                    = "ENABLED"
      target_capacity          = 100
    }
  }
  
  tags = var.tags
}

# CloudWatch Log Groups for ECS tasks
resource "aws_cloudwatch_log_group" "image_generation" {
  name              = "/aws/ecs/${var.name_prefix}-image-generation"
  retention_in_days = 14
  
  tags = var.tags
}

resource "aws_cloudwatch_log_group" "video_generation" {
  name              = "/aws/ecs/${var.name_prefix}-video-generation"
  retention_in_days = 14
  
  tags = var.tags
}

resource "aws_cloudwatch_log_group" "content_posting" {
  name              = "/aws/ecs/${var.name_prefix}-content-posting"
  retention_in_days = 14
  
  tags = var.tags
}

# Outputs
output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "ecs_cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = aws_ecs_cluster.main.arn
}

output "load_balancer_dns_name" {
  description = "DNS name of the load balancer"
  value       = aws_lb.main.dns_name
}

output "load_balancer_zone_id" {
  description = "Zone ID of the load balancer"
  value       = aws_lb.main.zone_id
}

output "ecr_repositories" {
  description = "ECR repository URLs"
  value = {
    image_generation = aws_ecr_repository.image_generation.repository_url
    video_generation = aws_ecr_repository.video_generation.repository_url
    content_posting  = aws_ecr_repository.content_posting.repository_url
  }
}

output "service_discovery_namespace" {
  description = "Service discovery namespace"
  value = {
    id   = aws_service_discovery_private_dns_namespace.main.id
    name = aws_service_discovery_private_dns_namespace.main.name
  }
}
