"""
Content Generation Service Lambda Function

This service orchestrates the creation of consistent character content by:
1. Using LoRA models to generate consistent character images
2. Using Kling AI to create videos from those images
3. Providing a unified API for content creation
"""

import json
import boto3
import os
import uuid
import urllib3
import base64
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
CONTENT_JOBS_TABLE_NAME = os.environ.get('CONTENT_JOBS_TABLE_NAME', 'ai-influencer-content-jobs')
REPLICATE_API_TOKEN_SECRET = os.environ.get('REPLICATE_API_TOKEN_SECRET', 'replicate-api-token')
KLING_API_TOKEN_SECRET = os.environ.get('KLING_API_TOKEN_SECRET', 'kling-api-token')

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

def lambda_handler(event, context):
    """Main Lambda handler for content generation"""
    
    try:
        # Parse the event
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', event)
        
        action = body.get('action', 'generate')
        
        if action == 'generate_image':
            return handle_generate_image(body, context)
        elif action == 'generate_video':
            return handle_generate_video(body, context)
        elif action == 'generate_complete_content':
            return handle_generate_complete_content(body, context)
        elif action == 'status':
            return handle_get_status(body, context)
        elif action == 'list':
            return handle_list_jobs(body, context)
        elif action == 'sync':
            return handle_sync_replicate(body, context)
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

def handle_generate_image(body, context):
    """Generate a consistent character image using LoRA model"""
    
    try:
        # Required parameters
        character_id = body.get('character_id')
        prompt = body.get('prompt', '')
        
        if not character_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'character_id is required'})
            }
        
        # Get character details and LoRA model info
        characters_table = dynamodb.Table(CHARACTERS_TABLE_NAME)
        character_response = characters_table.get_item(Key={'id': character_id})
        
        if 'Item' not in character_response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Character not found'})
            }
        
        character = character_response['Item']
        lora_model_url = character.get('lora_model_url')
        trigger_word = character.get('trigger_word')
        
        if not lora_model_url or not trigger_word:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Character LoRA model not trained yet. Please complete training first.'})
            }
        
        # Create job record
        job_id = str(uuid.uuid4())
        job = {
            'job_id': job_id,
            'character_id': character_id,
            'character_name': character.get('name', 'unknown'),
            'type': 'image',
            'status': 'generating',
            'prompt': prompt,
            'trigger_word': trigger_word,
            'lora_model_url': lora_model_url,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        # Save job to DynamoDB
        content_jobs_table = dynamodb.Table(CONTENT_JOBS_TABLE_NAME)
        content_jobs_table.put_item(Item=job)
        
        # Generate image using LoRA model on Replicate
        result = generate_image_with_lora(lora_model_url, trigger_word, prompt, job_id)
        
        # Check if webhook is configured for async processing
        webhook_url = os.environ.get('REPLICATE_WEBHOOK_URL')
        
        if result and isinstance(result, dict) and result.get('prediction_id') and webhook_url:
            # Async processing with webhooks
            job.update({
                'status': 'processing',
                'replicate_prediction_id': result['prediction_id'],
                'updated_at': datetime.now(timezone.utc).isoformat()
            })
            content_jobs_table.put_item(Item=job)
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'job_id': job_id,
                    'status': 'processing',
                    'type': 'image',
                    'character_id': character_id,
                    'prompt': prompt,
                    'message': 'Image generation started, check status for updates'
                }, default=decimal_default)
            }
        elif result and isinstance(result, str):
            # Synchronous result (backward compatibility)
            job.update({
                'status': 'completed',
                'output_url': result,
                'completed_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            })
            content_jobs_table.put_item(Item=job)
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'job_id': job_id,
                    'status': 'completed',
                    'type': 'image',
                    'output_url': result,
                    'character_id': character_id,
                    'prompt': prompt
                }, default=decimal_default)
            }
        else:
            # Update job as failed
            job.update({
                'status': 'failed',
                'error': 'Failed to generate image',
                'updated_at': datetime.now(timezone.utc).isoformat()
            })
            content_jobs_table.put_item(Item=job)
            
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Failed to generate image'})
            }
            
    except Exception as e:
        print(f"Error in handle_generate_image: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f'Image generation failed: {str(e)}'})
        }

