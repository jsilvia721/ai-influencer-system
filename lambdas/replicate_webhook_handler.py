"""
Replicate Webhook Handler Lambda Function

This function receives webhook notifications from Replicate when LoRA training
jobs complete or fail, providing real-time status updates without polling.
"""

import json
import boto3
import os
import hmac
import hashlib
from datetime import datetime, timezone
from decimal import Decimal

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
secrets_client = boto3.client('secretsmanager')

# Environment variables
CHARACTERS_TABLE_NAME = os.environ.get('CHARACTERS_TABLE_NAME', 'ai-influencer-characters')
TRAINING_JOBS_TABLE_NAME = os.environ.get('TRAINING_JOBS_TABLE_NAME', 'ai-influencer-training-jobs')
CONTENT_JOBS_TABLE_NAME = os.environ.get('CONTENT_JOBS_TABLE_NAME', 'ai-influencer-content-jobs')
REPLICATE_WEBHOOK_SECRET = os.environ.get('REPLICATE_WEBHOOK_SECRET', 'replicate-webhook-secret')

def get_secret(secret_name):
    """Retrieve secret from AWS Secrets Manager"""
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except Exception as e:
        print(f"Error retrieving secret {secret_name}: {str(e)}")
        return None

def verify_webhook_signature(payload, signature, secret):
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

