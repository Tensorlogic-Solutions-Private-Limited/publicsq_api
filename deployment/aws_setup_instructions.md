# AWS S3 Configuration for Bulk Upload Result Files

This document provides step-by-step instructions for configuring AWS S3 and EC2 IAM roles to support the bulk upload result file functionality.

## Prerequisites

- AWS Account with appropriate permissions
- EC2 instance running the application (ip-172-31-42-110)
- S3 bucket for storing result files

## Current Setup Details

- **EC2 Instance**: ip-172-31-42-110 (13.232.204.43)
- **SSH Key**: qn-gen-VS.pem
- **Application Path**: /var/www/smartqp-api
- **Service Name**: smartqp-api.service
- **S3 Bucket**: smartqp
- **AWS Region**: ap-south-1 (Mumbai)
- **Application User**: ubuntu

## Step 1: Create S3 Bucket

### 1.1 Create the Bucket

```bash
# Create the bucket in ap-south-1 region (Mumbai)
aws s3 mb s3://smartqp --region ap-south-1
```

### 1.2 Configure Bucket Versioning (Optional but Recommended)

```bash
aws s3api put-bucket-versioning \
  --bucket smartqp \
  --versioning-configuration Status=Enabled
```

### 1.3 Configure Server-Side Encryption

```bash
aws s3api put-bucket-encryption \
  --bucket smartqp \
  --server-side-encryption-configuration '{
    "Rules": [
      {
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "AES256"
        },
        "BucketKeyEnabled": true
      }
    ]
  }'
```

## Step 2: Create IAM Policy for S3 Access

### 2.1 Create S3 Access Policy

Create a file named `s3-upload-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::smartqp/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": "arn:aws:s3:::smartqp"
    }
  ]
}
```

### 2.2 Create the IAM Policy

```bash
aws iam create-policy \
  --policy-name SmartQPS3UploadPolicy \
  --policy-document file://s3-upload-policy.json \
  --description "Policy for SmartQP application to upload result files to S3"
```

## Step 3: Create IAM Role for EC2

### 3.1 Create Trust Policy

Create a file named `ec2-trust-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

### 3.2 Create the IAM Role

```bash
aws iam create-role \
  --role-name SmartQPEC2Role \
  --assume-role-policy-document file://ec2-trust-policy.json \
  --description "IAM role for SmartQP EC2 instances to access S3"
```

### 3.3 Attach Policy to Role

```bash
# Get  account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Attach the S3 policy to the role
aws iam attach-role-policy \
  --role-name SmartQPEC2Role \
  --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/SmartQPS3UploadPolicy
```

## Step 4: Create Instance Profile

### 4.1 Create Instance Profile

```bash
aws iam create-instance-profile \
  --instance-profile-name SmartQPEC2InstanceProfile
```

### 4.2 Add Role to Instance Profile

```bash
aws iam add-role-to-instance-profile \
  --instance-profile-name SmartQPEC2InstanceProfile \
  --role-name SmartQPEC2Role
```

## Step 5: Attach Instance Profile to EC2

### 5.1 If Creating a New EC2 Instance

```bash
aws ec2 run-instances \
  --image-id ami-xxxxxxxxx \
  --count 1 \
  --instance-type t3.medium \
  --key-name qn-gen-VS \
  --security-group-ids sg-xxxxxxxxx \
  --subnet-id subnet-xxxxxxxxx \
  --iam-instance-profile Name=SmartQPEC2InstanceProfile
```

### 5.2 If Attaching to Existing EC2 Instance

```bash
# Get  instance ID (replace with  actual instance ID)
INSTANCE_ID="i-xxxxxxxxxxxxxxxxx"

# Associate the instance profile
aws ec2 associate-iam-instance-profile \
  --instance-id $INSTANCE_ID \
  --iam-instance-profile Name=SmartQPEC2InstanceProfile
```

## Step 6: Configure Application Environment Variables

Add these environment variables to  application deployment:

### 6.1 Update Environment Variables

```bash
# Add to  .env file or environment configuration
export S3_BUCKET_NAME=smartqp
export AWS_DEFAULT_REGION=ap-south-1
```

### 6.2 For Docker/Container Deployment

```yaml
# docker-compose.yml or Kubernetes deployment
environment:
  - S3_BUCKET_NAME=smartqp
  - AWS_DEFAULT_REGION=ap-south-1
