"""
AWS S3 service for uploading and managing result files.

This service handles uploading result Excel files to S3 bucket
and provides secure access URLs for download.
"""

import boto3
import os
import logging
from typing import Optional
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class S3Service:
    """Service for AWS S3 operations."""
    
    def __init__(self):
        """Initialize S3 client with AWS credentials from environment or IAM role."""
        try:
            # Initialize S3 client - will use IAM role if running on EC2
            self.s3_client = boto3.client('s3')
            
            # Get S3 bucket name from environment variable
            self.bucket_name = os.getenv('S3_BUCKET_NAME', 'smartqp')
            
            # Get S3 bucket prefix for upload results
            self.bucket_prefix = os.getenv('S3_BUCKET_PREFIX', 'BulkUploadResponse')
            
            # Get AWS region from environment variable
            self.region = os.getenv('AWS_DEFAULT_REGION', 'ap-south-1')
            
            logger.info(f"S3 service initialized with bucket: {self.bucket_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize S3 service: {str(e)}")
            raise
    
    def upload_file(self, local_file_path: str, s3_key: str) -> str:
        """
        Upload a local file to S3 bucket.
        
        Args:
            local_file_path: Path to the local file to upload
            s3_key: S3 object key (path within bucket)
            
        Returns:
            str: S3 URL of the uploaded file
            
        Raises:
            HTTPException: If upload fails
        """
        try:
            # Check if local file exists
            if not os.path.exists(local_file_path):
                raise HTTPException(status_code=404, detail=f"Local file not found: {local_file_path}")
            
            # Upload file to S3
            self.s3_client.upload_file(
                local_file_path,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    'ServerSideEncryption': 'AES256'  # Enable server-side encryption
                }
            )
            
            # Generate S3 URL
            s3_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
            
            logger.info(f"Successfully uploaded file to S3: {s3_url}")
            return s3_url
            
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            raise HTTPException(
                status_code=500, 
                detail="AWS credentials not configured. Please check IAM role or credentials."
            )
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"S3 upload failed with error {error_code}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload file to S3: {error_code}"
            )
        except Exception as e:
            logger.error(f"Unexpected error during S3 upload: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload file to S3: {str(e)}"
            )
    
    def upload_file_from_memory(self, file_content: bytes, s3_key: str, content_type: str = "application/octet-stream") -> str:
        """
        Upload file content from memory to S3 bucket.
        
        Args:
            file_content: File content as bytes
            s3_key: S3 object key (path within bucket)
            content_type: MIME type of the file
            
        Returns:
            str: S3 URL of the uploaded file
            
        Raises:
            HTTPException: If upload fails
        """
        try:
            # Upload file content to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content,
                ContentType=content_type
            )
            
            # Generate S3 URL
            s3_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
            
            logger.info(f"Successfully uploaded file from memory to S3: {s3_url}")
            return s3_url
            
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            raise HTTPException(
                status_code=500, 
                detail="AWS credentials not configured. Please check IAM role or credentials."
            )
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"S3 upload from memory failed with error {error_code}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload file to S3: {error_code}"
            )
        except Exception as e:
            logger.error(f"Unexpected error during S3 upload from memory: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload file to S3: {str(e)}"
            )
    
    def generate_presigned_url(self, s3_key: str, expiration: int = 3600) -> str:
        """
        Generate a presigned URL for secure file download.
        
        Args:
            s3_key: S3 object key
            expiration: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            str: Presigned URL for file download
        """
        try:
            response = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )
            
            logger.info(f"Generated presigned URL for {s3_key}")
            return response
            
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to generate download URL"
            )
    
    def delete_file(self, s3_key: str) -> bool:
        """
        Delete a file from S3 bucket.
        
        Args:
            s3_key: S3 object key to delete
            
        Returns:
            bool: True if deletion was successful
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"Successfully deleted file from S3: {s3_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to delete file from S3: {str(e)}")
            return False
    
    def generate_s3_key(self, job_id: str, filename: str) -> str:
        """
        Generate S3 key (path) for a result file.
        
        Args:
            job_id: Upload job ID
            filename: Original filename
            
        Returns:
            str: S3 key for the file
        """
        # Store files directly in the BulkUploadResponse folder
        return f"{self.bucket_prefix}/{filename}"
    
    def check_bucket_exists(self) -> bool:
        """
        Check if the configured S3 bucket exists and is accessible.
        
        Returns:
            bool: True if bucket exists and is accessible
        """
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.error(f"S3 bucket '{self.bucket_name}' does not exist")
            else:
                logger.error(f"Cannot access S3 bucket '{self.bucket_name}': {error_code}")
            return False


# Create a singleton instance for use across the application
s3_service = S3Service()
