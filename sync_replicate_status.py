#!/usr/bin/env python3
"""
Sync Content Generation Jobs with Replicate

This script queries all pending/processing jobs in our DynamoDB database,
checks their status on Replicate, and updates our records with the current
status and any error messages.
"""

import json
import boto3
import os
import urllib3
from datetime import datetime, timezone
from decimal import Decimal

# Initialize clients
dynamodb = boto3.resource('dynamodb')
secrets_client = boto3.client('secretsmanager')
http = urllib3.PoolManager()

# Configuration
CONTENT_JOBS_TABLE_NAME = os.environ.get('CONTENT_JOBS_TABLE_NAME', 'ai-influencer-content-jobs')
REPLICATE_API_TOKEN_SECRET = os.environ.get('REPLICATE_API_TOKEN_SECRET', 'replicate-api-token')

def get_secret(secret_name):
    """Retrieve secret from AWS Secrets Manager"""
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except Exception as e:
        print(f"Error retrieving secret {secret_name}: {str(e)}")
        return None

def get_replicate_prediction_status(prediction_id, api_token):
    """Get the current status of a prediction from Replicate"""
    try:
        headers = {'Authorization': f'Token {api_token}'}
        
        response = http.request(
            'GET',
            f'https://api.replicate.com/v1/predictions/{prediction_id}',
            headers=headers
        )
        
        if response.status == 200:
            return json.loads(response.data.decode('utf-8'))
        else:
            print(f"Failed to get prediction status: HTTP {response.status}")
            return None
            
    except Exception as e:
        print(f"Error getting prediction status: {str(e)}")
        return None

def update_job_status(job_id, status_data):
    """Update job status in DynamoDB based on Replicate data"""
    try:
        content_jobs_table = dynamodb.Table(CONTENT_JOBS_TABLE_NAME)
        
        status = status_data.get('status')
        updates = {
            'replicate_status': status,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        if status == 'succeeded':
            output = status_data.get('output')
            output_url = None
            
            # Handle different output formats
            if isinstance(output, list) and len(output) > 0:
                output_url = output[0]
            elif isinstance(output, str):
                output_url = output
            
            if output_url:
                updates.update({
                    'status': 'completed',
                    'output_url': output_url,
                    'completed_at': datetime.now(timezone.utc).isoformat()
                })
            
        elif status == 'failed':
            error_message = status_data.get('error', 'Job failed on Replicate')
            updates.update({
                'status': 'failed',
                'error': error_message
            })
        
        elif status in ['starting', 'processing']:
            updates['status'] = 'processing'
        
        # Build update expression
        update_expression_parts = []
        expression_attribute_values = {}
        
        for key, value in updates.items():
            if value is not None:
                update_expression_parts.append(f"{key} = :{key}")
                expression_attribute_values[f":{key}"] = value
        
        if update_expression_parts:
            content_jobs_table.update_item(
                Key={'job_id': job_id},
                UpdateExpression="SET " + ", ".join(update_expression_parts),
                ExpressionAttributeValues=expression_attribute_values
            )
            
        return True
        
    except Exception as e:
        print(f"Error updating job {job_id}: {str(e)}")
        return False

def sync_jobs():
    """Main sync function"""
    print("Starting Replicate job sync...")
    
    # Get API token
    api_token = get_secret(REPLICATE_API_TOKEN_SECRET)
    if not api_token:
        print("ERROR: Could not retrieve Replicate API token")
        return
    
    # Get all jobs that might need syncing
    try:
        content_jobs_table = dynamodb.Table(CONTENT_JOBS_TABLE_NAME)
        
        # Scan for jobs that are still in processing states or failed without error messages
        response = content_jobs_table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('status').is_in([
                'generating', 'processing', 'generating_image', 'generating_video'
            ]) | (
                boto3.dynamodb.conditions.Attr('status').eq('failed') & 
                boto3.dynamodb.conditions.Attr('error').not_exists()
            )
        )
        
        jobs = response.get('Items', [])
        print(f"Found {len(jobs)} jobs to sync")
        
        if not jobs:
            print("No jobs need syncing!")
            return
        
        synced_count = 0
        updated_count = 0
        
        for job in jobs:
            job_id = job['job_id']
            job_type = job.get('type', 'unknown')
            created_at = job.get('created_at', 'unknown')
            
            print(f"\nProcessing job {job_id} (type: {job_type}, created: {created_at})")
            
            # Try to find the prediction ID
            # Check if we have a stored replicate prediction ID
            prediction_id = job.get('replicate_prediction_id')
            
            if not prediction_id:
                print(f"  No Replicate prediction ID found for job {job_id} - skipping")
                continue
            
            # Get status from Replicate
            print(f"  Checking Replicate prediction {prediction_id}")
            status_data = get_replicate_prediction_status(prediction_id, api_token)
            
            if not status_data:
                print(f"  Could not get status from Replicate")
                continue
                
            current_status = status_data.get('status')
            current_job_status = job.get('status')
            
            print(f"  Replicate status: {current_status}, Current job status: {current_job_status}")
            
            # Update if status has changed
            if current_status != current_job_status:
                print(f"  Status changed from {current_job_status} to {current_status} - updating...")
                
                if update_job_status(job_id, status_data):
                    updated_count += 1
                    print(f"  ✓ Updated job {job_id}")
                    
                    # If failed, print the error message
                    if current_status == 'failed':
                        error_msg = status_data.get('error', 'No error message')
                        print(f"  Error: {error_msg}")
                else:
                    print(f"  ✗ Failed to update job {job_id}")
            else:
                print(f"  Status unchanged - no update needed")
            
            synced_count += 1
        
        print(f"\n=== Sync Complete ===")
        print(f"Jobs processed: {synced_count}")
        print(f"Jobs updated: {updated_count}")
        
    except Exception as e:
        print(f"Error during sync: {str(e)}")

