#!/bin/bash

# AWS Training Infrastructure Deployment Script
# This script helps manage your AI training infrastructure

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if terraform is installed
    if ! command -v terraform &> /dev/null; then
        log_error "Terraform is not installed. Please install it first."
        exit 1
    fi
    
    # Check if AWS CLI is installed
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Run 'aws configure' first."
        exit 1
    fi
    
    # Check if terraform.tfvars exists
    if [ ! -f "terraform.tfvars" ]; then
        log_warn "terraform.tfvars not found. Creating from example..."
        cp terraform.tfvars.example terraform.tfvars
        log_error "Please edit terraform.tfvars with your settings before proceeding."
        exit 1
    fi
    
    log_info "Prerequisites check passed!"
}

estimate_cost() {
    log_info "Estimating training costs..."
    
    # Get spot price from terraform.tfvars
    MAX_PRICE=$(grep 'max_spot_price' terraform.tfvars | cut -d'"' -f2)
    HOURS=$(grep 'training_duration_hours' terraform.tfvars | cut -d'=' -f2 | tr -d ' ')
    
    COMPUTE_COST=$(echo "$MAX_PRICE * $HOURS" | bc -l)
    STORAGE_COST=$(echo "0.08 * $HOURS" | bc -l)  # Approximate EBS cost
    TOTAL_COST=$(echo "$COMPUTE_COST + $STORAGE_COST + 0.50" | bc -l)  # +0.50 for misc costs
    
    echo "==================== COST ESTIMATE ===================="
    echo "Max Spot Price:     \$$MAX_PRICE/hour"
    echo "Training Duration:  $HOURS hours"
    echo "Compute Cost:       \$$COMPUTE_COST"
    echo "Storage Cost:       \$$STORAGE_COST"
    echo "Misc (S3, etc):     \$0.50"
    echo "TOTAL ESTIMATE:     \$$TOTAL_COST"
    echo "======================================================="
    echo "Note: Actual spot prices may be lower, reducing costs!"
}

deploy_infrastructure() {
    log_info "Deploying AWS infrastructure..."
    
    # Initialize Terraform
    terraform init
    
    # Plan the deployment
    terraform plan -out=tfplan
    
    # Show cost estimate
    estimate_cost
    
    # Ask for confirmation
    echo ""
    read -p "Do you want to proceed with deployment? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Deployment cancelled."
        exit 0
    fi
    
    # Apply the deployment
    terraform apply tfplan
    
    # Get outputs
    S3_BUCKET=$(terraform output -raw s3_bucket_name)
    
    log_info "Infrastructure deployed successfully!"
    log_info "S3 Bucket: $S3_BUCKET"
}

upload_training_data() {
    log_info "Uploading training data to S3..."
    
    S3_BUCKET=$(terraform output -raw s3_bucket_name 2>/dev/null || echo "")
    
    if [ -z "$S3_BUCKET" ]; then
        log_error "Infrastructure not deployed. Run './deploy.sh deploy' first."
        exit 1
    fi
    
    # Check if training data exists
    if [ ! -d "../training_data" ]; then
        log_error "Training data directory not found at ../training_data"
        exit 1
    fi
    
    # Upload training data
    aws s3 sync ../training_data/ "s3://$S3_BUCKET/training_data/" --delete
    
    # Upload training config
    if [ -f "../training_data/training_config.toml" ]; then
        aws s3 cp ../training_data/training_config.toml "s3://$S3_BUCKET/config/"
    fi
    
    log_info "Training data uploaded successfully!"
}

start_training() {
    log_info "Starting training instance..."
    
    # Scale up the auto scaling group to launch an instance
    ASG_NAME=$(aws autoscaling describe-auto-scaling-groups \
        --query "AutoScalingGroups[?contains(AutoScalingGroupName, 'ai-influencer-training')].AutoScalingGroupName" \
        --output text)
    
    if [ -z "$ASG_NAME" ]; then
        log_error "Auto Scaling Group not found. Make sure infrastructure is deployed."
        exit 1
    fi
    
    log_info "Scaling up Auto Scaling Group: $ASG_NAME"
    aws autoscaling update-auto-scaling-group \
        --auto-scaling-group-name "$ASG_NAME" \
        --desired-capacity 1
    
    log_info "Training instance is starting..."
    log_info "It will take 5-10 minutes to initialize and start training."
    log_info "Monitor progress with: ./deploy.sh monitor"
}