def handle_generate_video(body, context):
    """Generate video from an existing image using Kling"""
    
    try:
        # Required parameters
        image_url = body.get('image_url')
        prompt = body.get('prompt', '')
        character_id = body.get('character_id')
        
        if not image_url:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'image_url is required'})
            }
        
        # Get character info if provided
        character_name = 'unknown'
        if character_id:
            try:
                characters_table = dynamodb.Table(CHARACTERS_TABLE_NAME)
                character_response = characters_table.get_item(Key={'id': character_id})
                if 'Item' in character_response:
                    character_name = character_response['Item'].get('name', 'unknown')
            except Exception:
                pass  # Continue with unknown character name
        
        # Create job record
        job_id = str(uuid.uuid4())
        job = {
            'job_id': job_id,
            'character_id': character_id,
            'character_name': character_name,
            'type': 'video',
            'status': 'generating',
            'prompt': prompt,
            'input_image_url': image_url,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        # Save job to DynamoDB
        content_jobs_table = dynamodb.Table(CONTENT_JOBS_TABLE_NAME)
        content_jobs_table.put_item(Item=job)
        
        # Generate video using Kling with webhook support
        result = generate_video_with_kling(image_url, prompt, job_id)
        
        # Check if webhook is configured for async processing
        webhook_url = os.environ.get('REPLICATE_WEBHOOK_URL')
        
        if result and isinstance(result, dict) and result.get('prediction_id') and webhook_url:
            # Async processing with webhooks
            job.update({
                'status': 'processing',
                'replicate_prediction_id': result['prediction_id'],
                'updated_at': datetime.now(timezone.utc).isoformat()
            })
            content_jobs_table.put_item(Item=job)
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'job_id': job_id,
                    'status': 'processing',
                    'type': 'video',
                    'character_id': character_id,
                    'input_image_url': image_url,
                    'prompt': prompt,
                    'message': 'Video generation started, check status for updates'
                }, default=decimal_default)
            }
        elif result and isinstance(result, str):
            # Synchronous result (backward compatibility)
            job.update({
                'status': 'completed',
                'output_url': result,
                'completed_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            })
            content_jobs_table.put_item(Item=job)
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'job_id': job_id,
                    'status': 'completed',
                    'type': 'video',
                    'output_url': result,
                    'input_image_url': image_url,
                    'prompt': prompt
                }, default=decimal_default)
            }
        else:
            # Update job as failed
            job.update({
                'status': 'failed',
                'error': 'Failed to generate video',
                'updated_at': datetime.now(timezone.utc).isoformat()
            })
            content_jobs_table.put_item(Item=job)
            
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Failed to generate video'})
            }
            
    except Exception as e:
        print(f"Error in handle_generate_video: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f'Video generation failed: {str(e)}'})
        }

