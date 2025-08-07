"""
LoRA Model Training Lambda Function with Replicate API Integration using urllib3

This function handles training character-specific LoRA models using Replicate's 
Flux LoRA training service. It processes training images and creates consistent 
character models for content generation.
"""

import json
import boto3
import os
import uuid
import time
import urllib3
import zipfile
import tempfile
from datetime import datetime, timezone
from decimal import Decimal

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
secrets_client = boto3.client('secretsmanager')

# Initialize urllib3
http = urllib3.PoolManager()

# Environment variables
BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'ai-influencer-system-content')
CHARACTERS_TABLE_NAME = os.environ.get('CHARACTERS_TABLE_NAME', 'ai-influencer-characters')
TRAINING_JOBS_TABLE_NAME = os.environ.get('TRAINING_JOBS_TABLE_NAME', 'ai-influencer-training-jobs')
REPLICATE_API_TOKEN_SECRET = os.environ.get('REPLICATE_API_TOKEN_SECRET', 'replicate-api-token')

def get_secret(secret_name):
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

def handler(event, context):
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

def handle_training_request(body, context):
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
        if not api_token or api_token == "placeholder-token-needs-to-be-updated":
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Replicate API token not configured. Please set up the token in AWS Secrets Manager.'})
            }
        
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
        
        # Get selected training images from character record
        selected_training_images = character.get('selected_training_images', [])
        if not selected_training_images:
            # No fallback - require selected training images to be present
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'No selected training images found for this character. Please select and upload training images before starting training.'
                })
            }
        
        training_images = selected_training_images
        
        if len(training_images) < 5:  # Reduced minimum for testing
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': f'Insufficient training images. Found {len(training_images)}, need at least 5 for testing (normally 10+). Please select more training images.'
                })
            }
        
        # Create training job record
        job_id = str(uuid.uuid4())
        training_job = {
            'job_id': job_id,
            'character_id': character_id,
            'character_name': character_name,
            'status': 'preparing',
            'training_images_count': len(training_images),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'replicate_id': 'pending',
            'trigger_word': f"{character_name.lower().replace(' ', '_')}_character"
        }
        
        # Save initial job record
        training_jobs_table = dynamodb.Table(TRAINING_JOBS_TABLE_NAME)
        training_jobs_table.put_item(Item=training_job)
        
        print(f"Starting LoRA training for character {character_id} with {len(training_images)} images")
        
        # Create zip file with training images and upload to S3
        zip_url = create_training_data_zip(character_id, training_images)
        
        # Prepare training data for Replicate
        trigger_word = training_job['trigger_word']
        
        # Create character-specific training prompt
        character_description = character.get('description', '')
        character_style = character.get('style', '')
        character_personality = character.get('personality', '')
        
        # Build a comprehensive training prompt
        training_prompt_parts = [f"A photo of {trigger_word}"]
        
        if character_description:
            training_prompt_parts.append(character_description)
        
        if character_style:
            training_prompt_parts.append(f"in {character_style} style")
            
        training_prompt_parts.extend([
            "high quality",
            "detailed",
            "professional photography"
        ])
        
        training_prompt = ", ".join(training_prompt_parts)
        
        # Start LoRA training on Replicate using urllib3
        try:
            # Get webhook URL for real-time status updates
            webhook_url = os.environ.get('REPLICATE_WEBHOOK_URL')
            
            # Generate a seed based on character ID and current time for reproducibility
            # but uniqueness across different training runs
            import hashlib
            seed_string = f"{character_id}_{int(time.time() * 1000)}"
            seed = int(hashlib.md5(seed_string.encode()).hexdigest()[:8], 16) % 1000000
            
            training_input = {
                "input_images": zip_url,
                "trigger_word": trigger_word,
                "lora_type": "subject",  # Training a specific character/person
                "training_steps": 1000,  # Fast training steps
                "seed": seed
            }
            
            # Submit training job to Replicate
            headers = {
                'Authorization': f'Token {api_token}',
                'Content-Type': 'application/json'
            }
            
            # Build payload for training endpoint with required destination and version
            # Create a destination model name based on character
            character_model_name = f"lora-{character_name.lower().replace(' ', '-')}-{character_id[:8]}"
            destination_model = f"jsilvia721/{character_model_name}"
            
            # First, create the destination model if it doesn't exist
            model_created = create_destination_model(api_token, character_model_name, character_name)
            if not model_created:
                return {
                    'statusCode': 500,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'Failed to create destination model on Replicate'})
                }
            
            payload_data = {
                'version': 'f463fbfc97389e10a2f443a8a84b6953b1058eafbf0c9af4d84457ff07cb04db',
                'destination': destination_model,
                'input': training_input
            }
            
            # Add webhook URL if configured (per Replicate docs)
            if webhook_url:
                payload_data['webhook'] = webhook_url
                # Only send webhook for start and completed events to reduce noise
                payload_data['webhook_events_filter'] = ['start', 'completed']
                print(f"Using webhook URL: {webhook_url}")
            else:
                print("No webhook URL configured, status updates will require polling")
            
            print(f"Training payload: {json.dumps(payload_data, indent=2)}")
            
            response = http.request(
                'POST',
                f'https://api.replicate.com/v1/models/replicate/fast-flux-trainer/versions/{payload_data["version"]}/trainings',
                body=json.dumps({
                    'destination': payload_data['destination'],
                    'input': payload_data['input'],
                    'webhook': payload_data.get('webhook'),
                    'webhook_events_filter': payload_data.get('webhook_events_filter')
                }),
                headers=headers
            )
            
            if response.status == 201:
                prediction_data = json.loads(response.data.decode('utf-8'))
                replicate_id = prediction_data['id']
                
                # Update job record with Replicate ID
                training_job.update({
                    'replicate_id': replicate_id,
                    'status': 'training',
                    'replicate_status': prediction_data.get('status', 'starting'),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                })
                
                training_jobs_table.put_item(Item=training_job)
                
                # Update character training status to 'training'
                update_character_training_status(character_id, 'training')
                
                print(f"LoRA training started successfully: {replicate_id}")
                
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
                        'message': 'LoRA training started successfully on Replicate'
                    }, default=decimal_default)
                }
            else:
                error_msg = f"Replicate API error: {response.status} - {response.data.decode('utf-8')}"
                print(error_msg)
                
                # Update job status to failed
                training_job.update({
                    'status': 'failed',
                    'error': error_msg,
                    'updated_at': datetime.now(timezone.utc).isoformat()
                })
                training_jobs_table.put_item(Item=training_job)
                
                return {
                    'statusCode': 500,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': f'Failed to start training: {error_msg}'})
                }
                
        except Exception as e:
            error_msg = f"Error calling Replicate API: {str(e)}"
            print(error_msg)
            
            # Update job status to failed
            training_job.update({
                'status': 'failed',
                'error': error_msg,
                'updated_at': datetime.now(timezone.utc).isoformat()
            })
            training_jobs_table.put_item(Item=training_job)
            
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': error_msg})
            }
        
    except Exception as e:
        print(f"Error in handle_training_request: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f'Training failed: {str(e)}'})
        }