def list_recent_replicate_predictions(api_token, limit=20):
    """List recent predictions from Replicate to help identify missing prediction IDs"""
    try:
        headers = {'Authorization': f'Token {api_token}'}
        
        response = http.request(
            'GET',
            f'https://api.replicate.com/v1/predictions?limit={limit}',
            headers=headers
        )
        
        if response.status == 200:
            data = json.loads(response.data.decode('utf-8'))
            predictions = data.get('results', [])
            
            print(f"\n=== Recent Replicate Predictions ===")
            for pred in predictions:
                pred_id = pred.get('id')
                status = pred.get('status')
                created_at = pred.get('created_at')
                model = pred.get('model', 'unknown')
                
                # Get model name from URL if available
                if isinstance(model, str) and '/' in model:
                    model_name = model.split('/')[-1] if model.startswith('http') else model
                else:
                    model_name = str(model)
                
                print(f"  {pred_id}: {status} (model: {model_name}, created: {created_at})")
                
                if status == 'failed':
                    error = pred.get('error', 'No error message')
                    print(f"    Error: {error}")
            
            return predictions
        else:
            print(f"Failed to get predictions: HTTP {response.status}")
            return []
            
    except Exception as e:
        print(f"Error listing predictions: {str(e)}")
        return []

def interactive_sync():
    """Interactive mode for syncing specific predictions"""
    api_token = get_secret(REPLICATE_API_TOKEN_SECRET)
    if not api_token:
        print("ERROR: Could not retrieve Replicate API token")
        return
    
    print("=== Interactive Replicate Sync ===")
    print("1. List recent Replicate predictions")
    print("2. Sync specific prediction ID")
    print("3. Auto-sync all pending jobs")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == '1':
        limit = input("How many recent predictions to show? (default 20): ").strip()
        limit = int(limit) if limit.isdigit() else 20
        list_recent_replicate_predictions(api_token, limit)
        
    elif choice == '2':
        prediction_id = input("Enter Replicate prediction ID: ").strip()
        if prediction_id:
            status_data = get_replicate_prediction_status(prediction_id, api_token)
            if status_data:
                print(f"\nPrediction Status: {json.dumps(status_data, indent=2)}")
                
                # Ask if user wants to create a job record for this prediction
                create_job = input("\nCreate job record for this prediction? (y/n): ").strip().lower()
                if create_job == 'y':
                    job_id = input("Enter job ID (or press enter for auto-generated): ").strip()
                    if not job_id:
                        import uuid
                        job_id = str(uuid.uuid4())
                    
                    # Create basic job record
                    job = {
                        'job_id': job_id,
                        'replicate_prediction_id': prediction_id,
                        'type': 'image',  # Default, user can modify
                        'status': 'processing',
                        'created_at': datetime.now(timezone.utc).isoformat(),
                        'updated_at': datetime.now(timezone.utc).isoformat()
                    }
                    
                    try:
                        content_jobs_table = dynamodb.Table(CONTENT_JOBS_TABLE_NAME)
                        content_jobs_table.put_item(Item=job)
                        print(f"Created job record: {job_id}")
                        
                        # Now update with Replicate status
                        if update_job_status(job_id, status_data):
                            print(f"Updated job with Replicate status")
                        
                    except Exception as e:
                        print(f"Error creating job: {str(e)}")
            
    elif choice == '3':
        sync_jobs()
    
    else:
        print("Invalid choice")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--interactive':
        interactive_sync()
    else:
        sync_jobs()
