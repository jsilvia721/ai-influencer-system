#!/usr/bin/env python3
"""
Sync Content Generation Jobs with Replicate - Lambda Function

This Lambda function can be called via API to sync all content generation jobs
with their current status on Replicate, including error messages.
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
        secret_data = json.loads(response['SecretString'])
        return secret_data.get('replicate_api_key')  # Extract the specific API key
    except Exception as e:
        print(f"Error retrieving secret {secret_name}: {str(e)}")
        return None

def decimal_default(obj):
    """JSON serializer for DynamoDB Decimal types"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def get_replicate_predictions(api_token, max_predictions=1000):
    """Get ALL predictions from Replicate with pagination for disaster recovery"""
    all_predictions = []
    next_cursor = None
    fetched_count = 0
    
    try:
        headers = {'Authorization': f'Token {api_token}'}
        
        while fetched_count < max_predictions:
            # Build URL with pagination
            url = 'https://api.replicate.com/v1/predictions?limit=100'
            if next_cursor:
                url += f'&cursor={next_cursor}'
            
            print(f"Fetching predictions from Replicate (batch {len(all_predictions)//100 + 1})...")
            
            response = http.request('GET', url, headers=headers)
            
            if response.status == 200:
                data = json.loads(response.data.decode('utf-8'))
                batch_predictions = data.get('results', [])
                
                if not batch_predictions:
                    print("No more predictions to fetch")
                    break
                
                all_predictions.extend(batch_predictions)
                fetched_count += len(batch_predictions)
                
                print(f"Fetched {len(batch_predictions)} predictions (total: {len(all_predictions)})")
                
                # Check if there's more data
                next_cursor = data.get('next')
                if not next_cursor:
                    print("Reached end of predictions")
                    break
                    
            elif response.status == 429:
                print("Rate limited by Replicate API, waiting 5 seconds...")
                import time
                time.sleep(5)
                continue
            else:
                print(f"Failed to get predictions: HTTP {response.status}")
                if response.data:
                    print(f"Error details: {response.data.decode('utf-8')}")
                break
        
        print(f"Successfully fetched {len(all_predictions)} total predictions from Replicate")
        return all_predictions
        
    except Exception as e:
        print(f"Error getting predictions: {str(e)}")
        return all_predictions  # Return what we have so far

def get_replicate_prediction_status(prediction_id, api_token):
    """Get the current status of a specific prediction from Replicate"""
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
            print(f"Failed to get prediction status for {prediction_id}: HTTP {response.status}")
            return None
            
    except Exception as e:
        print(f"Error getting prediction status for {prediction_id}: {str(e)}")
        return None

