"""
Training Image Generation Webhook Handler for Replicate

This function receives webhook notifications from Replicate when training image
generation jobs complete or fail, providing real-time status updates.
"""

import json
import boto3
import os
import hmac
import hashlib
import urllib3
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional

# Initialize urllib3 for HTTP requests
http = urllib3.PoolManager()

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')
secrets_client = boto3.client('secretsmanager')

# Environment variables
TRAINING_JOBS_TABLE_NAME = os.environ.get('TRAINING_JOBS_TABLE_NAME', 'ai-influencer-training-jobs')
S3_BUCKET = os.environ.get('S3_BUCKET_NAME', 'ai-influencer-system-dev-content-bkdeyg')
REPLICATE_WEBHOOK_SECRET = os.environ.get('REPLICATE_WEBHOOK_SECRET', 'replicate-webhook-secret')

def get_secret(secret_name: str) -> Optional[str]:
    """Retrieve secret from AWS Secrets Manager"""
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except Exception as e:
        print(f"Error retrieving secret {secret_name}: {str(e)}")
        return None

def verify_webhook_signature(payload: str, signature: str, secret: str) -> bool:
    """Verify the webhook signature from Replicate"""
    if not signature or not secret:
        return False
    
    try:
        # Replicate sends signature as 'sha256=<hex_digest>'
        expected_signature = 'sha256=' + hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    except Exception as e:
        print(f"Error verifying webhook signature: {str(e)}")
        return False

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

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main Lambda handler for training image generation webhooks"""
    
    try:
        print(f"Received webhook event: {json.dumps(event)}")
        
        # Extract request details
        http_method = event.get('httpMethod', 'POST')
        headers = event.get('headers', {})
        body = event.get('body', '')
        
        # Handle CORS preflight
        if http_method == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type, X-Replicate-Signature',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS'
                },
                'body': ''
            }
        
        if http_method != 'POST':
            return {
                'statusCode': 405,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Method not allowed'})
            }
        
        # Verify webhook signature for security
        signature = headers.get('X-Replicate-Signature') or headers.get('x-replicate-signature')
        webhook_secret = get_secret(REPLICATE_WEBHOOK_SECRET)
        
        if webhook_secret and webhook_secret != "placeholder-secret":
            if not verify_webhook_signature(body, signature, webhook_secret):
                print("Webhook signature verification failed")
                return {
                    'statusCode': 401,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'Unauthorized - invalid signature'})
                }
        else:
            print("Warning: Webhook secret not configured, skipping signature verification")
        
        # Parse webhook payload
        try:
            webhook_data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Invalid JSON payload'})
            }
        
        # Extract prediction information
        prediction_id = webhook_data.get('id')
        status = webhook_data.get('status')
        
        if not prediction_id:
            print("No prediction ID in webhook payload")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Missing prediction ID'})
            }
        
        # Extract job information from query parameters (since metadata field is not supported)
        query_params = event.get('queryStringParameters', {})
        job_id = query_params.get('job_id') if query_params else None
        image_index = query_params.get('image_index') if query_params else None
        
        # Convert image_index to int if present
        if image_index:
            try:
                image_index = int(image_index)
            except ValueError:
                image_index = None
        
        if not job_id:
            print(f"No job_id in metadata for prediction {prediction_id}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Missing job_id in metadata'})
            }
        
        print(f"Processing webhook for prediction {prediction_id}, job {job_id}, image {image_index}, status {status}")
        
        # Process the webhook based on status
        result = process_training_webhook(
            job_id=job_id,
            prediction_id=prediction_id,
            image_index=image_index,
            status=status,
            webhook_data=webhook_data
        )
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'message': 'Webhook processed successfully',
                'job_id': job_id,
                'prediction_id': prediction_id,
                'status': status,
                'processed': result
            })
        }
        
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f'Webhook processing failed: {str(e)}'})
        }

def process_training_webhook(
    job_id: str,
    prediction_id: str,
    image_index: int,
    status: str,
    webhook_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Process a training image generation webhook"""
    
    table = dynamodb.Table(TRAINING_JOBS_TABLE_NAME)
    
    try:
        # Get the current job record
        response = table.get_item(Key={'job_id': job_id})
        job = response.get('Item')
        
        if not job:
            print(f"Job {job_id} not found in database")
            return {'error': 'Job not found'}
        
        # Get current predictions list
        predictions = job.get('replicate_predictions', [])
        image_urls = job.get('image_urls', [])
        
        # Find and update the specific prediction
        prediction_updated = False
        for prediction in predictions:
            if prediction['prediction_id'] == prediction_id:
                prediction['status'] = status
                prediction['updated_at'] = datetime.now(timezone.utc).isoformat()
                
                if status == 'succeeded':
                    # Handle successful image generation
                    output = webhook_data.get('output')
                    if output:
                        image_url = output[0] if isinstance(output, list) else output
                        
                        # Download and upload to S3
                        character_name = job.get('character_name', 'unknown')
                        folder_id = job.get('character_id', job_id)
                        s3_key = f"training-images/{folder_id}/{character_name.replace(' ', '_')}_training_{image_index:02d}.jpg"
                        
                        s3_url = upload_image_to_s3(image_url, s3_key)
                        if s3_url:
                            prediction['s3_url'] = s3_url
                            image_urls.append(s3_url)
                            print(f"Successfully uploaded image {image_index} for job {job_id}")
                        else:
                            prediction['error'] = 'Failed to upload to S3'
                            print(f"Failed to upload image {image_index} for job {job_id}")
                    
                elif status == 'failed':
                    # Handle failed generation
                    error_message = webhook_data.get('error', 'Image generation failed')
                    prediction['error'] = error_message
                    print(f"Image generation failed for job {job_id}, image {image_index}: {error_message}")
                
                prediction_updated = True
                break
        
        if not prediction_updated:
            print(f"Prediction {prediction_id} not found in job {job_id}")
            return {'error': 'Prediction not found in job'}
        
        # Calculate progress statistics
        completed_predictions = len([p for p in predictions if p.get('status') == 'succeeded'])
        failed_predictions = len([p for p in predictions if p.get('status') == 'failed'])
        total_attempts = len([p for p in predictions if p.get('status') in ['succeeded', 'failed']])
        
        success_rate = (completed_predictions / total_attempts * 100) if total_attempts > 0 else 0
        
        # Determine if job is complete
        total_images = job.get('total_images', len(predictions))
        job_status = 'processing'
        
        # Job is complete if we have enough successful images OR all predictions are done
        all_predictions_done = len([p for p in predictions if p.get('status') in ['succeeded', 'failed']]) >= len(predictions)
        target_reached = completed_predictions >= total_images
        
        if target_reached or all_predictions_done:
            job_status = 'completed'
        
        # Update the job record
        update_expression = 'SET replicate_predictions = :predictions, completed_images = :completed, image_urls = :urls, success_rate = :rate, #status = :status, updated_at = :updated'
        expression_attribute_names = {'#status': 'status'}
        expression_attribute_values = {
            ':predictions': predictions,
            ':completed': completed_predictions,
            ':urls': image_urls,
            ':rate': Decimal(str(round(success_rate, 2))),
            ':status': job_status,
            ':updated': datetime.now(timezone.utc).isoformat()
        }
        
        table.update_item(
            Key={'job_id': job_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values
        )
        
        print(f"Updated job {job_id}: {completed_predictions}/{total_images} images completed, {success_rate:.1f}% success rate, status: {job_status}")
        
        return {
            'job_updated': True,
            'completed_images': completed_predictions,
            'total_images': total_images,
            'success_rate': float(success_rate),
            'job_status': job_status
        }
        
    except Exception as e:
        print(f"Error processing webhook for job {job_id}: {str(e)}")
        return {'error': str(e)}
