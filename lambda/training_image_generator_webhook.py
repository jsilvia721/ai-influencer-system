"""
AWS Lambda function for generating training images using Replicate's Flux 1.1 Pro with Webhooks

This function generates diverse training images for characters using AI image generation,
with webhooks for real-time status updates instead of polling.
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
    AWS Lambda handler for training image generation using webhooks
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
        
        print(f"Starting training image generation for character: {character_name}")
        print(f"Target: {num_images} images")
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
            'max_attempts': min(num_images * 2 + 3, 25),
            'success_rate': Decimal('0.0'),
            'image_urls': [],
            'replicate_predictions': [],  # Store prediction IDs for webhook tracking
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        try:
            table = dynamodb.Table('ai-influencer-training-jobs')
            table.put_item(Item=job_record)
        except Exception as e:
            print(f"Warning: Could not store job in DynamoDB: {e}")
        
        # Start the image generation process with webhooks
        result = generate_training_images_with_webhooks(
            api_token=api_token,
            job_id=job_id,
            character_name=character_name,
            character_description=character_description,
            folder_id=folder_id,
            num_images=num_images,
            table=table
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'job_id': job_id,
                'status': 'processing',
                'message': f'Training image generation started for {character_name}',
                'total_requested': num_images,
                'webhook_enabled': True,
                'predictions_submitted': result.get('predictions_submitted', 0),
                'real_time_updates': 'enabled'
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

def generate_training_images_with_webhooks(
    api_token: str,
    job_id: str,
    character_name: str,
    character_description: str,
    folder_id: str,
    num_images: int,
    table
) -> Dict[str, Any]:
    """
    Generate training images using webhooks for real-time updates.
    Submits all predictions at once with webhook URLs.
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
    
    # Use the requested number of prompts (cycle if needed)
    prompts = []
    for i in range(num_images):
        prompts.append(all_prompts[i % len(all_prompts)])
    
    # Submit all predictions with webhook URLs
    prediction_ids = []
    successful_submissions = 0
    
    # Get the webhook URL - this should be configured in your API Gateway
    webhook_url = get_webhook_url()
    
    for i, prompt in enumerate(prompts, 1):
        try:
            print(f"Submitting prediction {i}/{num_images}: {prompt[:100]}...")
            
            prediction_id = submit_prediction_with_webhook(
                api_token=api_token,
                prompt=prompt,
                webhook_url=webhook_url,
                job_id=job_id,
                image_index=i
            )
            
            if prediction_id:
                prediction_ids.append({
                    'prediction_id': prediction_id,
                    'image_index': i,
                    'prompt': prompt,
                    'status': 'submitted',
                    'submitted_at': datetime.now(timezone.utc).isoformat()
                })
                successful_submissions += 1
                print(f"Successfully submitted prediction {i}/{num_images}: {prediction_id}")
            else:
                print(f"Failed to submit prediction {i}/{num_images}")
        
        except Exception as e:
            print(f"Error submitting prediction {i}: {str(e)}")
    
    # Update job with prediction IDs
    try:
        table.update_item(
            Key={'job_id': job_id},
            UpdateExpression='SET replicate_predictions = :predictions, current_attempt = :attempt, updated_at = :updated',
            ExpressionAttributeValues={
                ':predictions': prediction_ids,
                ':attempt': successful_submissions,
                ':updated': datetime.now(timezone.utc).isoformat()
            }
        )
    except Exception as e:
        print(f"Warning: Could not update predictions in DynamoDB: {e}")
    
    print(f"Job {job_id}: Submitted {successful_submissions}/{num_images} predictions for webhook processing")
    
    return {
        'predictions_submitted': successful_submissions,
        'prediction_ids': [p['prediction_id'] for p in prediction_ids],
        'status': 'processing'
    }

def get_webhook_url() -> str:
    """Get the webhook URL for Replicate callbacks"""
    # This should be your API Gateway URL + webhook endpoint
    # Format: https://your-api-gateway-id.execute-api.region.amazonaws.com/stage/replicate-webhook
    
    # You can set this as an environment variable or construct it
    api_gateway_url = os.environ.get('API_GATEWAY_URL', 'https://9fkbuxy8g6.execute-api.us-east-1.amazonaws.com/dev')
    return f"{api_gateway_url}/replicate-webhook"

def submit_prediction_with_webhook(
    api_token: str,
    prompt: str,
    webhook_url: str,
    job_id: str,
    image_index: int
) -> Optional[str]:
    """Submit a single prediction with webhook URL to Replicate"""
    try:
        headers = {
            'Authorization': f'Token {api_token}',
            'Content-Type': 'application/json'
        }
        
        # Encode metadata in webhook URL as query parameters since metadata field is not allowed
        webhook_url_with_params = f"{webhook_url}?job_id={job_id}&image_index={image_index}"
        
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
            },
            'webhook': webhook_url_with_params,
            'webhook_events_filter': ['start', 'completed']
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
        
        print(f"Successfully submitted prediction {prediction_id} with webhook {webhook_url}")
        return prediction_id
        
    except Exception as e:
        print(f"Error in submit_prediction_with_webhook: {str(e)}")
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
