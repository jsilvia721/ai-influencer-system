# Storage Module
# Creates S3 buckets, CloudFront distribution, and lifecycle policies

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "resource_suffix" {
  description = "Random suffix for unique naming"
  type        = string
}

variable "enable_versioning" {
  description = "Enable S3 bucket versioning"
  type        = bool
  default     = true
}

variable "lifecycle_rules" {
  description = "S3 lifecycle rules"
  type        = list(object({
    id     = string
    status = string
    expiration = optional(object({
      days = number
    }))
    noncurrent_version_expiration = optional(object({
      days = number
    }))
    transition = optional(object({
      days          = number
      storage_class = string
    }))
  }))
  default = []
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# Primary S3 Bucket for content storage
resource "aws_s3_bucket" "primary" {
  bucket = "${var.name_prefix}-content-${var.resource_suffix}"
  
  tags = merge(var.tags, {
    Name = "${var.name_prefix}-primary-bucket"
    Type = "ContentStorage"
  })
}

resource "aws_s3_bucket_versioning" "primary" {
  bucket = aws_s3_bucket.primary.id
  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Disabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "primary" {
  bucket = aws_s3_bucket.primary.id
  
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "primary" {
  bucket = aws_s3_bucket.primary.id
  
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle configuration
resource "aws_s3_bucket_lifecycle_configuration" "primary" {
  count = length(var.lifecycle_rules) > 0 ? 1 : 0
  
  bucket = aws_s3_bucket.primary.id
  
  dynamic "rule" {
    for_each = var.lifecycle_rules
    content {
      id     = rule.value.id
      status = rule.value.status
      
      dynamic "expiration" {
        for_each = rule.value.expiration != null ? [rule.value.expiration] : []
        content {
          days = expiration.value.days
        }
      }
      
      dynamic "noncurrent_version_expiration" {
        for_each = rule.value.noncurrent_version_expiration != null ? [rule.value.noncurrent_version_expiration] : []
        content {
          noncurrent_days = noncurrent_version_expiration.value.days
        }
      }
      
      dynamic "transition" {
        for_each = rule.value.transition != null ? [rule.value.transition] : []
        content {
          days          = transition.value.days
          storage_class = transition.value.storage_class
        }
      }
    }
  }
}

# Models S3 Bucket for LoRA models and training data
resource "aws_s3_bucket" "models" {
  bucket = "${var.name_prefix}-models-${var.resource_suffix}"
  
  tags = merge(var.tags, {
    Name = "${var.name_prefix}-models-bucket"
    Type = "ModelStorage"
  })
}

resource "aws_s3_bucket_versioning" "models" {
  bucket = aws_s3_bucket.models.id
  versioning_configuration {
    status = "Enabled"  # Always enable versioning for models
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "models" {
  bucket = aws_s3_bucket.models.id
  
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "models" {
  bucket = aws_s3_bucket.models.id
  
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Logs S3 Bucket
resource "aws_s3_bucket" "logs" {
  bucket = "${var.name_prefix}-logs-${var.resource_suffix}"
  
  tags = merge(var.tags, {
    Name = "${var.name_prefix}-logs-bucket"
    Type = "LogStorage"
  })
}

resource "aws_s3_bucket_server_side_encryption_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id
  
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# S3 bucket ACL for logs
resource "aws_s3_bucket_ownership_controls" "logs" {
  bucket = aws_s3_bucket.logs.id

  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_acl" "logs" {
  depends_on = [aws_s3_bucket_ownership_controls.logs]
  bucket     = aws_s3_bucket.logs.id
  acl        = "log-delivery-write"
}

resource "aws_s3_bucket_public_access_block" "logs" {
  depends_on = [aws_s3_bucket_acl.logs]
  bucket = aws_s3_bucket.logs.id
  
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# Lifecycle policy for logs bucket
resource "aws_s3_bucket_lifecycle_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id
  
  rule {
    id     = "log_retention"
    status = "Enabled"
    
    filter {
      prefix = ""
    }
    
    expiration {
      days = 90  # Delete logs after 90 days
    }
    
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
  }
}

# CloudFront Origin Access Control
resource "aws_cloudfront_origin_access_control" "primary" {
  name                              = "${var.name_prefix}-oac"
  description                       = "OAC for primary S3 bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# CloudFront Distribution
resource "aws_cloudfront_distribution" "primary" {
  origin {
    domain_name              = aws_s3_bucket.primary.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.primary.id
    origin_id                = "S3-${aws_s3_bucket.primary.bucket}"
  }
  
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "CDN for AI Influencer System content"
  default_root_object = "index.html"
  
  # Logging configuration
  logging_config {
    include_cookies = false
    bucket         = aws_s3_bucket.logs.bucket_domain_name
    prefix         = "cloudfront-logs/"
  }
  
  default_cache_behavior {
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-${aws_s3_bucket.primary.bucket}"
    compress               = true
    viewer_protocol_policy = "redirect-to-https"
    
    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
    
    min_ttl     = 0
    default_ttl = 3600    # 1 hour
    max_ttl     = 86400   # 24 hours
  }
  
  # Cache behavior for images
  ordered_cache_behavior {
    path_pattern           = "images/*"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-${aws_s3_bucket.primary.bucket}"
    compress               = true
    viewer_protocol_policy = "redirect-to-https"
    
    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
    
    min_ttl     = 0
    default_ttl = 86400   # 24 hours
    max_ttl     = 31536000 # 1 year
  }
  
  # Cache behavior for videos
  ordered_cache_behavior {
    path_pattern           = "videos/*"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-${aws_s3_bucket.primary.bucket}"
    compress               = false  # Don't compress video files
    viewer_protocol_policy = "redirect-to-https"
    
    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
    
    min_ttl     = 0
    default_ttl = 86400   # 24 hours
    max_ttl     = 31536000 # 1 year
  }
  
  price_class = "PriceClass_100"  # Use only North America and Europe for cost optimization
  
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
  
  viewer_certificate {
    cloudfront_default_certificate = true
  }
  
  tags = merge(var.tags, {
    Name = "${var.name_prefix}-cloudfront"
  })
}

# S3 bucket policy for CloudFront access
resource "aws_s3_bucket_policy" "primary" {
  bucket = aws_s3_bucket.primary.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontServicePrincipal"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.primary.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.primary.arn
          }
        }
      }
    ]
  })
}

# S3 bucket notification for processing pipeline
resource "aws_s3_bucket_notification" "primary" {
  bucket = aws_s3_bucket.primary.id
  
  # This would be configured to trigger Lambda functions
  # when new content is uploaded
  
  depends_on = [aws_s3_bucket_policy.primary]
}

# Cost optimization - Intelligent Tiering
resource "aws_s3_bucket_intelligent_tiering_configuration" "primary" {
  bucket = aws_s3_bucket.primary.id
  name   = "IntelligentTiering"
  
  status = "Enabled"
  
  tiering {
    access_tier = "DEEP_ARCHIVE_ACCESS"
    days        = 180
  }
  
  tiering {
    access_tier = "ARCHIVE_ACCESS"
    days        = 90
  }
}

# Outputs
output "primary_bucket_name" {
  description = "Name of the primary S3 bucket"
  value       = aws_s3_bucket.primary.bucket
}

output "primary_bucket_arn" {
  description = "ARN of the primary S3 bucket"
  value       = aws_s3_bucket.primary.arn
}

output "primary_bucket_domain_name" {
  description = "Domain name of the primary S3 bucket"
  value       = aws_s3_bucket.primary.bucket_domain_name
}

output "models_bucket_name" {
  description = "Name of the models S3 bucket"
  value       = aws_s3_bucket.models.bucket
}

output "models_bucket_arn" {
  description = "ARN of the models S3 bucket"
  value       = aws_s3_bucket.models.arn
}

output "logs_bucket_name" {
  description = "Name of the logs S3 bucket"
  value       = aws_s3_bucket.logs.bucket
}

output "cloudfront_distribution_id" {
  description = "ID of the CloudFront distribution"
  value       = aws_cloudfront_distribution.primary.id
}

output "cloudfront_distribution_arn" {
  description = "ARN of the CloudFront distribution"
  value       = aws_cloudfront_distribution.primary.arn
}

output "cloudfront_domain_name" {
  description = "Domain name of the CloudFront distribution"
  value       = aws_cloudfront_distribution.primary.domain_name
}

output "cloudfront_hosted_zone_id" {
  description = "Hosted zone ID of the CloudFront distribution"
  value       = aws_cloudfront_distribution.primary.hosted_zone_id
}