def update_job_with_replicate_data(job, prediction_data):
    """Update a job record with data from Replicate using optimal schema v2.0"""
    try:
        content_jobs_table = dynamodb.Table(CONTENT_JOBS_TABLE_NAME)
        
        prediction_status = prediction_data.get('status')
        updates = {
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'prediction_id': prediction_data.get('id'),
            'prediction_status': prediction_status,
        }
        
        # Store comprehensive prediction data using optimal schema
        if prediction_data.get('created_at'):
            updates['prediction_created_at'] = prediction_data['created_at']
        if prediction_data.get('started_at'):
            updates['prediction_started_at'] = prediction_data['started_at'] 
        if prediction_data.get('completed_at'):
            updates['prediction_completed_at'] = prediction_data['completed_at']
            
        # Input parameters
        if prediction_data.get('input'):
            updates['input_params'] = prediction_data['input']
            
        # Model information
        if prediction_data.get('model'):
            model_url = prediction_data['model']
            # Parse model info from URL like "owner/model-name" 
            if '/' in model_url:
                owner, model_name = model_url.split('/', 1)
                updates['model_info'] = {
                    'model_owner': owner,
                    'model_name': model_name,
                    'model_url': model_url
                }
        
        if prediction_data.get('version'):
            if 'model_info' not in updates:
                updates['model_info'] = {}
            updates['model_info']['model_version'] = prediction_data['version']
            
        # Execution logs and metrics
        if prediction_data.get('logs'):
            updates['execution_logs'] = prediction_data['logs']
        if prediction_data.get('metrics'):
            updates['metrics'] = prediction_data['metrics']
            
        # URLs
        if prediction_data.get('urls'):
            updates['urls'] = prediction_data['urls']
            
        # Output data
        if prediction_data.get('output'):
            updates['output_data'] = prediction_data['output']
        
        # Store additional Replicate fields based on OpenAPI schema
        if prediction_data.get('data_removed'):
            updates['data_removed'] = prediction_data['data_removed']
        if prediction_data.get('deployment'):
            updates['deployment'] = prediction_data['deployment']
            
        # Handle status-specific logic based on Replicate's 5 status values
        if prediction_status == 'succeeded':
            output = prediction_data.get('output')
            result_url = None
            
            # Handle different output formats
            if isinstance(output, list) and len(output) > 0:
                result_url = output[0]
            elif isinstance(output, str):
                result_url = output
            
            if result_url:
                # Determine result type based on URL or job type
                result_type = 'video' if any(ext in result_url.lower() for ext in ['.mp4', '.mov', '.webm']) else 'image'
                
                updates.update({
                    'status': 'completed',
                    'result_urls': [result_url] if isinstance(output, str) else output,
                    'result_type': result_type,
                    'primary_result_url': result_url,
                    'completed_at': prediction_data.get('completed_at', datetime.now(timezone.utc).isoformat())
                })
            
        elif prediction_status == 'failed':
            error_message = prediction_data.get('error', 'Job failed on Replicate')
            
            # Create structured error information
            error_details = {
                'category': 'replicate_error',
                'component': 'replicate',
                'original_error': error_message,
                'prediction_id': prediction_data.get('id')
            }
            
            # Add model-specific error categorization
            if error_message and 'LoRA' in error_message or 'lora' in error_message.lower():
                error_details['component'] = 'lora'
                error_details['category'] = 'model_error'
            elif error_message and 'kling' in error_message.lower():
                error_details['component'] = 'kling'
                error_details['category'] = 'model_error'
            
            updates.update({
                'status': 'failed',
                'error_message': error_message,  # Human readable
                'error_details': error_details  # Structured data
            })
            
        elif prediction_status == 'canceled':
            updates['status'] = 'canceled'
            
        elif prediction_status in ['starting', 'processing']:
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
                Key={'job_id': job['job_id']},
                UpdateExpression="SET " + ", ".join(update_expression_parts),
                ExpressionAttributeValues=expression_attribute_values
            )
            
        return True
        
    except Exception as e:
        print(f"Error updating job {job.get('job_id')}: {str(e)}")
        return False

def match_jobs_with_predictions(jobs, predictions):
    """Match jobs with Replicate predictions based on prompts and timing"""
    matches = []
    
    # Create a lookup of predictions by model and prompt
    prediction_lookup = {}
    for pred in predictions:
        # Extract prompt and model info
        input_data = pred.get('input', {})
        prompt = input_data.get('prompt', '')
        model = pred.get('model', '')
        created_at = pred.get('created_at', '')
        
        # Create a key for matching
        key = f"{prompt[:50]}_{model}"  # Use first 50 chars of prompt + model
        
        if key not in prediction_lookup:
            prediction_lookup[key] = []
        prediction_lookup[key].append(pred)
    
    # Try to match jobs with predictions
    for job in jobs:
        job_prompt = job.get('prompt', '')
        job_created = job.get('created_at', '')
        
        # If job already has a prediction ID, try to find exact match
        if job.get('replicate_prediction_id'):
            for pred in predictions:
                if pred.get('id') == job.get('replicate_prediction_id'):
                    matches.append((job, pred))
                    break
            continue
        
        # Try to match based on prompt and timing
        # Look for predictions with similar prompts
        for key, pred_list in prediction_lookup.items():
            if job_prompt[:50] in key or any(job_prompt.lower() in pred.get('input', {}).get('prompt', '').lower() for pred in pred_list):
                # Find the prediction closest in time to the job creation
                best_match = None
                min_time_diff = float('inf')
                
                try:
                    job_time = datetime.fromisoformat(job_created.replace('Z', '+00:00'))
                    
                    for pred in pred_list:
                        pred_time = datetime.fromisoformat(pred.get('created_at', '').replace('Z', '+00:00'))
                        time_diff = abs((job_time - pred_time).total_seconds())
                        
                        if time_diff < min_time_diff and time_diff < 3600:  # Within 1 hour
                            min_time_diff = time_diff
                            best_match = pred
                    
                    if best_match:
                        matches.append((job, best_match))
                        break
                        
                except Exception as e:
                    print(f"Error matching job timing: {str(e)}")
                    continue
    
    return matches

