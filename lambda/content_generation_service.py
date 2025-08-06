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

def get_secret(secret_name, key=None):
    """Retrieve secret from AWS Secrets Manager"""
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        secret_string = response['SecretString']
        
        # If a key is specified, try to parse as JSON and extract the key
        if key:
            try:
                secret_data = json.loads(secret_string)
                return secret_data.get(key)
            except json.JSONDecodeError:
                print(f"Secret {secret_name} is not valid JSON, returning raw value")
                return secret_string
        
        return secret_string
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
        
        # Create job record using optimal schema v2.0
        job_id = str(uuid.uuid4())
        job = {
            'job_id': job_id,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'status': 'processing',
            
            # Job request data
            'job_type': 'image',
            'user_prompt': prompt,
            'character_id': character_id,
            'character_name': character.get('name', 'unknown'),
            'character_trigger_word': trigger_word,
            'lora_model_url': lora_model_url,
            
            # Additional metadata
            'retry_count': 0
        }
        
        # Save job to DynamoDB
        content_jobs_table = dynamodb.Table(CONTENT_JOBS_TABLE_NAME)
        content_jobs_table.put_item(Item=job)
        
        # Generate image using LoRA model on Replicate
        result = generate_image_with_lora(lora_model_url, trigger_word, prompt, job_id)
        
        if isinstance(result, dict) and result.get('success'):
            image_url = result.get('url')
            # Update job with result
            updates = {
                'status': 'completed',
                'output_url': image_url,
                'completed_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Add prediction ID if available
            if result.get('prediction_id'):
                updates['replicate_prediction_id'] = result.get('prediction_id')
            
            job.update(updates)
            content_jobs_table.put_item(Item=job)
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'job_id': job_id,
                    'status': 'completed',
                    'type': 'image',
                    'output_url': image_url,
                    'character_id': character_id,
                    'prompt': prompt
                }, default=decimal_default)
            }
        else:
            # Update job as failed with detailed error message
            error_message = result.get('error', 'Failed to generate image') if isinstance(result, dict) else 'Failed to generate image'
            job.update({
                'status': 'failed',
                'error': error_message,
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
        
        # Create job record
        job_id = str(uuid.uuid4())
        job = {
            'job_id': job_id,
            'character_id': character_id,
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
        
        # Generate video using Kling
        video_url = generate_video_with_kling(image_url, prompt)
        
        if video_url:
            # Update job with result
            job.update({
                'status': 'completed',
                'output_url': video_url,
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
                    'output_url': video_url,
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
    """Generate image using trained LoRA model on Replicate"""
    
    try:
        api_token = get_secret(REPLICATE_API_TOKEN_SECRET)
        if not api_token:
            print("Replicate API token not available")
            return {'success': False, 'error': 'Replicate API token not available'}
        
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
        
        response = http.request(
            'POST',
            f'https://api.replicate.com/v1/models/{model_path}/versions/{version_id}/predictions',
            body=json.dumps({'input': payload['input']}),  # Only send input when using model endpoint
            headers=headers
        )
        
        if response.status == 201:
            prediction_data = json.loads(response.data.decode('utf-8'))
            prediction_id = prediction_data['id']
            
            print(f"Started image generation with prediction ID: {prediction_id}")
            
            # Poll for completion (simple polling for now)
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
                            return {'success': True, 'url': output[0], 'prediction_id': prediction_id}
                        elif isinstance(output, str):
                            return {'success': True, 'url': output, 'prediction_id': prediction_id}
                    elif status_data['status'] == 'failed':
                        error_msg = status_data.get('error', 'Unknown error')
                        print(f"Image generation failed: {error_msg}")
                        return {'success': False, 'error': error_msg}
                
                time.sleep(2)
                wait_time += 2
            
            print("Image generation timed out")
            return {'success': False, 'error': 'Image generation timed out after 60 seconds'}
        else:
            error_msg = f"Failed to start image generation: HTTP {response.status}"
            if response.data:
                try:
                    error_data = json.loads(response.data.decode('utf-8'))
                    if 'detail' in error_data:
                        error_msg = error_data['detail']
                    elif 'error' in error_data:
                        error_msg = error_data['error']
                except:
                    pass
            print(error_msg)
            return {'success': False, 'error': error_msg}
            
    except Exception as e:
        error_msg = f"Error generating image with LoRA: {str(e)}"
        print(error_msg)
        return {'success': False, 'error': error_msg}

def generate_video_with_kling(image_url, prompt):
    """Generate video using Kling v2.1 via Replicate from an input image"""
    
    try:
        api_token = get_secret(REPLICATE_API_TOKEN_SECRET)
        if not api_token:
            print("Replicate API token not available")
            return None
        
        # Use Kling v2.1 model via Replicate for image-to-video generation
        payload = {
            'model': 'kwaivgi/kling-v2.1',  # Use latest version automatically
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
        if webhook_url:
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
            body=json.dumps({'input': payload['input']}),  # Only send input when using model endpoint
            headers=headers
        )
        
        if response.status == 201:
            prediction_data = json.loads(response.data.decode('utf-8'))
            prediction_id = prediction_data['id']
            
            print(f"Kling video generation started via Replicate, prediction_id: {prediction_id}")
            
            # Poll for completion (simple polling for now)
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
    """Get status of a content generation job"""
    
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
    """List content generation jobs with unified schema"""
    
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
        jobs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Transform jobs to have consistent format for frontend (optimal schema v2.0)
        transformed_jobs = []
        for job in jobs:
            # Map from optimal schema v2.0 to frontend format with fallbacks
            transformed_job = {
                'job_id': job.get('job_id'),
                'character_id': job.get('character_id'),
                'character_name': job.get('character_name', 'Unknown'),
                'type': job.get('job_type') or job.get('type'),  # New schema uses job_type, fallback to legacy
                'status': job.get('status'),
                'prompt': job.get('user_prompt') or job.get('prompt', ''),  # New schema uses user_prompt, fallback to legacy
                'created_at': job.get('created_at'),
                'updated_at': job.get('updated_at')
            }
            
            # Add completion timestamp if available
            if job.get('completed_at'):
                transformed_job['completed_at'] = job['completed_at']
            
            # Handle result URLs from optimal schema v2.0
            if job.get('primary_result_url'):
                transformed_job['result_url'] = job['primary_result_url']
                transformed_job['output_url'] = job['primary_result_url']  # Backward compatibility
                
                # Map to specific URL types based on job type
                job_type = job.get('job_type', job.get('type', ''))
                if job_type == 'video':
                    transformed_job['video_url'] = job['primary_result_url']
                elif job_type == 'image':
                    transformed_job['image_url'] = job['primary_result_url']
            
            # Include all result URLs if available
            if job.get('result_urls'):
                transformed_job['result_urls'] = job['result_urls']
            
            # Handle legacy output_url field for backward compatibility
            elif job.get('output_url'):
                transformed_job['result_url'] = job['output_url']
                transformed_job['output_url'] = job['output_url']
                
                job_type = job.get('job_type', job.get('type', ''))
                if job_type == 'video':
                    transformed_job['video_url'] = job['output_url']
                elif job_type == 'image':
                    transformed_job['image_url'] = job['output_url']
            
            # Add error information if present (optimal schema v2.0 uses error_message)
            if job.get('error_message'):
                transformed_job['error'] = job['error_message']
                
                # Include error details if available
                if job.get('error_details'):
                    error_details = job['error_details']
                    if isinstance(error_details, dict):
                        transformed_job['error_category'] = error_details.get('category', 'unknown')
                        transformed_job['error_component'] = error_details.get('component')
            
            # Backward compatibility: check legacy error field as well
            elif job.get('error'):
                transformed_job['error'] = job['error']
            
            # Add Replicate information if available
            if job.get('replicate_prediction_id'):
                transformed_job['replicate_prediction_id'] = job['replicate_prediction_id']
            
            if job.get('replicate_status'):
                transformed_job['replicate_status'] = job['replicate_status']
            
            # Add input image URL for video jobs
            if job.get('input_image_url'):
                transformed_job['input_image_url'] = job['input_image_url']
            
            # Add LoRA model info for image jobs
            if job.get('lora_model_url'):
                transformed_job['lora_model_url'] = job['lora_model_url']
            if job.get('trigger_word'):
                transformed_job['trigger_word'] = job['trigger_word']
            
            transformed_jobs.append(transformed_job)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'jobs': transformed_jobs,
                'count': len(transformed_jobs)
            }, default=decimal_default)
        }
        
    except Exception as e:
        print(f"Error listing jobs: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': f'Failed to list content jobs: {str(e)}'})
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

# Initialize tables on cold start
ensure_tables_exist()