def handle_generate_complete_content(body, context):
    """Generate both image and video in sequence (LoRA → Kling pipeline)"""
    
    try:
        # Required parameters
        character_id = body.get('character_id')
        prompt = body.get('prompt', '')
        
        if not character_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'character_id is required'})
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
        lora_model_url = character.get('lora_model_url')
        trigger_word = character.get('trigger_word')
        
        if not lora_model_url or not trigger_word:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Character LoRA model not trained yet. Please complete training first.'})
            }
        
        # Create job record
        job_id = str(uuid.uuid4())
        job = {
            'job_id': job_id,
            'character_id': character_id,
            'character_name': character.get('name', 'unknown'),
            'type': 'complete',
            'status': 'generating_image',
            'prompt': prompt,
            'trigger_word': trigger_word,
            'lora_model_url': lora_model_url,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        # Save job to DynamoDB
        content_jobs_table = dynamodb.Table(CONTENT_JOBS_TABLE_NAME)
        content_jobs_table.put_item(Item=job)
        
        # Step 1: Generate image using LoRA
        print(f"Generating image for job {job_id} with LoRA model")
        image_url = generate_image_with_lora(lora_model_url, trigger_word, prompt)
        
        if not image_url:
            job.update({
                'status': 'failed',
                'error': 'Failed to generate image with LoRA',
                'updated_at': datetime.now(timezone.utc).isoformat()
            })
            content_jobs_table.put_item(Item=job)
            
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Failed to generate image with LoRA'})
            }
        
        # Update job with image result
        job.update({
            'status': 'generating_video',
            'image_url': image_url,
            'updated_at': datetime.now(timezone.utc).isoformat()
        })
        content_jobs_table.put_item(Item=job)
        
        # Step 2: Generate video using Kling
        print(f"Generating video for job {job_id} with Kling using image: {image_url}")
        video_url = generate_video_with_kling(image_url, prompt)
        
        if video_url:
            # Update job with final result
            job.update({
                'status': 'completed',
                'video_url': video_url,
                'completed_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            })
            content_jobs_table.put_item(Item=job)
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'job_id': job_id,
                    'status': 'completed',
                    'type': 'complete',
                    'character_id': character_id,
                    'prompt': prompt,
                    'image_url': image_url,
                    'video_url': video_url,
                    'message': 'Generated both consistent character image and video successfully'
                }, default=decimal_default)
            }
        else:
            # Update job as failed at video step
            job.update({
                'status': 'failed',
                'error': 'Failed to generate video with Kling',
                'updated_at': datetime.now(timezone.utc).isoformat()
            })
            content_jobs_table.put_item(Item=job)
            
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Failed to generate video with Kling',
                    'image_url': image_url,  # Still return the image that was generated
                    'message': 'Image generation succeeded but video generation failed'
                })
            }
            
    except Exception as e:
        print(f"Error in handle_generate_complete_content: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f'Complete content generation failed: {str(e)}'})
        }

