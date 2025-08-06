"""
LoRA Model Training Lambda Function

This function handles training character-specific LoRA models using Replicate's 
Flux LoRA training service. It processes training images and creates consistent 
character models for content generation.
"""

import json
import boto3
import os
import uuid
import time
from datetime import datetime, timezone
from decimal import Decimal
import replicate
from typing import Dict, List, Optional, Any

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
secrets_client = boto3.client('secretsmanager')

# Environment variables
BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'ai-influencer-system-content')
CHARACTERS_TABLE_NAME = os.environ.get('CHARACTERS_TABLE_NAME', 'ai-influencer-characters')
TRAINING_JOBS_TABLE_NAME = os.environ.get('TRAINING_JOBS_TABLE_NAME', 'ai-influencer-training-jobs')
REPLICATE_API_TOKEN_SECRET = os.environ.get('REPLICATE_API_TOKEN_SECRET', 'replicate-api-token')

def get_secret(secret_name: str) -> str:
    """Retrieve secret from AWS Secrets Manager"""
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except Exception as e:
        print(f"Error retrieving secret {secret_name}: {str(e)}")
        return None

def decimal_default(obj):
    """JSON serializer for DynamoDB Decimal types"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def lambda_handler(event, context):
    """Main Lambda handler for LoRA model training"""
    
    try:
        # Parse the event
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', event)
        
        action = body.get('action', 'train')
        
        if action == 'train':
            return handle_training_request(body, context)
        elif action == 'status':
            return handle_status_check(body, context)
        elif action == 'list':
            return handle_list_jobs(body, context)
        else:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Invalid action'})
            }
            
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f'Internal server error: {str(e)}'})
        }

def handle_training_request(body: Dict[str, Any], context) -> Dict[str, Any]:
    """Handle LoRA model training request"""
    
    try:
        # Required parameters
        character_id = body.get('character_id')
        if not character_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'character_id is required'})
            }
        
        # Get Replicate API token
        api_token = get_secret(REPLICATE_API_TOKEN_SECRET)
        if not api_token:
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Replicate API token not configured'})
            }
        
        # Initialize Replicate client
        replicate_client = replicate.Client(api_token=api_token)
        
        # Get character details
        characters_table = dynamodb.Table(CHARACTERS_TABLE_NAME)
        character_response = characters_table.get_item(Key={'id': character_id})
        
        if 'Item' not in character_response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Character not found'})
            }
        
        character = character_response['Item']
        character_name = character.get('name', 'unknown')
        
        # Get training images from S3
        training_images = get_training_images_for_character(character_id)
        if len(training_images) < 10:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': f'Insufficient training images. Found {len(training_images)}, need at least 10'
                })
            }
        
        # Create training job record
        job_id = str(uuid.uuid4())
        training_job = {
            'job_id': job_id,
            'character_id': character_id,
            'character_name': character_name,
            'status': 'starting',
            'training_images_count': len(training_images),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        # Save initial job record
        training_jobs_table = dynamodb.Table(TRAINING_JOBS_TABLE_NAME)
        training_jobs_table.put_item(Item=training_job)
        
        # Prepare training data for Replicate
        trigger_word = f"{character_name.lower().replace(' ', '_')}_character"
        
        # Create zip file URL with training images
        zip_url = create_training_data_zip(character_id, training_images)
        
        # Start LoRA training on Replicate
        # Using Replicate's Flux LoRA training model
        print(f"Starting LoRA training for character {character_id} with {len(training_images)} images")
        
        training_input = {
            "input_images": zip_url,
            "trigger_word": trigger_word,
            "max_train_steps": 1000,
            "learning_rate": 1e-4,
            "batch_size": 1,
            "resolution": 512,
            "seed": 42,
            "autocaption": True,
            "hf_repo_id": f"ai-influencer-{character_id}-lora",
            "hf_token": "",  # Optional: for private repos
            "is_public": False
        }
        
        # Submit training job to Replicate
        try:
            prediction = replicate_client.predictions.create(
                model="ostris/flux-dev-lora-trainer",
                input=training_input
            )
            
            replicate_id = prediction.id
            
            # Update job record with Replicate ID
            training_job.update({
                'replicate_id': replicate_id,
                'status': 'training',
                'trigger_word': trigger_word,
                'updated_at': datetime.now(timezone.utc).isoformat()
            })
            
            training_jobs_table.put_item(Item=training_job)
            
            print(f"LoRA training started: {replicate_id}")
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'job_id': job_id,
                    'replicate_id': replicate_id,
                    'status': 'training',
                    'character_id': character_id,
                    'trigger_word': trigger_word,
                    'training_images_count': len(training_images),
                    'message': 'LoRA training started successfully'
                }, default=decimal_default)
            }
            
        except Exception as e:
            # Update job status to failed
            training_job.update({
                'status': 'failed',
                'error': str(e),
                'updated_at': datetime.now(timezone.utc).isoformat()
            })
            training_jobs_table.put_item(Item=training_job)
            
            raise e
        
    except Exception as e:
        print(f"Error in handle_training_request: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f'Training failed: {str(e)}'})
        }

def handle_status_check(body: Dict[str, Any], context) -> Dict[str, Any]:
    """Check the status of a LoRA training job"""
    
    try:
        job_id = body.get('job_id')
        if not job_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'job_id is required'})
            }
        
        # Get job from database
        training_jobs_table = dynamodb.Table(TRAINING_JOBS_TABLE_NAME)
        job_response = training_jobs_table.get_item(Key={'job_id': job_id})
        
        if 'Item' not in job_response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Training job not found'})
            }
        
        job = job_response['Item']
        
        # If job has Replicate ID, check status with Replicate
        if job.get('replicate_id') and job.get('status') in ['training', 'starting']:
            api_token = get_secret(REPLICATE_API_TOKEN_SECRET)
            if api_token:
                replicate_client = replicate.Client(api_token=api_token)
                
                try:
                    prediction = replicate_client.predictions.get(job['replicate_id'])
                    
                    # Update job status based on Replicate status
                    if prediction.status == 'succeeded':
                        # LoRA training completed
                        job.update({
                            'status': 'completed',
                            'lora_model_url': prediction.output,
                            'completed_at': datetime.now(timezone.utc).isoformat(),
                            'updated_at': datetime.now(timezone.utc).isoformat()
                        })
                        
                        # Update character record with LoRA model info
                        update_character_with_lora_model(job['character_id'], {
                            'lora_model_url': prediction.output,
                            'trigger_word': job.get('trigger_word'),
                            'training_completed_at': datetime.now(timezone.utc).isoformat()
                        })
                        
                    elif prediction.status == 'failed':
                        job.update({
                            'status': 'failed',
                            'error': prediction.error or 'Training failed on Replicate',
                            'updated_at': datetime.now(timezone.utc).isoformat()
                        })
                    
                    elif prediction.status in ['starting', 'processing']:
                        job.update({
                            'status': 'training',
                            'updated_at': datetime.now(timezone.utc).isoformat()
                        })
                    
                    # Save updated job
                    training_jobs_table.put_item(Item=job)
                    
                except Exception as e:
                    print(f"Error checking Replicate status: {str(e)}")
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(job, default=decimal_default)
        }
        
    except Exception as e:
        print(f"Error in handle_status_check: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f'Status check failed: {str(e)}'})
        }

def handle_list_jobs(body: Dict[str, Any], context) -> Dict[str, Any]:
    """List all LoRA training jobs"""
    
    try:
        character_id = body.get('character_id')  # Optional filter
        
        training_jobs_table = dynamodb.Table(TRAINING_JOBS_TABLE_NAME)
        
        if character_id:
            # Filter by character
            response = training_jobs_table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('character_id').eq(character_id)
            )
        else:
            # Get all jobs
            response = training_jobs_table.scan()
        
        jobs = response.get('Items', [])
        
        # Sort by creation date (newest first)
        jobs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'jobs': jobs,
                'count': len(jobs)
            }, default=decimal_default)
        }
        
    except Exception as e:
        print(f"Error in handle_list_jobs: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f'Failed to list jobs: {str(e)}'})
        }

def get_training_images_for_character(character_id: str) -> List[str]:
    """Get list of training image URLs for a character from S3"""
    
    try:
        prefix = f"training-images/{character_id}/"
        
        response = s3_client.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix=prefix
        )
        
        images = []
        for obj in response.get('Contents', []):
            if obj['Key'].lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                # Generate presigned URL for the image
                url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': BUCKET_NAME, 'Key': obj['Key']},
                    ExpiresIn=3600 * 24  # 24 hours
                )
                images.append(url)
        
        return images
        
    except Exception as e:
        print(f"Error getting training images: {str(e)}")
        return []

def create_training_data_zip(character_id: str, image_urls: List[str]) -> str:
    """Create a zip file with training images and upload to S3"""
    
    import zipfile
    import tempfile
    import requests
    from io import BytesIO
    
    try:
        # Create temporary zip file
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_zip:
            with zipfile.ZipFile(tmp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                
                for i, image_url in enumerate(image_urls):
                    try:
                        # Download image
                        response = requests.get(image_url, timeout=30)
                        response.raise_for_status()
                        
                        # Add to zip with sequential naming
                        filename = f"image_{i+1:03d}.jpg"
                        zipf.writestr(filename, response.content)
                        
                    except Exception as e:
                        print(f"Error downloading image {image_url}: {str(e)}")
                        continue
            
            # Upload zip to S3
            zip_key = f"training-data/{character_id}/training_images.zip"
            
            with open(tmp_zip.name, 'rb') as zip_file:
                s3_client.upload_fileobj(
                    zip_file,
                    BUCKET_NAME,
                    zip_key,
                    ExtraArgs={'ContentType': 'application/zip'}
                )
            
            # Generate presigned URL for the zip
            zip_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': BUCKET_NAME, 'Key': zip_key},
                ExpiresIn=3600 * 24  # 24 hours
            )
            
            return zip_url
            
    except Exception as e:
        print(f"Error creating training data zip: {str(e)}")
        raise e

def update_character_with_lora_model(character_id: str, lora_info: Dict[str, Any]):
    """Update character record with LoRA model information"""
    
    try:
        characters_table = dynamodb.Table(CHARACTERS_TABLE_NAME)
        
        characters_table.update_item(
            Key={'id': character_id},
            UpdateExpression="SET lora_model_url = :url, trigger_word = :trigger, training_completed_at = :completed, updated_at = :updated",
            ExpressionAttributeValues={
                ':url': lora_info.get('lora_model_url'),
                ':trigger': lora_info.get('trigger_word'),
                ':completed': lora_info.get('training_completed_at'),
                ':updated': datetime.now(timezone.utc).isoformat()
            }
        )
        
        print(f"Updated character {character_id} with LoRA model info")
        
    except Exception as e:
        print(f"Error updating character with LoRA model: {str(e)}")

# Ensure DynamoDB tables exist
def ensure_tables_exist():
    """Create DynamoDB tables if they don't exist"""
    
    try:
        # Training jobs table
        training_jobs_table = dynamodb.Table(TRAINING_JOBS_TABLE_NAME)
        training_jobs_table.load()
    except:
        # Create training jobs table
        dynamodb.create_table(
            TableName=TRAINING_JOBS_TABLE_NAME,
            KeySchema=[
                {'AttributeName': 'job_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'job_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        print(f"Created table: {TRAINING_JOBS_TABLE_NAME}")

# Initialize tables on cold start
ensure_tables_exist()