def handle_status_check(body, context):
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
        if job.get('replicate_id') and job.get('replicate_id') != 'pending' and job.get('status') in ['training', 'preparing']:
            api_token = get_secret(REPLICATE_API_TOKEN_SECRET)
            if api_token:
                try:
                    headers = {'Authorization': f'Token {api_token}'}
                    response = http.request(
                        'GET',
                        f'https://api.replicate.com/v1/predictions/{job["replicate_id"]}',
                        headers=headers
                    )
                    
                    if response.status == 200:
                        prediction_data = json.loads(response.data.decode('utf-8'))
                        replicate_status = prediction_data.get('status')
                        
                        # Update job status based on Replicate status
                        if replicate_status == 'succeeded':
                            # LoRA training completed
                            job.update({
                                'status': 'completed',
                                'replicate_status': 'succeeded',
                                'lora_model_url': prediction_data.get('output'),
                                'completed_at': datetime.now(timezone.utc).isoformat(),
                                'updated_at': datetime.now(timezone.utc).isoformat()
                            })
                            
                            # Update character record with LoRA model info
                            update_character_with_lora_model(job['character_id'], {
                                'lora_model_url': prediction_data.get('output'),
                                'trigger_word': job.get('trigger_word'),
                                'training_completed_at': datetime.now(timezone.utc).isoformat()
                            })
                            
                            # Update character training status to 'completed'
                            update_character_training_status(job['character_id'], 'completed')
                            
                        elif replicate_status == 'failed':
                            job.update({
                                'status': 'failed',
                                'replicate_status': 'failed',
                                'error': prediction_data.get('error', 'Training failed on Replicate'),
                                'updated_at': datetime.now(timezone.utc).isoformat()
                            })
                            
                            # Update character training status to 'failed'
                            update_character_training_status(job['character_id'], 'failed')
                        
                        elif replicate_status in ['starting', 'processing']:
                            job.update({
                                'status': 'training',
                                'replicate_status': replicate_status,
                                'updated_at': datetime.now(timezone.utc).isoformat()
                            })
                            
                            # Update character training status to 'training'
                            update_character_training_status(job['character_id'], 'training')
                        
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

def handle_list_jobs(body, context):
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

