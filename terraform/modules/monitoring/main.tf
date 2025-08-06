# Monitoring Module
# Integrates CloudWatch, SNS, and cost tracking

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID for resources monitored by CloudWatch"
  type        = string
}

variable "rds_instance_id" {
  description = "RDS instance ID for monitoring"
  type        = string
}

variable "s3_bucket_name" {
  description = "Name of the primary S3 bucket for content storage"
  type        = string
}

variable "ecs_cluster_name" {
  description = "ECS cluster name for monitoring"
  type        = string
}

variable "notification_email" {
  description = "Email address for notifications and alerts"
  type        = string
}

variable "cost_alert_threshold" {
  description = "Cost threshold in USD for alerts"
  type        = number
  default     = 100
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# SNS Topic for alerts
resource "aws_sns_topic" "alerts" {
  name = "${var.name_prefix}-alerts"
  
  tags = var.tags
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.notification_email
}

# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.name_prefix}-dashboard"
  
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "text"
        x    = 0
        y    = 0
        width = 24
        height = 1
        properties = {
          markdown = "# AI Influencer System Metrics"
        }
      },
      {
        type       = "metric"
        x          = 0
        y          = 1
        width      = 12
        height     = 6
        properties = {
          metrics = [
            [ "AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", var.rds_instance_id ]
          ]
          period    = 300
          stat      = "Average"
          region    = "${data.aws_region.current.name}"
          title     = "RDS CPU Utilization"
        }
      },
      {
        type       = "metric"
        x          = 12
        y          = 1
        width      = 12
        height     = 6
        properties = {
          metrics = [
            [ "AWS/ECS", "CPUUtilization", "ClusterName", var.ecs_cluster_name ]
          ]
          period    = 300
          stat      = "Average"
          region    = "${data.aws_region.current.name}"
          title     = "ECS CPU Utilization"
        }
      }
    ]
  })
}

# CloudWatch Metric Alarm for Cost
resource "aws_cloudwatch_metric_alarm" "cost" {
  alarm_name          = "${var.name_prefix}-cost"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = "21600"  # 6 hours
  statistic           = "Maximum"
  threshold           = var.cost_alert_threshold
  alarm_description   = "This metric monitors the estimated charges for AWS usage"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  
  dimensions = {
    Currency = "USD"
  }
}

# Data sources
data "aws_region" "current" {}

data "aws_caller_identity" "current" {}

# Outputs
output "dashboard_url" {
  description = "URL of the CloudWatch dashboard"
  value       = "https://console.aws.amazon.com/cloudwatch/home?region=${data.aws_region.current.name}#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}"
}

output "sns_topic_arn" {
  description = "ARN of the SNS topic for alerts"
  value       = aws_sns_topic.alerts.arn
}