def generate_image_with_lora(lora_model_url, trigger_word, prompt, job_id=None):
    """Generate image using trained LoRA model on Replicate with webhook support"""
    
    try:
        print(f"Attempting to retrieve secret: {REPLICATE_API_TOKEN_SECRET}")
        api_token = get_secret(REPLICATE_API_TOKEN_SECRET)
        print(f"API token retrieved: {'YES' if api_token else 'NO'}")
        if api_token:
            print(f"Token prefix: {api_token[:10]}...")
        
        if not api_token:
            print("Replicate API token not available")
            return None
        
        # Build prompt with trigger word
        full_prompt = f"{trigger_word}, {prompt}" if prompt else trigger_word
        
        # Use the trained LoRA model directly via Replicate
        # The lora_model_url should be in format: jsilvia721/model-name:version
        payload = {
            'input': {
                'prompt': full_prompt,
                'num_outputs': 1,
                'aspect_ratio': '9:16',  # Good for social media
                'output_format': 'jpg',
                'guidance_scale': 3.5,
                'num_inference_steps': 28
            }
        }
        
        # Add webhook for real-time updates if configured
        webhook_url = os.environ.get('REPLICATE_WEBHOOK_URL')
        if webhook_url and job_id:
            payload['webhook'] = f"{webhook_url}?job_id={job_id}&type=image"
            payload['webhook_events_filter'] = ['start', 'completed']
        
        # Extract model path from lora_model_url (format: owner/model:version)
        if ':' in lora_model_url:
            model_path = lora_model_url.split(':')[0]  # Get owner/model part
        else:
            # Fallback if no version specified
            model_path = lora_model_url
        
        headers = {
            'Authorization': f'Token {api_token}',
            'Content-Type': 'application/json'
        }
        
        # Use version-specific endpoint for trained models
        version_id = lora_model_url.split(':')[1] if ':' in lora_model_url else lora_model_url
        
        api_url = f'https://api.replicate.com/v1/models/{model_path}/versions/{version_id}/predictions'
        print(f"Making API request to: {api_url}")
        print(f"Headers: Authorization=Token {api_token[:10]}..., Content-Type={headers['Content-Type']}")
        
        response = http.request(
            'POST',
            api_url,
            body=json.dumps(payload),
            headers=headers
        )
        
        print(f"API response status: {response.status}")
        if response.status != 201:
            error_body = response.data.decode('utf-8') if response.data else 'No response body'
            print(f"API error response: {error_body}")
        
        if response.status == 201:
            prediction_data = json.loads(response.data.decode('utf-8'))
            prediction_id = prediction_data['id']
            
            # Update job with replicate prediction ID for webhook tracking
            if job_id:
                content_jobs_table = dynamodb.Table(CONTENT_JOBS_TABLE_NAME)
                content_jobs_table.update_item(
                    Key={'job_id': job_id},
                    UpdateExpression="SET replicate_prediction_id = :pred_id, updated_at = :updated",
                    ExpressionAttributeValues={
                        ':pred_id': prediction_id,
                        ':updated': datetime.now(timezone.utc).isoformat()
                    }
                )
            
            # If webhook configured, return job started successfully
            if webhook_url and job_id:
                return {'prediction_id': prediction_id, 'status': 'started'}
            
            # Otherwise fall back to polling (for backwards compatibility)
            import time
            max_wait = 60  # Maximum 60 seconds
            wait_time = 0
            
            while wait_time < max_wait:
                status_response = http.request(
                    'GET',
                    f'https://api.replicate.com/v1/predictions/{prediction_id}',
                    headers={'Authorization': f'Token {api_token}'}
                )
                
                if status_response.status == 200:
                    status_data = json.loads(status_response.data.decode('utf-8'))
                    
                    if status_data['status'] == 'succeeded':
                        output = status_data.get('output')
                        if output and isinstance(output, list) and len(output) > 0:
                            return output[0]  # Return first image URL
                        elif isinstance(output, str):
                            return output
                    elif status_data['status'] == 'failed':
                        print(f"Image generation failed: {status_data.get('error')}")
                        return None
                
                time.sleep(2)
                wait_time += 2
            
            print("Image generation timed out")
            return None
        else:
            print(f"Failed to start image generation: {response.status}")
            return None
            
    except Exception as e:
        print(f"Error generating image with LoRA: {str(e)}")
        return None