def create_job_from_prediction(prediction_data):
    """Create a job record from a Replicate prediction using optimal schema v2.0"""
    try:
        # Extract basic info from prediction
        prediction_id = prediction_data.get('id')
        prediction_status = prediction_data.get('status')
        
        # Create job ID from prediction ID
        job_id = f"replicate-{prediction_id}"
        
        # Extract character info from prompt if available
        input_data = prediction_data.get('input', {})
        prompt = input_data.get('prompt', '')
        
        # Try to extract character trigger word from prompt
        character_name = 'Unknown'
        character_trigger_word = None
        character_id = None
        
        # Look for common trigger word patterns
        if 'valentina_cruz_character' in prompt.lower():
            character_name = 'Valentina Cruz'
            character_trigger_word = 'valentina_cruz_character'
            character_id = '66fd7b15-dccd-4069-bf95-0a23cdc7b348'  # Known character ID
        elif 'sofia_woman' in prompt.lower():
            character_name = 'Sofia'
            character_trigger_word = 'sofia_woman'
        
        # Determine job type
        model_url = prediction_data.get('model', '')
        job_type = 'video' if 'kling' in model_url.lower() else 'image'
        
        # Build job record using optimal schema v2.0
        job = {
            'job_id': job_id,
            'created_at': prediction_data.get('created_at', datetime.now(timezone.utc).isoformat()),
            'updated_at': datetime.now(timezone.utc).isoformat(),
            
            # Job request data
            'job_type': job_type,
            'user_prompt': prompt,
            'character_name': character_name,
            'retry_count': 0
        }
        
        # Add character info if found
        if character_id:
            job['character_id'] = character_id
        if character_trigger_word:
            job['character_trigger_word'] = character_trigger_word
            
        # Add LoRA model URL if it's a LoRA job
        if job_type == 'image' and '/' in model_url:
            job['lora_model_url'] = model_url
        
        # Replicate prediction data
        job['prediction_id'] = prediction_id
        job['prediction_status'] = prediction_status
        
        if prediction_data.get('created_at'):
            job['prediction_created_at'] = prediction_data['created_at']
        if prediction_data.get('started_at'):
            job['prediction_started_at'] = prediction_data['started_at']
        if prediction_data.get('completed_at'):
            job['prediction_completed_at'] = prediction_data['completed_at']
            
        # Input parameters
        if prediction_data.get('input'):
            job['input_params'] = prediction_data['input']
            
        # Model information
        if model_url:
            if '/' in model_url:
                owner, model_name = model_url.split('/', 1)
                job['model_info'] = {
                    'model_owner': owner,
                    'model_name': model_name,
                    'model_url': model_url
                }
                
        if prediction_data.get('version'):
            if 'model_info' not in job:
                job['model_info'] = {}
            job['model_info']['model_version'] = prediction_data['version']
            
        # Execution logs and metrics
        if prediction_data.get('logs'):
            job['execution_logs'] = prediction_data['logs']
        if prediction_data.get('metrics'):
            job['metrics'] = prediction_data['metrics']
            
        # URLs
        if prediction_data.get('urls'):
            job['urls'] = prediction_data['urls']
            
        # Output data
        if prediction_data.get('output'):
            job['output_data'] = prediction_data['output']
        
        # Handle status-specific data
        if prediction_status == 'succeeded':
            output = prediction_data.get('output')
            result_url = None
            
            # Handle different output formats
            if isinstance(output, list) and len(output) > 0:
                result_url = output[0]
            elif isinstance(output, str):
                result_url = output
            
            if result_url:
                # Determine result type based on URL
                result_type = 'video' if any(ext in result_url.lower() for ext in ['.mp4', '.mov', '.webm']) else 'image'
                
                job.update({
                    'status': 'completed',
                    'result_urls': [result_url],
                    'result_type': result_type,
                    'primary_result_url': result_url,
                    'completed_at': prediction_data.get('completed_at', datetime.now(timezone.utc).isoformat())
                })
        
        elif prediction_status == 'failed':
            error_message = prediction_data.get('error', 'Job failed on Replicate')
            
            # Create structured error information
            error_details = {
                'category': 'replicate_error',
                'component': 'replicate',
                'original_error': error_message,
                'prediction_id': prediction_id
            }
            
            # Add model-specific error categorization
            if 'LoRA' in error_message or 'lora' in error_message.lower():
                error_details['component'] = 'lora'
                error_details['category'] = 'model_error'
            elif 'kling' in error_message.lower():
                error_details['component'] = 'kling'
                error_details['category'] = 'model_error'
            
            job.update({
                'status': 'failed',
                'error_message': error_message,
                'error_details': error_details
            })
        
        elif prediction_status in ['starting', 'processing']:
            job['status'] = 'processing'
        else:
            job['status'] = 'pending'
        
        return job
        
    except Exception as e:
        print(f"Error creating job from prediction: {str(e)}")
        return None