def decimal_default(obj):
    """JSON serializer for DynamoDB Decimal types"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def lambda_handler(event, context):
    """Main Lambda handler for Replicate webhooks"""
    
    try:
        print(f"Received webhook event: {json.dumps(event)}")
        
        # Extract request details
        http_method = event.get('httpMethod', 'POST')
        path = event.get('path', '/')
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
        
        print(f"Processing webhook for prediction {prediction_id} with status {status}")
        
        # Try to find a training job first
        training_jobs_table = dynamodb.Table(TRAINING_JOBS_TABLE_NAME)
        response = training_jobs_table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('replicate_id').eq(prediction_id)
        )
        
        training_jobs = response.get('Items', [])
        
        # If no training job found, check for content generation job
        if not training_jobs:
            content_jobs_table = dynamodb.Table(CONTENT_JOBS_TABLE_NAME)
            response = content_jobs_table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('replicate_prediction_id').eq(prediction_id)
            )
            
            content_jobs = response.get('Items', [])
            if content_jobs:
                return handle_content_generation_webhook(content_jobs[0], webhook_data, status)
        
        if not training_jobs:
            print(f"No job found for Replicate ID: {prediction_id}")
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Job not found'})
            }
        
        # Should only be one job per replicate_id
        job = training_jobs[0]
        job_id = job['job_id']
        character_id = job['character_id']
        
        print(f"Found training job {job_id} for character {character_id}")
        
        # Update job status based on webhook
        updates = {
            'replicate_status': status,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        if status == 'succeeded':
            # Training completed successfully
            updates.update({
                'status': 'completed',
                'completed_at': datetime.now(timezone.utc).isoformat(),
                'lora_model_url': webhook_data.get('output')
            })
            
            # Update character record with completed training status and LoRA model info
            update_character_training_status(character_id, 'completed', {
                'lora_model_url': webhook_data.get('output'),
                'trigger_word': job.get('trigger_word'),
                'training_completed_at': datetime.now(timezone.utc).isoformat()
            })
            
            print(f"Training completed successfully for job {job_id}")
            
        elif status == 'failed':
            # Training failed
            error_message = webhook_data.get('error', 'Training failed on Replicate')
            updates.update({
                'status': 'failed',
                'error': error_message
            })
            
            # Update character record with failed status
            update_character_training_status(character_id, 'failed')
            
            print(f"Training failed for job {job_id}: {error_message}")
            
        elif status in ['starting', 'processing']:
            # Training in progress
            updates['status'] = 'training'
            
            # Update character record with training status
            update_character_training_status(character_id, 'training')
            
            print(f"Training in progress for job {job_id}: {status}")
        
        # Apply updates to job record
        update_expression_parts = []
        expression_attribute_values = {}
        expression_attribute_names = {}
        
        for key, value in updates.items():
            if key == 'status':  # Handle reserved keyword
                update_expression_parts.append("#status = :status")
                expression_attribute_names['#status'] = 'status'
                expression_attribute_values[':status'] = value
            elif key == 'error':  # Handle reserved keyword
                update_expression_parts.append("#error = :error")
                expression_attribute_names['#error'] = 'error'
                expression_attribute_values[':error'] = value
            else:
                update_expression_parts.append(f"{key} = :{key}")
                expression_attribute_values[f":{key}"] = value
        
        update_kwargs = {
            'Key': {'job_id': job_id},
            'UpdateExpression': "SET " + ", ".join(update_expression_parts),
            'ExpressionAttributeValues': expression_attribute_values
        }
        
        if expression_attribute_names:
            update_kwargs['ExpressionAttributeNames'] = expression_attribute_names
        
        training_jobs_table.update_item(**update_kwargs)
        
        print(f"Updated training job {job_id} with status {status}")
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'message': 'Webhook processed successfully',
                'job_id': job_id,
                'status': status
            }, default=decimal_default)
        }
        
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f'Webhook processing failed: {str(e)}'})
        }

def update_character_training_status(character_id, status, lora_info=None):
    """Update character training status and optionally LoRA model info"""
    
    try:
        characters_table = dynamodb.Table(CHARACTERS_TABLE_NAME)
        
        # Base updates
        updates = {
            'training_status': status,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        # Add LoRA model info if provided (for completed training)
        if lora_info:
            updates.update({
                'lora_model_url': lora_info.get('lora_model_url'),
                'trigger_word': lora_info.get('trigger_word'),
                'training_completed_at': lora_info.get('training_completed_at')
            })
        
        # Build update expression
        update_expression_parts = []
        expression_attribute_values = {}
        
        for key, value in updates.items():
            if value is not None:  # Only update non-null values
                update_expression_parts.append(f"{key} = :{key}")
                expression_attribute_values[f":{key}"] = value
        
        if update_expression_parts:
            characters_table.update_item(
                Key={'id': character_id},
                UpdateExpression="SET " + ", ".join(update_expression_parts),
                ExpressionAttributeValues=expression_attribute_values
            )
            
        print(f"Updated character {character_id} training status to {status}")
        
    except Exception as e:
        print(f"Error updating character training status: {str(e)}")

def handle_content_generation_webhook(content_job, webhook_data, status):
    """Handle webhook for content generation jobs"""
    
    try:
        job_id = content_job['job_id']
        content_jobs_table = dynamodb.Table(CONTENT_JOBS_TABLE_NAME)
        
        print(f"Found content generation job {job_id} with status {status}")
        
        # Update job status based on webhook
        updates = {
            'replicate_status': status,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        if status == 'succeeded':
            # Content generation completed successfully
            output = webhook_data.get('output')
            
            # Handle different output formats from Replicate
            output_url = None
            if isinstance(output, list) and len(output) > 0:
                # Usually for images/videos, output is a list of URLs
                output_url = output[0]
            elif isinstance(output, str):
                # Sometimes output is directly a string URL
                output_url = output
            
            updates.update({
                'status': 'completed',
                'completed_at': datetime.now(timezone.utc).isoformat(),
                'output_url': output_url,
                'replicate_output': output  # Store full output for reference
            })
            
            print(f"Content generation completed successfully for job {job_id}")
            
        elif status == 'failed':
            # Content generation failed
            error_message = webhook_data.get('error', 'Content generation failed on Replicate')
            updates.update({
                'status': 'failed',
                'error': error_message
            })
            
            print(f"Content generation failed for job {job_id}: {error_message}")
            
        elif status in ['starting', 'processing']:
            # Content generation in progress
            updates['status'] = 'processing'
            
            print(f"Content generation in progress for job {job_id}: {status}")
        
        # Apply updates to job record
        update_expression_parts = []
        expression_attribute_values = {}
        expression_attribute_names = {}
        
        for key, value in updates.items():
            if value is not None:  # Only update non-null values
                if key == 'status':  # Handle reserved keyword
                    update_expression_parts.append("#status = :status")
                    expression_attribute_names['#status'] = 'status'
                    expression_attribute_values[':status'] = value
                elif key == 'error':  # Handle reserved keyword
                    update_expression_parts.append("#error = :error")
                    expression_attribute_names['#error'] = 'error'
                    expression_attribute_values[':error'] = value
                else:
                    update_expression_parts.append(f"{key} = :{key}")
                    expression_attribute_values[f":{key}"] = value
        
        if update_expression_parts:
            update_kwargs = {
                'Key': {'job_id': job_id},
                'UpdateExpression': "SET " + ", ".join(update_expression_parts),
                'ExpressionAttributeValues': expression_attribute_values
            }
            
            if expression_attribute_names:
                update_kwargs['ExpressionAttributeNames'] = expression_attribute_names
            
            content_jobs_table.update_item(**update_kwargs)
        
        print(f"Updated content generation job {job_id} with status {status}")
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'message': 'Content generation webhook processed successfully',
                'job_id': job_id,
                'status': status
            }, default=decimal_default)
        }
        
    except Exception as e:
        print(f"Error processing content generation webhook: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f'Content generation webhook processing failed: {str(e)}'})
        }