def generate_video_with_kling(image_url, prompt, job_id=None):
    """Generate video using Kling v2.1 via Replicate from an input image with webhook support"""
    
    try:
        api_token = get_secret(REPLICATE_API_TOKEN_SECRET)
        if not api_token:
            print("Replicate API token not available")
            return None
        
        # Use Kling v2.1 model via Replicate for image-to-video generation
        payload = {
            'input': {
                'start_image': image_url,  # Required first frame
                'prompt': prompt,
                'duration': 5,  # 5 seconds
                'mode': 'standard',  # 720p resolution, 24fps
                'negative_prompt': 'blurry, low quality, distorted, unnatural movement'
            }
        }
        
        # Add webhook for real-time updates if configured
        webhook_url = os.environ.get('REPLICATE_WEBHOOK_URL')
        if webhook_url and job_id:
            payload['webhook'] = f"{webhook_url}?job_id={job_id}&type=video"
            payload['webhook_events_filter'] = ['start', 'completed']
        elif webhook_url:
            payload['webhook'] = webhook_url
            payload['webhook_events_filter'] = ['start', 'completed']
        
        headers = {
            'Authorization': f'Token {api_token}',
            'Content-Type': 'application/json'
        }
        
        print(f"Starting Kling video generation via Replicate with image: {image_url}")
        
        response = http.request(
            'POST',
            'https://api.replicate.com/v1/models/kwaivgi/kling-v2.1/predictions',
            body=json.dumps(payload),
            headers=headers
        )
        
        if response.status == 201:
            prediction_data = json.loads(response.data.decode('utf-8'))
            prediction_id = prediction_data['id']
            
            print(f"Kling video generation started via Replicate, prediction_id: {prediction_id}")
            
            # Update job with replicate prediction ID for webhook tracking
            if job_id:
                content_jobs_table = dynamodb.Table(CONTENT_JOBS_TABLE_NAME)
                content_jobs_table.update_item(
                    Key={'job_id': job_id},
                    UpdateExpression="SET replicate_prediction_id = :pred_id, updated_at = :updated",
                    ExpressionAttributeValues={
                        ':pred_id': prediction_id,
                        ':updated': datetime.now(timezone.utc).isoformat()
                    }
                )
            
            # If webhook configured, return job started successfully
            if webhook_url and job_id:
                return {'prediction_id': prediction_id, 'status': 'started'}
            
            # Otherwise fall back to polling (for backwards compatibility)
            import time
            max_wait = 300  # Maximum 5 minutes for video generation 
            wait_time = 0
            
            while wait_time < max_wait:
                status_response = http.request(
                    'GET',
                    f'https://api.replicate.com/v1/predictions/{prediction_id}',
                    headers={'Authorization': f'Token {api_token}'}
                )
                
                if status_response.status == 200:
                    status_data = json.loads(status_response.data.decode('utf-8'))
                    status = status_data.get('status')
                    
                    if status == 'succeeded':
                        output = status_data.get('output')
                        if output:
                            # Handle different output formats
                            if isinstance(output, list) and len(output) > 0:
                                video_url = output[0]
                            elif isinstance(output, str):
                                video_url = output
                            else:
                                video_url = output
                            
                            print(f"Kling video generation completed: {video_url}")
                            return video_url
                        else:
                            print("Video generation succeeded but no output URL")
                            return None
                            
                    elif status == 'failed':
                        error_msg = status_data.get('error', 'Unknown error')
                        print(f"Kling video generation failed: {error_msg}")
                        return None
                    
                    elif status in ['starting', 'processing']:
                        print(f"Kling video generation in progress: {status}")
                        # Continue polling
                    else:
                        print(f"Unknown status: {status}")
                
                time.sleep(10)  # Wait 10 seconds between polls
                wait_time += 10
            
            print("Kling video generation timed out")
            return None
            
        else:
            error_msg = response.data.decode('utf-8') if response.data else 'Unknown error'
            print(f"Failed to start Kling video generation: {response.status} - {error_msg}")
            return None
            
    except Exception as e:
        print(f"Error generating video with Kling via Replicate: {str(e)}")
        return None

def handle_get_status(body, context):
    """Get status of a content generation job and expire if stale"""
    
    try:
        job_id = body.get('job_id')
        if not job_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'job_id is required'})
            }
        
        content_jobs_table = dynamodb.Table(CONTENT_JOBS_TABLE_NAME)
        job_response = content_jobs_table.get_item(Key={'job_id': job_id})
        
        if 'Item' not in job_response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Job not found'})
            }
        
        job = job_response['Item']
        
        # Check if job is stale and expire it
        if job.get('status') == 'processing':
            current_time = datetime.now(timezone.utc)
            
            # Check if job has no replicate_prediction_id (never submitted to Replicate)
            if not job.get('replicate_prediction_id'):
                created_at = datetime.fromisoformat(job['created_at'].replace('Z', '+00:00'))
                age_seconds = (current_time - created_at).total_seconds()
                
                if age_seconds > 5 * 60:  # 5 minutes
                    # Job failed to submit to Replicate - mark as failed
                    job['status'] = 'failed'
                    job['error'] = 'Job failed to submit to Replicate API'
                    job['error_category'] = 'submission_failure'
                    job['error_component'] = 'replicate_api'
                    job['updated_at'] = current_time.isoformat()
                    content_jobs_table.put_item(Item=job)
                    print(f"Expired job {job_id}: Failed to submit to Replicate")
                    
            else:
                # Job has replicate_prediction_id but still processing for too long
                created_at = datetime.fromisoformat(job['created_at'].replace('Z', '+00:00'))
                age_seconds = (current_time - created_at).total_seconds()
                
                if age_seconds > 15 * 60:  # 15 minutes
                    # Mark as timed out
                    job['status'] = 'failed'
                    job['error'] = 'Job timed out after 15 minutes of processing'
                    job['error_category'] = 'timeout'
                    job['error_component'] = 'processing'
                    job['updated_at'] = current_time.isoformat()
                    content_jobs_table.put_item(Item=job)
                    print(f"Expired stale job {job_id}: Processing timeout")
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(job, default=decimal_default)
        }
        
    except Exception as e:
        print(f"Error getting job status: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f'Failed to get job status: {str(e)}'})
        }

