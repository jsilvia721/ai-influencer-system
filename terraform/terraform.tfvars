# Terraform Variables for AI Influencer System

# AWS Configuration
aws_region             = "us-east-1"
project_name          = "ai-influencer-system"
environment           = "dev"
owner                 = "ai-team"

# EC2 Key Pair
key_pair_name = "ai-influencer-system-key"

# Notification Settings
notification_email = "admin@example.com"

# Security Settings
allowed_cidr_blocks = ["0.0.0.0/0"]

# Character Configuration
max_characters           = 3  # Starting with 3 for testing
daily_posts_per_character = 2

# Instance Configuration
spot_instance_max_price = "0.50"
