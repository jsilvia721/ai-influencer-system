# AWS Training Infrastructure for AI Influencer System

This Terraform configuration creates a cost-optimized AWS infrastructure for training LoRA models using kohya_ss on spot instances.

## 🚀 Quick Start

1. **Install Prerequisites**:
   ```bash
   # Install Terraform
   brew install terraform  # macOS
   # or download from https://terraform.io/downloads
   
   # Install AWS CLI
   brew install awscli  # macOS
   # or download from https://aws.amazon.com/cli/
   
   # Configure AWS credentials
   aws configure
   ```

2. **Set Up Configuration**:
   ```bash
   cd terraform/
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your settings
   ```

3. **Deploy and Train**:
   ```bash
   ./deploy.sh deploy      # Deploy infrastructure
   ./deploy.sh upload      # Upload training data
   ./deploy.sh start       # Start training
   ./deploy.sh monitor     # Monitor progress
   ./deploy.sh download    # Download results
   ```

## 💰 Cost Optimization Features

### Spot Instances
- **Up to 90% savings** compared to on-demand instances
- Automatic spot price bidding
- Diversified instance allocation across availability zones

### Instance Recommendations
| Instance Type | GPU Memory | Spot Price Range | Best For |
|---------------|------------|------------------|----------|
| `g4dn.xlarge` | 16GB | $0.20-0.40/hr | Most LoRA training |
| `g4dn.2xlarge` | 16GB | $0.40-0.80/hr | Faster training |
| `p3.2xlarge` | 16GB | $0.60-1.20/hr | High performance |

### Storage Optimization
- **GP3 EBS volumes** for better cost/performance ratio
- Automatic volume deletion on termination
- 100GB default size (adjustable)

### Auto-Scaling
- **Start with 0 instances** - only pay when training
- Automatic shutdown after training completion
- Scale up/down on demand

## 🏗️ Infrastructure Components

### Core Infrastructure
- **VPC** with public subnet for training instances
- **Security Group** with SSH, Jupyter, and TensorBoard access
- **Internet Gateway** for outbound internet access

### Compute Resources
- **Launch Template** with Deep Learning AMI
- **Auto Scaling Group** with spot instance policies
- **IAM roles** for S3 and CloudWatch access

### Storage & Monitoring
- **S3 bucket** for training data and model storage
- **CloudWatch** for monitoring and logging
- **SNS** for training completion notifications

## 📁 Directory Structure

```
terraform/
├── main.tf                 # Main Terraform configuration
├── user_data.sh           # Instance initialization script
├── terraform.tfvars.example  # Configuration template
├── deploy.sh              # Deployment management script
└── README.md              # This file
```

## 🔧 Configuration Options

### terraform.tfvars Settings

```hcl
# Region (us-east-1 typically has cheapest spot prices)
aws_region = "us-east-1"

# Project name for resource naming
project_name = "ai-influencer-training"

# Instance configuration
instance_type = "g4dn.xlarge"
max_spot_price = "0.50"

# Training parameters  
training_duration_hours = 4

# Security
key_pair_name = "your-key-pair-name"  # REQUIRED!
allowed_cidr_blocks = ["0.0.0.0/0"]   # Restrict to your IP
```

## 🔐 Security Best Practices

1. **Restrict Access**: Update `allowed_cidr_blocks` to your IP only
2. **Use Key Pairs**: Ensure you have an EC2 key pair created
3. **Encrypted Storage**: EBS volumes are encrypted by default
4. **IAM Roles**: Minimal permissions for S3 and CloudWatch access

## 📊 Training Workflow

### 1. Data Preparation
Your training data should be structured like this:
```
training_data/
├── 10_sofia woman/
│   ├── image_001.jpg
│   ├── image_001.txt
│   └── ...
└── training_config.toml
```

### 2. Deployment Commands
```bash
# Deploy infrastructure
./deploy.sh deploy

# Upload your training data
./deploy.sh upload

# Start training instance
./deploy.sh start

# Monitor training progress
./deploy.sh monitor

# Download trained models
./deploy.sh download

# Clean up when done
./deploy.sh destroy
```

### 3. Monitoring Options
- **TensorBoard**: `http://INSTANCE_IP:6006`
- **Jupyter Notebook**: `http://INSTANCE_IP:8888` (token: `training-token`)
- **SSH Access**: `ssh -i your-key.pem ubuntu@INSTANCE_IP`
- **Logs**: Check S3 bucket for training logs

## 💡 Training Optimization

### kohya_ss Configuration
The infrastructure is optimized for kohya_ss with:
- **Mixed precision (fp16)** for memory efficiency
- **Cached latents** for faster data loading  
- **AdamW8bit optimizer** for reduced memory usage
- **XFormers** for attention optimization

### Cost-Saving Tips
1. **Use us-east-1** region for cheapest spot prices
2. **Set realistic max_spot_price** (70% of on-demand price)
3. **Monitor training progress** and stop when complete
4. **Use smaller instance types** for initial testing
5. **Clean up resources** when not in use

## 🚨 Troubleshooting

### Common Issues

**Spot Instance Interruption**:
- Training data and progress are saved to S3
- Instance will automatically restart training from last checkpoint
- Consider using persistent instances for critical training

**Permission Errors**:
- Ensure AWS credentials are configured: `aws configure`
- Verify key pair exists: Check AWS EC2 console
- Check IAM permissions for EC2, S3, and Auto Scaling

**Training Fails**:
- Check instance logs: `ssh` into instance and check `/var/log/user-data.log`
- Monitor S3 for training logs
- Verify training data format matches kohya_ss requirements

**High Costs**:
- Check current spot prices: AWS EC2 console > Spot Requests
- Adjust `max_spot_price` in terraform.tfvars
- Ensure instances are terminated after training

### Getting Help
- Check AWS CloudWatch logs for detailed error messages
- Monitor S3 bucket for training progress and logs
- SSH into running instances for real-time debugging

## 🧹 Cleanup

**Important**: Always run cleanup to avoid ongoing charges:

```bash
# Stop training instance
./deploy.sh stop

# Destroy all infrastructure
./deploy.sh destroy
```

This will remove:
- All EC2 instances
- Auto Scaling Groups  
- VPC and networking resources
- **S3 bucket and data** (⚠️ backup first!)

## 📝 Cost Estimation

Typical training costs for a 4-hour LoRA training session:

| Component | Cost |
|-----------|------|
| g4dn.xlarge spot (4h) | $0.80-1.60 |
| EBS storage (4h) | $0.32 |
| S3 storage/transfer | $0.10 |
| **Total Estimate** | **$1.22-2.02** |

*Actual costs may be lower due to spot pricing and shorter training times.*

## 🎯 Next Steps

After successful training:
1. **Integrate with your main application** - Update `config/config.yaml` with trained model
2. **Test the model** - Use your API to generate images with the new LoRA
3. **Optimize further** - Experiment with different training parameters
4. **Scale up** - Train multiple characters or use larger datasets

This infrastructure setup gives you professional-grade AI training capabilities at a fraction of the cost of managed services!