def handle_list_jobs(body, context):
    """List content generation jobs and expire stale processing jobs"""
    
    try:
        character_id = body.get('character_id')  # Optional filter
        
        content_jobs_table = dynamodb.Table(CONTENT_JOBS_TABLE_NAME)
        
        if character_id:
            response = content_jobs_table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('character_id').eq(character_id)
            )
        else:
            response = content_jobs_table.scan()
        
        jobs = response.get('Items', [])
        
        # Check for stale processing jobs and expire them
        current_time = datetime.now(timezone.utc)
        stale_job_threshold = 15 * 60  # 15 minutes in seconds
        expired_jobs = []
        
        for job in jobs:
            if job.get('status') == 'processing':
                # Check if job has no replicate_prediction_id (never submitted to Replicate)
                if not job.get('replicate_prediction_id'):
                    # Check if job is older than 5 minutes (failed to submit to Replicate)
                    created_at = datetime.fromisoformat(job['created_at'].replace('Z', '+00:00'))
                    age_seconds = (current_time - created_at).total_seconds()
                    
                    if age_seconds > 5 * 60:  # 5 minutes
                        # Job failed to submit to Replicate - mark as failed
                        job['status'] = 'failed'
                        job['error'] = 'Job failed to submit to Replicate API'
                        job['error_category'] = 'submission_failure'
                        job['error_component'] = 'replicate_api'
                        job['updated_at'] = current_time.isoformat()
                        expired_jobs.append(job)
                        
                else:
                    # Job has replicate_prediction_id but still processing
                    # Check if it's been processing too long (stale)
                    created_at = datetime.fromisoformat(job['created_at'].replace('Z', '+00:00'))
                    age_seconds = (current_time - created_at).total_seconds()
                    
                    if age_seconds > stale_job_threshold:  # 15 minutes
                        # Mark as timed out
                        job['status'] = 'failed'
                        job['error'] = 'Job timed out after 15 minutes of processing'
                        job['error_category'] = 'timeout'
                        job['error_component'] = 'processing'
                        job['updated_at'] = current_time.isoformat()
                        expired_jobs.append(job)
        
        # Update expired jobs in DynamoDB
        for expired_job in expired_jobs:
            content_jobs_table.put_item(Item=expired_job)
            print(f"Expired stale job {expired_job['job_id']}: {expired_job['error']}")
        
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
        print(f"Error listing jobs: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f'Failed to list jobs: {str(e)}'})
        }