def get_training_images_for_character(character_id):
    """Get list of training image URLs for a character from S3"""
    
    try:
        # Try multiple possible locations for training images
        possible_prefixes = [
            f"training-images/{character_id}/",  # Original location
        ]
        
        # Also check for any folders under training-images/ that might contain this character's images
        # This handles cases where images were generated with job_id as folder name
        try:
            list_response = s3_client.list_objects_v2(
                Bucket=BUCKET_NAME,
                Prefix="training-images/",
                Delimiter="/"
            )
            
            # Add all subdirectories as possible locations
            for common_prefix in list_response.get('CommonPrefixes', []):
                prefix = common_prefix['Prefix']
                if prefix not in possible_prefixes:
                    possible_prefixes.append(prefix)
        except Exception as e:
            print(f"Warning: Could not list training-images directories: {e}")
        
        all_images = []
        
        for prefix in possible_prefixes:
            try:
                response = s3_client.list_objects_v2(
                    Bucket=BUCKET_NAME,
                    Prefix=prefix
                )
                
                for obj in response.get('Contents', []):
                    if obj['Key'].lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                        # Generate presigned URL for the image
                        url = s3_client.generate_presigned_url(
                            'get_object',
                            Params={'Bucket': BUCKET_NAME, 'Key': obj['Key']},
                            ExpiresIn=3600 * 24  # 24 hours
                        )
                        all_images.append(url)
                        
            except Exception as e:
                print(f"Error checking prefix {prefix}: {str(e)}")
                continue
        
        # Remove duplicates while preserving order
        unique_images = []
        seen = set()
        for img in all_images:
            if img not in seen:
                unique_images.append(img)
                seen.add(img)
        
        print(f"Found {len(unique_images)} training images for character {character_id}")
        return unique_images
        
    except Exception as e:
        print(f"Error getting training images: {str(e)}")
        return []

def create_training_data_zip(character_id, image_urls):
    """Create a zip file with training images and upload to S3"""
    
    try:
        # Create temporary zip file
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_zip:
            with zipfile.ZipFile(tmp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                
                for i, image_url in enumerate(image_urls):
                    try:
                        # Extract S3 key from URL and generate fresh presigned URL
                        if 's3.amazonaws.com' in image_url:
                            # Extract the S3 key from the URL
                            if '?' in image_url:
                                base_url = image_url.split('?')[0]
                            else:
                                base_url = image_url
                            
                            # Get the S3 key (everything after the bucket name)
                            bucket_part = f"https://{BUCKET_NAME}.s3.amazonaws.com/"
                            if base_url.startswith(bucket_part):
                                s3_key = base_url[len(bucket_part):]
                                
                                # Download directly from S3 using boto3
                                try:
                                    response = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
                                    image_data = response['Body'].read()
                                    
                                    # Add to zip with sequential naming
                                    filename = f"image_{i+1:03d}.jpg"
                                    zipf.writestr(filename, image_data)
                                    print(f"Added image {i+1} from S3 key: {s3_key}")
                                    continue
                                    
                                except Exception as s3_error:
                                    print(f"Error downloading from S3 key {s3_key}: {str(s3_error)}")
                                    # Fall back to URL download
                        
                        # Fallback: try to download using the URL directly
                        response = http.request('GET', image_url)
                        if response.status == 200:
                            # Add to zip with sequential naming
                            filename = f"image_{i+1:03d}.jpg"
                            zipf.writestr(filename, response.data)
                            print(f"Added image {i+1} from URL download")
                        else:
                            print(f"Failed to download image {image_url}: {response.status}")
                        
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
            
            print(f"Created training zip: {zip_key}")
            return zip_url
            
    except Exception as e:
        print(f"Error creating training data zip: {str(e)}")
        raise e

def update_character_with_lora_model(character_id, lora_info):
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

def update_character_training_status(character_id, status):
    """Update character training status in the main character record"""
    
    try:
        characters_table = dynamodb.Table(CHARACTERS_TABLE_NAME)
        
        characters_table.update_item(
            Key={'id': character_id},
            UpdateExpression="SET training_status = :status, updated_at = :updated",
            ExpressionAttributeValues={
                ':status': status,
                ':updated': datetime.now(timezone.utc).isoformat()
            }
        )
        
        print(f"Updated character {character_id} training status to {status}")
        
    except Exception as e:
        print(f"Error updating character training status: {str(e)}")

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

def create_destination_model(api_token, model_name, character_name):
    """Create a destination model on Replicate for training"""
    
    try:
        headers = {
            'Authorization': f'Token {api_token}',
            'Content-Type': 'application/json'
        }
        
        # Check if model already exists
        check_response = http.request(
            'GET',
            f'https://api.replicate.com/v1/models/jsilvia721/{model_name}',
            headers={'Authorization': f'Token {api_token}'}
        )
        
        if check_response.status == 200:
            print(f"Model jsilvia721/{model_name} already exists")
            return True
        
        # Create new model
        model_data = {
            'owner': 'jsilvia721',
            'name': model_name,
            'description': f'LoRA model for AI influencer character: {character_name}',
            'visibility': 'private',  # Keep models private
            'hardware': 'gpu-t4',  # Default hardware for training
        }
        
        print(f"Creating model: {model_name}")
        response = http.request(
            'POST',
            'https://api.replicate.com/v1/models',
            body=json.dumps(model_data),
            headers=headers
        )
        
        if response.status == 201:
            print(f"Successfully created model: jsilvia721/{model_name}")
            return True
        else:
            error_msg = response.data.decode('utf-8')
            print(f"Failed to create model: {response.status} - {error_msg}")
            return False
            
    except Exception as e:
        print(f"Error creating destination model: {str(e)}")
        return False

# Initialize tables on cold start
ensure_tables_exist()