def handle_bootstrap_sync(predictions, content_jobs_table):
    """Bootstrap sync: Create job records from Replicate predictions"""
    try:
        created_count = 0
        bootstrap_results = []
        
        print(f"Creating jobs from {len(predictions)} Replicate predictions")
        
        for prediction in predictions:
            pred_id = prediction.get('id', 'unknown')
            pred_status = prediction.get('status', 'unknown')
            
            # Create job from prediction
            job = create_job_from_prediction(prediction)
            
            if job:
                try:
                    # Save job to DynamoDB
                    content_jobs_table.put_item(Item=job)
                    created_count += 1
                    
                    result = {
                        'job_id': job['job_id'],
                        'prediction_id': pred_id,
                        'status': pred_status,
                        'job_type': job.get('job_type', 'unknown'),
                        'character_name': job.get('character_name', 'Unknown'),
                        'created': True
                    }
                    
                    # Include error message if failed
                    if pred_status == 'failed':
                        result['error'] = prediction.get('error', 'Unknown error')
                    
                    # Include result URL if succeeded
                    if pred_status == 'succeeded' and job.get('primary_result_url'):
                        result['result_url'] = job['primary_result_url']
                    
                    bootstrap_results.append(result)
                    
                    print(f"Created job {job['job_id']} from prediction {pred_id} (Status: {pred_status})")
                    
                except Exception as e:
                    print(f"Error saving job for prediction {pred_id}: {str(e)}")
                    bootstrap_results.append({
                        'prediction_id': pred_id,
                        'status': pred_status,
                        'created': False,
                        'error': f'Failed to save job: {str(e)}'
                    })
            else:
                bootstrap_results.append({
                    'prediction_id': pred_id,
                    'status': pred_status,
                    'created': False,
                    'error': 'Failed to create job from prediction'
                })
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Bootstrap sync completed successfully',
                'mode': 'bootstrap',
                'predictions_processed': len(predictions),
                'jobs_created': created_count,
                'bootstrap_results': bootstrap_results
            }, default=decimal_default)
        }
        
    except Exception as e:
        print(f"Error during bootstrap sync: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': f'Bootstrap sync failed: {str(e)}'})
        }