# Ensure DynamoDB tables exist
def ensure_tables_exist():
    """Create DynamoDB tables if they don't exist"""
    
    try:
        # Content jobs table
        content_jobs_table = dynamodb.Table(CONTENT_JOBS_TABLE_NAME)
        content_jobs_table.load()
    except:
        # Create content jobs table
        dynamodb.create_table(
            TableName=CONTENT_JOBS_TABLE_NAME,
            KeySchema=[
                {'AttributeName': 'job_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'job_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        print(f"Created table: {CONTENT_JOBS_TABLE_NAME}")

def handle_sync_replicate(body, context):
    """Handle sync with Replicate - expire stale jobs and check Replicate status for processing jobs"""
    
    try:
        content_jobs_table = dynamodb.Table(CONTENT_JOBS_TABLE_NAME)
        
        # Get all jobs
        response = content_jobs_table.scan()
        jobs = response.get('Items', [])
        
        # Check for stale processing jobs and expire them
        current_time = datetime.now(timezone.utc)
        stale_job_threshold = 15 * 60  # 15 minutes in seconds
        expired_jobs = []
        synced_jobs = []
        
        # Get Replicate API token
        api_token = get_secret(REPLICATE_API_TOKEN_SECRET)
        if not api_token:
            print("Replicate API token not available for sync")
            # Still expire stale jobs even without API access
        
        for job in jobs:
            if job.get('status') == 'processing':
                # Check if job has no replicate_prediction_id (never submitted to Replicate)
                if not job.get('replicate_prediction_id'):
                    # Check if job is older than 5 minutes (failed to submit to Replicate)
                    created_at = datetime.fromisoformat(job['created_at'].replace('Z', '+00:00'))
                    age_seconds = (current_time - created_at).total_seconds()
                    
                    if age_seconds > 5 * 60:  # 5 minutes
                        # Job failed to submit to Replicate - mark as failed
                        job['status'] = 'failed'
                        job['error'] = 'Job failed to submit to Replicate API'
                        job['error_category'] = 'submission_failure'
                        job['error_component'] = 'replicate_api'
                        job['updated_at'] = current_time.isoformat()
                        expired_jobs.append(job)
                        
                else:
                    # Job has replicate_prediction_id - check status with Replicate
                    created_at = datetime.fromisoformat(job['created_at'].replace('Z', '+00:00'))
                    age_seconds = (current_time - created_at).total_seconds()
                    
                    if age_seconds > stale_job_threshold:  # 15 minutes
                        # Mark as timed out
                        job['status'] = 'failed'
                        job['error'] = 'Job timed out after 15 minutes of processing'
                        job['error_category'] = 'timeout'
                        job['error_component'] = 'processing'
                        job['updated_at'] = current_time.isoformat()
                        expired_jobs.append(job)
                        
                    elif api_token:
                        # Check status with Replicate API
                        try:
                            status_response = http.request(
                                'GET',
                                f'https://api.replicate.com/v1/predictions/{job["replicate_prediction_id"]}',
                                headers={'Authorization': f'Token {api_token}'}
                            )
                            
                            if status_response.status == 200:
                                status_data = json.loads(status_response.data.decode('utf-8'))
                                replicate_status = status_data.get('status')
                                
                                if replicate_status == 'succeeded':
                                    # Update job as completed
                                    output = status_data.get('output')
                                    if output:
                                        if isinstance(output, list) and len(output) > 0:
                                            result_url = output[0]
                                        elif isinstance(output, str):
                                            result_url = output
                                        else:
                                            result_url = str(output)
                                        
                                        job['status'] = 'completed'
                                        job['output_url'] = result_url
                                        job['completed_at'] = current_time.isoformat()
                                        job['updated_at'] = current_time.isoformat()
                                        synced_jobs.append(job)
                                        
                                elif replicate_status == 'failed':
                                    # Update job as failed
                                    error_msg = status_data.get('error', 'Replicate processing failed')
                                    job['status'] = 'failed'
                                    job['error'] = error_msg
                                    job['error_category'] = 'processing_failure'
                                    job['error_component'] = 'replicate'
                                    job['updated_at'] = current_time.isoformat()
                                    synced_jobs.append(job)
                                    
                                # If still processing, leave as is
                                
                        except Exception as e:
                            print(f"Error checking Replicate status for job {job['job_id']}: {str(e)}")
                            continue
        
        # Update all changed jobs in DynamoDB
        total_updated = 0
        for job in expired_jobs + synced_jobs:
            content_jobs_table.put_item(Item=job)
            total_updated += 1
            print(f"Updated job {job['job_id']}: {job['status']}")
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'message': 'Sync completed successfully',
                'synced_count': total_updated,
                'expired_count': len(expired_jobs),
                'updated_from_replicate': len(synced_jobs)
            }, default=decimal_default)
        }
        
    except Exception as e:
        print(f"Error in sync operation: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f'Sync failed: {str(e)}'})
        }

# Initialize tables on cold start
ensure_tables_exist()