stop_training() {
    log_info "Stopping training instance..."
    
    ASG_NAME=$(aws autoscaling describe-auto-scaling-groups \
        --query "AutoScalingGroups[?contains(AutoScalingGroupName, 'ai-influencer-training')].AutoScalingGroupName" \
        --output text)
    
    if [ -z "$ASG_NAME" ]; then
        log_error "Auto Scaling Group not found."
        exit 1
    fi
    
    aws autoscaling update-auto-scaling-group \
        --auto-scaling-group-name "$ASG_NAME" \
        --desired-capacity 0
    
    log_info "Training instance is stopping..."
}

monitor_training() {
    log_info "Monitoring training progress..."
    
    S3_BUCKET=$(terraform output -raw s3_bucket_name 2>/dev/null || echo "")
    
    if [ -z "$S3_BUCKET" ]; then
        log_error "Infrastructure not deployed."
        exit 1
    fi
    
    # Check for instances
    INSTANCE_ID=$(aws ec2 describe-instances \
        --filters "Name=tag:Name,Values=ai-influencer-training-training-instance" \
               "Name=instance-state-name,Values=running" \
        --query "Reservations[0].Instances[0].InstanceId" \
        --output text)
    
    if [ "$INSTANCE_ID" = "None" ] || [ -z "$INSTANCE_ID" ]; then
        log_warn "No running training instances found."
        log_info "Start training with: ./deploy.sh start"
        exit 0
    fi
    
    # Get instance public IP
    INSTANCE_IP=$(aws ec2 describe-instances \
        --instance-ids "$INSTANCE_ID" \
        --query "Reservations[0].Instances[0].PublicIpAddress" \
        --output text)
    
    echo "==================== TRAINING STATUS ===================="
    echo "Instance ID:      $INSTANCE_ID"
    echo "Instance IP:      $INSTANCE_IP"
    echo "TensorBoard:      http://$INSTANCE_IP:6006"
    echo "Jupyter:          http://$INSTANCE_IP:8888 (token: training-token)"
    echo "S3 Bucket:        $S3_BUCKET"
    echo "======================================================="
    
    # Check S3 for latest logs
    log_info "Checking for training logs in S3..."
    aws s3 ls "s3://$S3_BUCKET/logs/" --recursive --human-readable | tail -5
}

download_results() {
    log_info "Downloading training results..."
    
    S3_BUCKET=$(terraform output -raw s3_bucket_name 2>/dev/null || echo "")
    
    if [ -z "$S3_BUCKET" ]; then
        log_error "Infrastructure not deployed."
        exit 1
    fi
    
    # Create results directory
    mkdir -p ../results
    
    # Download outputs
    aws s3 sync "s3://$S3_BUCKET/output/" ../results/
    
    log_info "Results downloaded to ../results/"
    
    # List the downloaded files
    echo "Downloaded files:"
    ls -la ../results/
}

destroy_infrastructure() {
    log_warn "This will destroy ALL infrastructure and cannot be undone!"
    echo ""
    read -p "Are you sure you want to destroy the infrastructure? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Destruction cancelled."
        exit 0
    fi
    
    log_info "Destroying infrastructure..."
    terraform destroy -auto-approve
    log_info "Infrastructure destroyed."
}

show_help() {
    echo "AWS AI Training Infrastructure Management"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  deploy        Deploy the AWS infrastructure"
    echo "  upload        Upload training data to S3"
    echo "  start         Start a training instance"
    echo "  stop          Stop the training instance"
    echo "  monitor       Monitor training progress"
    echo "  download      Download training results"
    echo "  cost          Show cost estimate"
    echo "  destroy       Destroy all infrastructure"
    echo "  help          Show this help message"
    echo ""
    echo "Typical workflow:"
    echo "  1. ./deploy.sh deploy     # Deploy infrastructure"
    echo "  2. ./deploy.sh upload     # Upload training data"
    echo "  3. ./deploy.sh start      # Start training"
    echo "  4. ./deploy.sh monitor    # Monitor progress"
    echo "  5. ./deploy.sh download   # Download results"
    echo "  6. ./deploy.sh destroy    # Clean up (optional)"
}

# Main script logic
case "${1:-help}" in
    "deploy")
        check_prerequisites
        deploy_infrastructure
        ;;
    "upload")
        upload_training_data
        ;;
    "start")
        start_training
        ;;
    "stop")
        stop_training
        ;;
    "monitor")
        monitor_training
        ;;
    "download")
        download_results
        ;;
    "cost")
        estimate_cost
        ;;
    "destroy")
        destroy_infrastructure
        ;;
    "help"|*)
        show_help
        ;;
esac