def lambda_handler(event, context):
    """Main Lambda handler for syncing jobs with Replicate"""
    
    try:
        print("Starting Replicate job sync via API...")
        
        # Parse request
        http_method = event.get('httpMethod', 'POST')
        
        # Handle CORS preflight
        if http_method == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS'
                },
                'body': ''
            }
        
        if http_method != 'POST':
            return {
                'statusCode': 405,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Method not allowed'})
            }
        
        # Parse body for bootstrap mode
        bootstrap_mode = False
        if event.get('body'):
            try:
                body = json.loads(event['body'])
                bootstrap_mode = body.get('bootstrap', False)
            except:
                pass
        
        # Get API token
        api_token = get_secret(REPLICATE_API_TOKEN_SECRET)
        if not api_token:
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Could not retrieve Replicate API token'})
            }
        
        # Get all jobs from database
        content_jobs_table = dynamodb.Table(CONTENT_JOBS_TABLE_NAME)
        response = content_jobs_table.scan()
        jobs = response.get('Items', [])
        
        print(f"Found {len(jobs)} jobs in database")
        
        # Get ALL predictions from Replicate for disaster recovery
        max_predictions = 2000  # Configurable limit for disaster recovery
        predictions = get_replicate_predictions(api_token, max_predictions=max_predictions)
        print(f"Found {len(predictions)} total predictions on Replicate")
        
        # Bootstrap mode: Create jobs from Replicate predictions if database is empty
        if bootstrap_mode or len(jobs) == 0:
            print("Running in bootstrap mode - creating jobs from Replicate predictions")
            return handle_bootstrap_sync(predictions, content_jobs_table)
        
        # Match jobs with predictions and update
        matches = match_jobs_with_predictions(jobs, predictions)
        print(f"Found {len(matches)} job-prediction matches")
        
        updated_count = 0
        sync_results = []
        
        for job, prediction in matches:
            job_id = job.get('job_id', 'unknown')
            pred_id = prediction.get('id', 'unknown')
            old_status = job.get('status', 'unknown')
            new_status = prediction.get('status', 'unknown')
            
            print(f"Syncing job {job_id} with prediction {pred_id}")
            print(f"  Status: {old_status} -> {new_status}")
            
            if update_job_with_replicate_data(job, prediction):
                updated_count += 1
                
                result = {
                    'job_id': job_id,
                    'prediction_id': pred_id,
                    'old_status': old_status,
                    'new_status': new_status,
                    'updated': True
                }
                
                # Include error message if failed
                if new_status == 'failed':
                    error_msg = prediction.get('error', 'Unknown error')
                    result['error'] = error_msg
                    print(f"  Error: {error_msg}")
                
                sync_results.append(result)
            else:
                sync_results.append({
                    'job_id': job_id,
                    'prediction_id': pred_id,
                    'old_status': old_status,
                    'new_status': new_status,
                    'updated': False,
                    'error': 'Failed to update job'
                })
        
        # Also check for jobs with stored prediction IDs that weren't in recent predictions
        jobs_with_pred_ids = [job for job in jobs if job.get('replicate_prediction_id') and 
                             job.get('replicate_prediction_id') not in [p.get('id') for p in predictions]]
        
        for job in jobs_with_pred_ids:
            pred_id = job.get('replicate_prediction_id')
            prediction_data = get_replicate_prediction_status(pred_id, api_token)
            
            if prediction_data:
                job_id = job.get('job_id', 'unknown')
                old_status = job.get('status', 'unknown')
                new_status = prediction_data.get('status', 'unknown')
                
                print(f"Syncing job {job_id} with stored prediction {pred_id}")
                print(f"  Status: {old_status} -> {new_status}")
                
                if old_status != new_status:
                    if update_job_with_replicate_data(job, prediction_data):
                        updated_count += 1
                        
                        result = {
                            'job_id': job_id,
                            'prediction_id': pred_id,
                            'old_status': old_status,
                            'new_status': new_status,
                            'updated': True
                        }
                        
                        if new_status == 'failed':
                            error_msg = prediction_data.get('error', 'Unknown error')
                            result['error'] = error_msg
                            print(f"  Error: {error_msg}")
                        
                        sync_results.append(result)
        
        print(f"Sync complete: {updated_count} jobs updated")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Sync completed successfully',
                'jobs_processed': len(jobs),
                'predictions_checked': len(predictions),
                'jobs_updated': updated_count,
                'sync_results': sync_results
            }, default=decimal_default)
        }
        
    except Exception as e:
        print(f"Error during sync: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': f'Sync failed: {str(e)}'})
        }
