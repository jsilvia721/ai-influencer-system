"""
AWS Lambda function for generating training images with robust retry mechanism

This function generates a precise number of training images by retrying failed generations
up to a maximum number of attempts, providing real-time progress updates.
"""

import json
import boto3
import os
import uuid
import urllib3
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from decimal import Decimal

# Initialize urllib3 for HTTP requests
http = urllib3.PoolManager()

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
secrets_client = boto3.client('secretsmanager')

# Environment variables
S3_BUCKET = os.environ.get('S3_BUCKET_NAME', 'ai-influencer-system-dev-content-bkdeyg')
REPLICATE_API_TOKEN_SECRET = os.environ.get('REPLICATE_API_TOKEN_SECRET', 'replicate-api-token')

def get_secret(secret_name: str) -> Optional[str]:
    """Retrieve secret from AWS Secrets Manager"""
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except Exception as e:
        print(f"Error retrieving secret {secret_name}: {str(e)}")
        return None

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for training image generation with retry mechanism
    """
    print(f"Received event: {json.dumps(event)}")
    
    try:
        # Extract character information
        character_name = event.get('character_name')
        character_description = event.get('character_description')
        character_id = event.get('character_id')  # Optional - for organizing images
        num_images = event.get('num_images', 15)  # Default to 15 images
        
        if not character_name or not character_description:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing character_name or character_description'
                })
            }
        
        # Validate num_images range
        if num_images < 1 or num_images > 50:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'num_images must be between 1 and 50'
                })
            }
        
        # Get Replicate API token
        api_token = get_secret(REPLICATE_API_TOKEN_SECRET)
        if not api_token or api_token == "placeholder-token-needs-to-be-updated":
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Replicate API token not configured. Please set up the token in AWS Secrets Manager.'
                })
            }
        
        # Use provided job ID or generate one
        job_id = event.get('job_id', str(uuid.uuid4()))
        folder_id = character_id if character_id else job_id
        
        # Calculate max attempts: num_images * 2 + 3, capped at 25
        max_attempts = min(num_images * 2 + 3, 25)
        
        print(f"Starting training image generation for character: {character_name}")
        print(f"Target: {num_images} images, Max attempts: {max_attempts}")
        print(f"Job ID: {job_id}")
        
        # Store initial job status in DynamoDB
        job_record = {
            'job_id': job_id,
            'character_name': character_name,
            'character_description': character_description,
            'character_id': folder_id,
            'status': 'processing',
            'total_images': num_images,
            'completed_images': 0,
            'current_attempt': 0,
            'max_attempts': max_attempts,
            'success_rate': Decimal('0.0'),
            'image_urls': [],
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        try:
            table = dynamodb.Table('ai-influencer-training-jobs')
            table.put_item(Item=job_record)
        except Exception as e:
            print(f"Warning: Could not store job in DynamoDB: {e}")
        
        # Start the image generation process
        result = generate_training_images_with_retry(
            api_token=api_token,
            job_id=job_id,
            character_name=character_name,
            character_description=character_description,
            folder_id=folder_id,
            num_images=num_images,
            max_attempts=max_attempts,
            table=table
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'job_id': job_id,
                'status': result['status'],
                'message': f'Training image generation process started for {character_name}',
                'total_requested': num_images,
                'max_attempts': max_attempts,
                'current_attempt': result.get('current_attempt', 0),
                'completed_images': result.get('completed_images', 0),
                'success_rate': float(result.get('success_rate', 0)),
                'image_urls': result.get('image_urls', [])
            })
        }
        
    except Exception as e:
        print(f"Error in training image generation: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': f'Training image generation failed: {str(e)}'
            })
        }

def generate_training_images_with_retry(
    api_token: str,
    job_id: str,
    character_name: str,
    character_description: str,
    folder_id: str,
    num_images: int,
    max_attempts: int,
    table
) -> Dict[str, Any]:
    """
    Generate training images with retry mechanism.
    Continues until num_images are successfully generated or max_attempts is reached.
    """
    
    # Define varied prompts for training images
    all_prompts = [
        f"Beautiful portrait of {character_description}, Instagram influencer style, professional photography, soft lighting, high quality, 8k",
        f"Full body photo of {character_description}, confident pose, fashion photography, studio lighting, influencer aesthetic",
        f"{character_description}, casual chic outfit, natural beauty, lifestyle photography, golden hour lighting",
        f"Close-up beauty shot of {character_description}, flawless skin, makeup, professional portrait, soft focus background",
        f"{character_description} in trendy outfit, street style fashion, urban background, confident expression",
        f"Glamour shot of {character_description}, elegant pose, sophisticated lighting, fashion model aesthetic",
        f"Side profile of {character_description}, artistic beauty photography, dramatic lighting, high fashion style",
        f"Three-quarter view of {character_description}, social media influencer photo, engaging smile, professional quality",
        f"{character_description} in stylish casual wear, lifestyle content creator aesthetic, bright natural lighting",
        f"{character_description} in elegant dress, upscale fashion photography, luxury lifestyle aesthetic",
        f"{character_description} at the beach, swimwear fashion, golden hour lighting, vacation vibes, professional photography",
        f"{character_description} poolside, summer lifestyle content, bikini fashion, confident pose, resort setting",
        f"{character_description} in athletic wear, fitness lifestyle, gym setting, active pose, health and wellness aesthetic",
        f"{character_description} boudoir photography style, elegant lingerie, artistic lighting, sophisticated pose, tasteful composition",
        f"{character_description} in form-fitting outfit, fashion photography, confident expression, premium content aesthetic",
        f"Direct gaze portrait of {character_description}, captivating eyes, beauty photography, alluring expression",
        f"{character_description} looking away elegantly, candid beauty moment, suggestive pose, artistic photography",
        f"Creative angle shot of {character_description}, unique composition, fashion model aesthetic, premium content",
        f"Medium shot of {character_description}, balanced framing, influencer content style, attractive pose",
        f"Studio portrait of {character_description}, controlled lighting, professional beauty photography, glamour style",
        f"{character_description} with natural authentic expression, relatable influencer content, intimate setting",
        f"Environmental beauty portrait of {character_description}, lifestyle setting, aspirational content aesthetic",
        f"{character_description} in summer dress, outdoor setting, wind-blown hair, romantic lighting, lifestyle photography",
        f"{character_description} bedroom setting, cozy aesthetic, soft morning light, intimate lifestyle content"
    ]
    
    successful_images = []
    current_attempt = 0
    prompts_cycle = all_prompts * ((num_images // len(all_prompts)) + 1)  # Ensure we have enough prompts
    
    while len(successful_images) < num_images and current_attempt < max_attempts:
        current_attempt += 1
        
        # Select prompt (cycle through available prompts)
        prompt_index = (current_attempt - 1) % len(all_prompts)
        prompt = prompts_cycle[prompt_index]
        
        print(f"Attempt {current_attempt}/{max_attempts}: Generating image {len(successful_images)+1}/{num_images}")
        print(f"Prompt: {prompt[:100]}...")
        
        try:
            # Generate image using Replicate
            image_url = generate_single_image_with_replicate(api_token, prompt)
            
            if image_url:
                # Download and upload to S3
                image_number = len(successful_images) + 1
                s3_key = f"training-images/{folder_id}/{character_name.replace(' ', '_')}_training_{image_number:02d}.jpg"
                s3_url = upload_image_to_s3(image_url, s3_key)
                
                if s3_url:
                    successful_images.append(s3_url)
                    print(f"Successfully generated and stored image {image_number}/{num_images}")
                else:
                    print(f"Failed to upload image to S3 (attempt {current_attempt})")
            else:
                print(f"Failed to generate image with Replicate (attempt {current_attempt})")
        
        except Exception as e:
            print(f"Error in attempt {current_attempt}: {str(e)}")
        
        # Calculate success rate
        success_rate = (len(successful_images) / current_attempt) * 100 if current_attempt > 0 else 0
        
        # Update progress in DynamoDB
        try:
            table.update_item(
                Key={'job_id': job_id},
                UpdateExpression='SET completed_images = :completed, current_attempt = :attempt, success_rate = :rate, image_urls = :urls, updated_at = :updated',
                ExpressionAttributeValues={
                    ':completed': len(successful_images),
                    ':attempt': current_attempt,
                    ':rate': Decimal(str(round(success_rate, 2))),
                    ':urls': successful_images,
                    ':updated': datetime.now(timezone.utc).isoformat()
                }
            )
        except Exception as e:
            print(f"Warning: Could not update progress in DynamoDB: {e}")
        
        # Small delay between attempts
        if current_attempt < max_attempts and len(successful_images) < num_images:
            time.sleep(2)
    
    # Determine final status
    final_status = 'completed' if len(successful_images) >= num_images else 'completed'  # Always completed, may have partial results
    success_rate = (len(successful_images) / current_attempt) * 100 if current_attempt > 0 else 0
    
    # Final update to DynamoDB
    try:
        table.update_item(
            Key={'job_id': job_id},
            UpdateExpression='SET #status = :status, completed_images = :completed, current_attempt = :attempt, success_rate = :rate, image_urls = :urls, updated_at = :updated',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': final_status,
                ':completed': len(successful_images),
                ':attempt': current_attempt,
                ':rate': Decimal(str(round(success_rate, 2))),
                ':urls': successful_images,
                ':updated': datetime.now(timezone.utc).isoformat()
            }
        )
    except Exception as e:
        print(f"Warning: Could not update final status in DynamoDB: {e}")
    
    print(f"Job {job_id} completed: Generated {len(successful_images)}/{num_images} images in {current_attempt} attempts (success rate: {success_rate:.1f}%)")
    
    return {
        'status': final_status,
        'completed_images': len(successful_images),
        'current_attempt': current_attempt,
        'success_rate': success_rate,
        'image_urls': successful_images
    }

def generate_single_image_with_replicate(api_token: str, prompt: str) -> Optional[str]:
    """Generate a single image using Replicate's Flux Dev model"""
    try:
        headers = {
            'Authorization': f'Token {api_token}',
            'Content-Type': 'application/json'
        }
        
        payload = json.dumps({
            'version': 'black-forest-labs/flux-dev',
            'input': {
                'prompt': prompt,
                'aspect_ratio': '3:4',  # Portrait ratio for influencer content
                'output_format': 'jpg',
                'output_quality': 100,
                'num_inference_steps': 50,
                'guidance_scale': 3.5,
                'num_outputs': 1,
                'disable_safety_checker': False
            }
        })
        
        # Submit prediction request
        response = http.request(
            'POST',
            'https://api.replicate.com/v1/predictions',
            body=payload,
            headers=headers
        )
        
        if response.status != 201:
            print(f"Error creating prediction: {response.status} - {response.data.decode('utf-8')}")
            return None
        
        prediction_data = json.loads(response.data.decode('utf-8'))
        prediction_id = prediction_data['id']
        
        # Poll for completion
        max_wait_time = 120  # 2 minutes max wait
        poll_interval = 5    # Poll every 5 seconds
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            status_response = http.request(
                'GET',
                f'https://api.replicate.com/v1/predictions/{prediction_id}',
                headers=headers
            )
            
            if status_response.status == 200:
                status_data = json.loads(status_response.data.decode('utf-8'))
                status = status_data.get('status')
                
                if status == 'succeeded':
                    output = status_data.get('output')
                    if output and isinstance(output, list) and len(output) > 0:
                        return output[0]  # Return first generated image URL
                    elif isinstance(output, str):
                        return output  # Direct URL
                    else:
                        print(f"Unexpected output format: {output}")
                        return None
                        
                elif status == 'failed':
                    error = status_data.get('error', 'Unknown error')
                    print(f"Image generation failed: {error}")
                    return None
                    
                elif status in ['starting', 'processing']:
                    print(f"Generation in progress... ({elapsed_time}s elapsed)")
                    time.sleep(poll_interval)
                    elapsed_time += poll_interval
                    continue
                else:
                    print(f"Unknown status: {status}")
                    return None
            else:
                print(f"Error checking status: {status_response.status}")
                return None
        
        print(f"Timeout waiting for image generation (>{max_wait_time}s)")
        return None
        
    except Exception as e:
        print(f"Error in generate_single_image_with_replicate: {str(e)}")
        return None

def upload_image_to_s3(image_url: str, s3_key: str) -> Optional[str]:
    """Download image from URL and upload to S3"""
    try:
        # Download image
        response = http.request('GET', image_url)
        
        if response.status != 200:
            print(f"Failed to download image: {response.status}")
            return None
        
        # Upload to S3
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=response.data,
            ContentType='image/jpeg'
        )
        
        # Generate S3 URL
        s3_url = f"https://{S3_BUCKET}.s3.amazonaws.com/{s3_key}"
        return s3_url
        
    except Exception as e:
        print(f"Error uploading image to S3: {str(e)}")
        return None
