#!/bin/bash
# User Data for EC2 instances used in GPU training

# Update packages
sudo apt-get update -y

# Install Docker
sudo apt-get install -y \ 
    apt-transport-https \ 
    ca-certificates \ 
    curl \ 
    software-properties-common

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository \ 
   "deb [arch=amd64] https://download.docker.com/linux/ubuntu \ 
   $(lsb_release -cs) \ 
   stable"

sudo apt-get update -y
sudo apt-get install -y docker-ce

# Add ubuntu to docker group
sudo usermod -aG docker ubuntu

# Pull required Docker images
aws s3 cp s3://${s3_bucket}/${name_prefix}/docker.tar.gz .
tar -xzvf docker.tar.gz

# Run initialization script
chmod +x init.sh
./init.sh

