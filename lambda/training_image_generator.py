"""
AWS Lambda function for generating training images using Replicate's Flux 1.1 Pro

This function generates diverse training images for characters using AI image generation,
with varied poses, expressions, and settings to create a comprehensive training dataset.
"""

import json
import boto3
import os
import uuid
import urllib3
import time
from datetime import datetime, timezone
from typing import Dict, Any

# Initialize urllib3 for HTTP requests
http = urllib3.PoolManager()

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
secrets_client = boto3.client('secretsmanager')

# Environment variables
S3_BUCKET = os.environ.get('S3_BUCKET_NAME', 'ai-influencer-system-dev-content-bkdeyg')
REPLICATE_API_TOKEN_SECRET = os.environ.get('REPLICATE_API_TOKEN_SECRET', 'replicate-api-token')

def get_secret(secret_name):
    """Retrieve secret from AWS Secrets Manager"""
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except Exception as e:
        print(f"Error retrieving secret {secret_name}: {str(e)}")
        return None

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for training image generation using Flux 1.1 Pro
    """
    print(f"Received event: {json.dumps(event)}")
    
    try:
        # Extract character information
        character_name = event.get('character_name')
        character_description = event.get('character_description')
        character_id = event.get('character_id')  # Optional - for organizing images
        num_images = event.get('num_images', 15)  # Default to 15 images, configurable to save costs
        
        if not character_name or not character_description:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing character_name or character_description'
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
        
        # Use character_id if provided, otherwise use job_id for organization
        folder_id = character_id if character_id else job_id
        
        # Define varied prompts optimized for AI influencer training
        # These create diverse, attractive images suitable for social media and premium content
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
        
        # Use only the requested number of images (default 15, max 20)
        prompts = all_prompts[:min(num_images, len(all_prompts))]
        
        print(f"Starting training image generation for character: {character_name}")
        print(f"Description: {character_description}")
        print(f"Job ID: {job_id}")
        print(f"Will generate {len(prompts)} training images with varied poses")
        
        # Store initial job status in DynamoDB
        try:
            table = dynamodb.Table('ai-influencer-training-jobs')
            table.put_item(
                Item={
                    'job_id': job_id,
                    'character_name': character_name,
                    'character_description': character_description,
                    'character_id': folder_id,
                    'status': 'processing',
                    'total_images': len(prompts),
                    'completed_images': 0,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'image_urls': []
                }
            )
        except Exception as e:
            print(f"Warning: Could not store job in DynamoDB: {e}")
        
        # Generate images using Replicate
        image_urls = []
        successful_generations = 0
        
        for i, prompt in enumerate(prompts, 1):
            try:
                print(f"Generating image {i}/{len(prompts)}: {prompt[:100]}...")
                
                # Generate image using Replicate Flux 1.1 Pro
                image_url = generate_image_with_replicate(api_token, prompt)
                
                if image_url:
                    # Download and upload to S3
                    s3_key = f"training-images/{folder_id}/{character_name.replace(' ', '_')}_training_{i:02d}.jpg"
                    s3_url = upload_image_to_s3(image_url, s3_key)
                    
                    if s3_url:
                        image_urls.append(s3_url)
                        successful_generations += 1
                        print(f"Successfully generated and uploaded image {i}/{len(prompts)}")
                    else:
                        print(f"Failed to upload image {i} to S3")
                else:
                    print(f"Failed to generate image {i} with Replicate")
                
                # Update progress in DynamoDB
                try:
                    table.update_item(
                        Key={'job_id': job_id},
                        UpdateExpression='SET completed_images = :completed, image_urls = :urls',
                        ExpressionAttributeValues={
                            ':completed': successful_generations,
                            ':urls': image_urls
                        }
                    )
                except Exception as e:
                    print(f"Warning: Could not update progress in DynamoDB: {e}")
                
                # Small delay to avoid rate limits
                time.sleep(1)
                    
            except Exception as e:
                print(f"Error generating image {i}: {e}")
                continue
        
        # Mark job as completed
        final_status = 'completed' if successful_generations > 0 else 'failed'
        try:
            table.update_item(
                Key={'job_id': job_id},
                UpdateExpression='SET #status = :status, completed_images = :completed, updated_at = :updated',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': final_status,
                    ':completed': successful_generations,
                    ':updated': datetime.now(timezone.utc).isoformat()
                }
            )
        except Exception as e:
            print(f"Warning: Could not mark job as completed in DynamoDB: {e}")
        
        print(f"Job completed: Generated {successful_generations}/{len(prompts)} training images")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'job_id': job_id,
                'status': final_status,
                'message': f'Training image generation completed for {character_name}',
                'total_requested': len(prompts),
                'successful_generations': successful_generations,
                'image_urls': image_urls
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

def generate_image_with_replicate(api_token: str, prompt: str) -> str:
    """Generate an image using Replicate's Flux 1.1 Pro model"""
    try:
        # Replicate API endpoint for predictions
        headers = {
            'Authorization': f'Token {api_token}',
            'Content-Type': 'application/json'
        }
        
        # Payload for Flux Dev (official version from Replicate API)
        payload = json.dumps({
            'version': 'black-forest-labs/flux-dev',  # Use latest version
            'input': {
                'prompt': prompt,
                'aspect_ratio': '3:4',  # Portrait ratio for influencer content
                'output_format': 'jpg',
                'output_quality': 100,
                'num_inference_steps': 50,  # Default from API docs
                'guidance_scale': 3.5,     # Default from API docs  
                'num_outputs': 1,
                'disable_safety_checker': False  # Keep safety checker but Flux is less restrictive
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
            # Check prediction status
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
        print(f"Error in generate_image_with_replicate: {str(e)}")
        return None

def upload_image_to_s3(image_url: str, s3_key: str) -> str:
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