```

### 6.3 For Systemd Service

```ini
# In  service file
[Service]
Environment=S3_BUCKET_NAME=smartqp
Environment=AWS_DEFAULT_REGION=ap-south-1
```

## Step 7: Configure S3 Bucket Policy (Optional - for Additional Security)

### 7.1 Create Bucket Policy

Create a file named `bucket-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::_ACCOUNT_ID:role/SmartQPEC2Role"
      },
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::smartqp/*"
    },
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::_ACCOUNT_ID:role/SmartQPEC2Role"
      },
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": "arn:aws:s3:::smartqp"
    }
  ]
}
```

### 7.2 Apply Bucket Policy

```bash
aws s3api put-bucket-policy \
  --bucket smartqp \
  --policy file://bucket-policy.json
```

## Step 8: Test the Configuration

### 8.1 Test from EC2 Instance

```bash
# SSH to  EC2 instance and test S3 access
aws s3 ls s3://smartqp/

# Test upload
echo "test file" > test.txt
aws s3 cp test.txt s3://smartqp/BulkUploadResponse/test/
```

### 8.2 Test Application S3 Integration

```python
# Test script to verify S3 integration
import boto3
import os

def test_s3_connection():
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.getenv('S3_BUCKET_NAME')
        
        # Test bucket access
        response = s3_client.head_bucket(Bucket=bucket_name)
        print(f"✅ Successfully connected to bucket: {bucket_name}")
        
        # Test upload
        s3_client.put_object(
            Bucket=bucket_name,
            Key='BulkUploadResponse/test/connection-test.txt',
            Body='Connection test successful',
            ServerSideEncryption='AES256'
        )
        print("✅ Successfully uploaded test file")
        
        # Test download
        response = s3_client.get_object(
            Bucket=bucket_name,
            Key='BulkUploadResponse/test/connection-test.txt'
        )
        content = response['Body'].read().decode('utf-8')
        print(f"✅ Successfully downloaded test file: {content}")
        
        # Clean up
        s3_client.delete_object(
            Bucket=bucket_name,
            Key='BulkUploadResponse/test/connection-test.txt'
        )
        print("✅ Successfully cleaned up test file")
        
    except Exception as e:
        print(f"❌ Error testing S3 connection: {str(e)}")

if __name__ == "__main__":
    test_s3_connection()
```

## Step 9: Security Best Practices

### 9.1 Enable CloudTrail Logging

```bash
aws cloudtrail create-trail \
  --name smartqp-s3-trail \
  --s3-bucket-name -cloudtrail-bucket \
  --include-global-service-events \
  --is-multi-region-trail
```

### 9.2 Set Up S3 Access Logging

```bash
aws s3api put-bucket-logging \
  --bucket smartqp \
  --bucket-logging-status '{
    "LoggingEnabled": {
      "TargetBucket": "-access-logs-bucket",
      "TargetPrefix": "smartqp-s3-access-logs/"
    }
  }'
```

### 9.3 Configure Lifecycle Policy (Optional)

```bash
# Create lifecycle policy to automatically delete old files
aws s3api put-bucket-lifecycle-configuration \
  --bucket smartqp \
  --lifecycle-configuration '{
    "Rules": [
      {
        "ID": "DeleteOldResultFiles",
        "Status": "Enabled",
        "Filter": {
          "Prefix": "BulkUploadResponse/"
        },
        "Expiration": {
          "Days": 90
        }
      }
    ]
  }'
```

## Troubleshooting

### Common Issues and Solutions

1. **Permission Denied Errors**
   - Verify IAM role is attached to EC2 instance
   - Check IAM policy permissions
   - Ensure bucket name matches environment variable

2. **Bucket Not Found**
   - Verify bucket name is globally unique
   - Check region configuration
   - Ensure bucket exists in the specified region

3. **Network Connectivity Issues**
   - Check VPC endpoints for S3 if using private subnets
   - Verify security groups allow HTTPS outbound traffic
   - Check NAT gateway configuration for private subnets

4. **Application Integration Issues**
   - Verify boto3 is installed: `pip install boto3`
   - Check environment variables are set correctly
   - Test AWS credentials with AWS CLI

### Verification Commands

```bash
# Check if instance profile is attached
aws ec2 describe-instances --instance-ids i-xxxxxxxxxxxxxxxxx \
  --query 'Reservations[0].Instances[0].IamInstanceProfile'

# Check role policies
aws iam list-attached-role-policies --role-name SmartQPEC2Role

# Test S3 access from application server
curl -s http://169.254.169.254/latest/meta-data/iam/security-credentials/SmartQPEC2Role
```

## Cost Optimization

1. **Use Intelligent Tiering** for long-term storage
2. **Set up lifecycle policies** to automatically delete old files
3. **Monitor usage** with AWS Cost Explorer
4. **Use S3 Transfer Acceleration** only if needed for global users

## Monitoring and Alerts

Set up CloudWatch alarms for:
- S3 PUT/GET request counts
- Error rates
- Storage usage
- Data transfer costs

## Quick Setup for Current Instance

If you want to quickly set up S3 access for  current instance (ip-172-31-42-110), follow these steps:

### 1. Install boto3 on the server
```bash
# SSH to  instance
ssh -i "qn-gen-VS.pem" ubuntu@13.232.204.43

# Navigate to application directory
cd /var/www/smartqp-api

# Activate virtual environment
source venv/bin/activate

# Install boto3
pip install boto3

# Restart the service
sudo systemctl restart smartqp-api.service
```

### 2. Set environment variables
```bash
# Add to  systemd service file
sudo nano /etc/systemd/system/smartqp-api.service

# Add these lines under [Service]:
Environment=S3_BUCKET_NAME=smartqp
Environment=AWS_DEFAULT_REGION=ap-south-1

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart smartqp-api.service
```

### 3. Verify the setup
```bash
# Check service status
sudo systemctl status smartqp-api.service

# Test S3 access (if IAM role is configured)
aws s3 ls s3://smartqp/
```

This completes the AWS S3 configuration for  bulk upload result files functionality.
