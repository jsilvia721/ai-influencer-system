# Database Module
# Creates RDS PostgreSQL instance with backup, monitoring, and security

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where database will be created"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for database subnet group"
  type        = list(string)
}

variable "security_group_ids" {
  description = "List of security group IDs for the database"
  type        = list(string)
}

variable "engine" {
  description = "Database engine"
  type        = string
  default     = "postgres"
}

variable "engine_version" {
  description = "Database engine version"
  type        = string
  default     = "15.8"
}

variable "instance_class" {
  description = "Database instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "allocated_storage" {
  description = "Initial storage allocation in GB"
  type        = number
  default     = 20
}

variable "max_allocated_storage" {
  description = "Maximum storage allocation in GB"
  type        = number
  default     = 100
}

variable "db_name" {
  description = "Name of the database"
  type        = string
  default     = "ai_influencer_db"
}

variable "username" {
  description = "Database master username"
  type        = string
  default     = "ai_admin"
}

variable "backup_retention_period" {
  description = "Number of days to retain backups"
  type        = number
  default     = 7
}

variable "backup_window" {
  description = "Preferred backup window"
  type        = string
  default     = "03:00-04:00"
}

variable "maintenance_window" {
  description = "Preferred maintenance window"
  type        = string
  default     = "sun:04:00-sun:05:00"
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# Generate random password for database
resource "random_password" "db_password" {
  length  = 32
  special = true
}

# Database subnet group
resource "aws_db_subnet_group" "main" {
  name       = "${var.name_prefix}-db-subnet-group"
  subnet_ids = var.subnet_ids
  
  tags = merge(var.tags, {
    Name = "${var.name_prefix}-db-subnet-group"
  })
}

# Parameter group for PostgreSQL optimization
resource "aws_db_parameter_group" "main" {
  family = "postgres15"
  name   = "${var.name_prefix}-db-params"
  
  # Optimize for AI workloads
  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
  }
  
  parameter {
    name  = "log_statement"
    value = "all"
  }
  
  parameter {
    name  = "log_min_duration_statement"
    value = "1000"  # Log queries taking more than 1 second
  }
  
  parameter {
    name  = "work_mem"
    value = "16384"  # 16MB
  }
  
  parameter {
    name  = "maintenance_work_mem"
    value = "65536"  # 64MB
  }
  
  tags = var.tags
}

# Database option group
resource "aws_db_option_group" "main" {
  name                     = "${var.name_prefix}-db-options"
  option_group_description = "Option group for AI Influencer System database"
  engine_name              = var.engine
  major_engine_version     = "15"
  
  tags = var.tags
}

# RDS instance
resource "aws_db_instance" "main" {
  identifier = "${var.name_prefix}-database"
  
  # Engine configuration
  engine         = var.engine
  engine_version = var.engine_version
  instance_class = var.instance_class
  
  # Storage configuration
  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  
  # Database configuration
  db_name  = var.db_name
  username = var.username
  password = random_password.db_password.result
  
  # Network configuration
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = var.security_group_ids
  publicly_accessible    = false
  
  # Backup configuration
  backup_retention_period = var.backup_retention_period
  backup_window          = var.backup_window
  copy_tags_to_snapshot  = true
  delete_automated_backups = false
  
  # Maintenance configuration
  maintenance_window      = var.maintenance_window
  auto_minor_version_upgrade = true
  
  # Performance configuration
  parameter_group_name = aws_db_parameter_group.main.name
  option_group_name    = aws_db_option_group.main.name
  
  # Monitoring configuration
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_enhanced_monitoring.arn
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  
  # Performance Insights
  performance_insights_enabled = true
  performance_insights_retention_period = 7
  
  # Security
  deletion_protection = false # Set to true in production
  skip_final_snapshot = true  # Set to false in production
  final_snapshot_identifier = "${var.name_prefix}-final-snapshot"
  
  tags = merge(var.tags, {
    Name = "${var.name_prefix}-database"
  })
  
  lifecycle {
    prevent_destroy = false # Set to true in production
  }
}

# Store database credentials in Secrets Manager
resource "aws_secretsmanager_secret" "db_credentials" {
  name                    = "${var.name_prefix}-db-credentials"
  description             = "Database credentials for AI Influencer System"
  recovery_window_in_days = 7
  
  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    engine   = var.engine
    host     = aws_db_instance.main.endpoint
    port     = aws_db_instance.main.port
    dbname   = aws_db_instance.main.db_name
    username = aws_db_instance.main.username
    password = random_password.db_password.result
  })
}

# IAM role for enhanced monitoring
resource "aws_iam_role" "rds_enhanced_monitoring" {
  name = "${var.name_prefix}-rds-enhanced-monitoring"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })
  
  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "rds_enhanced_monitoring" {
  role       = aws_iam_role.rds_enhanced_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# CloudWatch alarms for database monitoring
resource "aws_cloudwatch_metric_alarm" "database_cpu" {
  alarm_name          = "${var.name_prefix}-database-cpu-utilization"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors database CPU utilization"
  alarm_actions       = [] # Add SNS topic ARN for notifications
  
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }
  
  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "database_connections" {
  alarm_name          = "${var.name_prefix}-database-connections"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors database connections"
  alarm_actions       = [] # Add SNS topic ARN for notifications
  
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }
  
  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "database_free_storage" {
  alarm_name          = "${var.name_prefix}-database-free-storage"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "2000000000"  # 2GB in bytes
  alarm_description   = "This metric monitors database free storage space"
  alarm_actions       = [] # Add SNS topic ARN for notifications
  
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }
  
  tags = var.tags
}

# Read replica for scaling (optional)
resource "aws_db_instance" "read_replica" {
  count = 0  # Set to 1 to enable read replica
  
  identifier             = "${var.name_prefix}-database-read-replica"
  replicate_source_db    = aws_db_instance.main.identifier
  instance_class         = var.instance_class
  publicly_accessible    = false
  auto_minor_version_upgrade = true
  
  # Monitoring
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_enhanced_monitoring.arn
  
  tags = merge(var.tags, {
    Name = "${var.name_prefix}-database-read-replica"
    Type = "ReadReplica"
  })
}

# Outputs
output "rds_instance_id" {
  description = "ID of the RDS instance"
  value       = aws_db_instance.main.id
}

output "rds_instance_arn" {
  description = "ARN of the RDS instance"
  value       = aws_db_instance.main.arn
}

output "rds_endpoint" {
  description = "RDS instance endpoint"
  value       = aws_db_instance.main.endpoint
}

output "rds_port" {
  description = "RDS instance port"
  value       = aws_db_instance.main.port
}

output "database_name" {
  description = "Name of the database"
  value       = aws_db_instance.main.db_name
}

output "database_username" {
  description = "Database master username"
  value       = aws_db_instance.main.username
  sensitive   = true
}

output "connection_string" {
  description = "Database connection string"
  value       = "postgresql://${aws_db_instance.main.username}:${random_password.db_password.result}@${aws_db_instance.main.endpoint}:${aws_db_instance.main.port}/${aws_db_instance.main.db_name}"
  sensitive   = true
}

output "credentials_secret_arn" {
  description = "ARN of the database credentials secret"
  value       = aws_secretsmanager_secret.db_credentials.arn
}
