import json
import boto3
import os
import uuid
from datetime import datetime
from typing import Dict, Any

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for API Gateway requests
    """
    print(f"Received event: {json.dumps(event)}")
    
    # Extract request details
    http_method = event.get('httpMethod', 'GET')
    path = event.get('path', '/')
    body = event.get('body')
    
    # Parse request body if present
    request_data = {}
    if body:
        try:
            request_data = json.loads(body)
        except json.JSONDecodeError:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS'
                },
                'body': json.dumps({'error': 'Invalid JSON in request body'})
            }
    
    # CORS preflight handling
    if http_method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS'
            },
            'body': ''
        }
    
    # Route requests
    try:
        if path == '/characters' and http_method == 'GET':
            return handle_get_characters()
        elif path == '/characters' and http_method == 'POST':
            return handle_create_character(request_data)
        elif path.startswith('/characters/') and http_method == 'DELETE':
            character_id = path.split('/')[-1]
            return handle_delete_character(character_id)
        elif path == '/generate-training-images' and http_method == 'POST':
            return handle_generate_training_images(request_data)
        elif path.startswith('/training-jobs/') and http_method == 'GET':
            job_id = path.split('/')[-1]
            return handle_get_job_status(job_id)
        elif path == '/training-jobs' and http_method == 'GET':
            return handle_get_all_jobs()
        elif path == '/train-lora' and http_method == 'POST':
            return handle_train_lora(request_data)
        elif path.startswith('/lora-training-status/') and http_method == 'GET':
            job_id = path.split('/')[-1]
            return handle_get_lora_training_status(job_id)
        elif path == '/lora-training-jobs' and http_method == 'GET':
            return handle_get_lora_training_jobs(request_data)
        elif path == '/lora-training' and http_method == 'POST':
            return handle_train_lora(request_data)
        elif path == '/training-images' and http_method == 'GET':
            return handle_get_training_images()
        elif path == '/replicate-webhook' and http_method == 'POST':
            return handle_replicate_webhook(event)
        elif path == '/generate-content' and http_method == 'POST':
            return handle_generate_content(request_data)
        elif path.startswith('/content-jobs/') and http_method == 'GET':
            job_id = path.split('/')[-1]
            return handle_get_content_job_status(job_id)
        elif path == '/content-jobs' and http_method == 'GET':
            return handle_list_content_jobs(request_data)
        elif path == '/sync-replicate' and http_method == 'POST':
            return handle_sync_replicate()
        else:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': f'Endpoint not found: {http_method} {path}'})
            }
            
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Internal server error'})
        }

def handle_get_characters():
    """Handle GET /characters"""
    try:
        # Initialize DynamoDB client
        dynamodb = boto3.resource('dynamodb')
        table_name = os.environ.get('CHARACTERS_TABLE_NAME', 'ai-influencer-characters')
        table = dynamodb.Table(table_name)
        
        # Scan the table to get all characters
        response = table.scan()
        characters = response.get('Items', [])
        
        # Convert Decimal types to native Python types for JSON serialization
        import decimal
        def decimal_default(obj):
            if isinstance(obj, decimal.Decimal):
                return float(obj)
            raise TypeError
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'data': characters}, default=decimal_default)
        }
        
    except Exception as e:
        print(f"Error retrieving characters: {str(e)}")
        # Return empty list if table doesn't exist or other error
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'data': []})
        }

def handle_create_character(request_data: Dict[str, Any]):
    """Handle POST /characters"""
    # Validate required fields
    required_fields = ['name', 'description', 'training_images']
    for field in required_fields:
        if field not in request_data:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': f'Missing required field: {field}'})
            }
    
    try:
        # Initialize DynamoDB client
        dynamodb = boto3.resource('dynamodb')
        table_name = os.environ.get('CHARACTERS_TABLE_NAME', 'ai-influencer-characters')
        
        # Try to get the table, create if it doesn't exist
        try:
            table = dynamodb.Table(table_name)
            table.load()  # This will raise an exception if table doesn't exist
        except dynamodb.meta.client.exceptions.ResourceNotFoundException:
            # Create the table if it doesn't exist
            table = dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {
                        'AttributeName': 'id',
                        'KeyType': 'HASH'
                    }
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'id',
                        'AttributeType': 'S'
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            # Wait for table to be created
            table.meta.client.get_waiter('table_exists').wait(TableName=table_name)
        
        # Generate character ID and timestamp
        character_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()
        
        # Prepare character data for DynamoDB
        character_item = {
            'id': character_id,
            'name': request_data['name'],
            'description': request_data['description'],
            'style': request_data.get('style', ''),
            'personality': request_data.get('personality', ''),
            'training_status': 'pending',
            'created_at': created_at,
            'training_images_count': len(request_data['training_images']),
            'selected_training_images': []  # Will be populated after S3 upload
        }
        
        # Save character to DynamoDB
        table.put_item(Item=character_item)
        
        # Upload training images to S3 and start LoRA training
        try:
            # Upload training images to S3 and get the URLs of selected images
            selected_image_urls = upload_training_images_to_s3(character_id, request_data['training_images'])
            
            # Update character record with selected training image URLs
            table.update_item(
                Key={'id': character_id},
                UpdateExpression="SET selected_training_images = :images",
                ExpressionAttributeValues={':images': selected_image_urls}
            )
            
            # Start LoRA training process
            start_lora_training(character_id)
            
        except Exception as training_error:
            print(f"Error starting training for character {character_id}: {str(training_error)}")
            # Update character status to indicate training failed to start
            table.update_item(
                Key={'id': character_id},
                UpdateExpression="SET training_status = :status",
                ExpressionAttributeValues={':status': 'failed'}
            )
        
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Character created successfully',
                'character_id': character_id,
                'character': character_item
            })
        }
        
    except Exception as e:
        print(f"Error creating character: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Failed to create character'})
        }

def handle_delete_character(character_id: str):
    """Handle DELETE /characters/{id}"""
    try:
        # Initialize DynamoDB client
        dynamodb = boto3.resource('dynamodb')
        table_name = os.environ.get('CHARACTERS_TABLE_NAME', 'ai-influencer-characters')
        table = dynamodb.Table(table_name)
        
        # Delete the character from DynamoDB
        table.delete_item(
            Key={'id': character_id}
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': f'Character {character_id} deleted successfully'})
        }
        
    except Exception as e:
        print(f"Error deleting character: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Failed to delete character'})
        }

def handle_generate_training_images(request_data: Dict[str, Any]):
    """Handle POST /generate-training-images"""
    # Validate required fields
    required_fields = ['character_name', 'character_description']
    for field in required_fields:
        if field not in request_data:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': f'Missing required field: {field}'})
            }
    
    # Invoke the training image generator Lambda
    try:
        lambda_client = boto3.client('lambda')
        
        # Get the training image generator function name from environment
        training_lambda_name = os.environ.get('TRAINING_IMAGE_GENERATOR_FUNCTION_NAME', 
                                            'ai-influencer-system-dev-training-image-generator')
        
        # Prepare payload for training image generator
        payload = {
            'character_name': request_data['character_name'],
            'character_description': request_data['character_description'],
            'character_id': request_data.get('character_id'),  # Optional character ID for organization
            'num_images': request_data.get('num_images', 15)  # Default to 15 images to save costs
        }
        
        # Generate a job ID here to return immediately
        job_id = str(uuid.uuid4())
        
        # Add job_id to the payload so the Lambda can use it
        payload['job_id'] = job_id
        
        # Invoke the training image generator Lambda asynchronously to avoid timeouts
        response = lambda_client.invoke(
            FunctionName=training_lambda_name,
            InvocationType='Event',  # Asynchronous to avoid API Gateway timeout
            Payload=json.dumps(payload)
        )
        
        # Return immediately with the job ID
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Training image generation started',
                'job_id': job_id,
                'status': 'processing',
                'total_requested': payload.get('num_images', 15)
            })
        }
        
    except Exception as e:
        print(f"Error invoking training image generator: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Failed to start training image generation'})
        }

def handle_get_job_status(job_id: str):
    """Handle GET /training-jobs/{job_id}"""
    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('ai-influencer-training-jobs')
        
        response = table.get_item(Key={'job_id': job_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Job not found'})
            }
        
        job = response['Item']
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'data': {
                    'job_id': job['job_id'],
                    'character_name': job['character_name'],
                    'status': job['status'],
                    'total_images': job.get('total_images', 0),
                    'completed_images': job.get('completed_images', 0),
                    'image_urls': job.get('image_urls', [])
                }
            })
        }
        
    except Exception as e:
        print(f"Error getting job status: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Failed to get job status'})
        }

def handle_get_all_jobs():
    """Handle GET /training-jobs"""
    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('ai-influencer-training-jobs')
        
        response = table.scan()
        jobs = response.get('Items', [])
        
        # Format jobs for frontend
        formatted_jobs = []
        for job in jobs:
            formatted_jobs.append({
                'job_id': job['job_id'],
                'character_name': job['character_name'],
                'status': job['status'],
                'total_images': job.get('total_images', 0),
                'completed_images': job.get('completed_images', 0),
                'image_urls': job.get('image_urls', [])
            })
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'data': formatted_jobs})
        }
        
    except Exception as e:
        print(f"Error getting all jobs: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Failed to get jobs'})
        }

def handle_train_lora(request_data: Dict[str, Any]):
    """Handle POST /train-lora"""
    # Validate required fields
    required_fields = ['character_id']
    for field in required_fields:
        if field not in request_data:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': f'Missing required field: {field}'})
            }
    
    # Invoke the LoRA model trainer Lambda
    try:
        lambda_client = boto3.client('lambda')
        
        # Get the LoRA trainer function name from environment
        lora_trainer_lambda_name = os.environ.get('LORA_TRAINER_FUNCTION_NAME', 
                                                'ai-influencer-system-dev-lora-trainer')
        
        # Prepare payload for LoRA trainer
        payload = {
            'action': 'train',
            'character_id': request_data['character_id']
        }
        
        # Invoke the LoRA trainer Lambda asynchronously
        response = lambda_client.invoke(
            FunctionName=lora_trainer_lambda_name,
            InvocationType='RequestResponse',  # Synchronous to get job ID
            Payload=json.dumps(payload)
        )
        
        # Parse response from LoRA trainer
        response_payload = json.loads(response['Payload'].read())
        
        if response['StatusCode'] == 200:
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': response_payload['body']
            }
        else:
            return {
                'statusCode': response['StatusCode'],
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': response_payload.get('body', json.dumps({'error': 'LoRA training failed'}))
            }
        
    except Exception as e:
        print(f"Error invoking LoRA trainer: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Failed to start LoRA training'})
        }

def handle_get_lora_training_status(job_id: str):
    """Handle GET /lora-training-status/{job_id}"""
    try:
        lambda_client = boto3.client('lambda')
        
        # Get the LoRA trainer function name from environment
        lora_trainer_lambda_name = os.environ.get('LORA_TRAINER_FUNCTION_NAME', 
                                                'ai-influencer-system-dev-lora-trainer')
        
        # Prepare payload for status check
        payload = {
            'action': 'status',
            'job_id': job_id
        }
        
        # Invoke the LoRA trainer Lambda
        response = lambda_client.invoke(
            FunctionName=lora_trainer_lambda_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        # Parse response from LoRA trainer
        response_payload = json.loads(response['Payload'].read())
        
        return {
            'statusCode': response['StatusCode'],
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': response_payload.get('body', json.dumps({'error': 'Failed to get status'}))
        }
        
    except Exception as e:
        print(f"Error getting LoRA training status: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Failed to get LoRA training status'})
        }

def handle_get_lora_training_jobs(request_data: Dict[str, Any]):
    """Handle GET /lora-training-jobs"""
    try:
        lambda_client = boto3.client('lambda')
        
        # Get the LoRA trainer function name from environment
        lora_trainer_lambda_name = os.environ.get('LORA_TRAINER_FUNCTION_NAME', 
                                                'ai-influencer-system-dev-lora-trainer')
        
        # Prepare payload for job listing
        payload = {
            'action': 'list',
            'character_id': request_data.get('character_id')  # Optional filter
        }
        
        # Invoke the LoRA trainer Lambda
        response = lambda_client.invoke(
            FunctionName=lora_trainer_lambda_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        # Parse response from LoRA trainer
        response_payload = json.loads(response['Payload'].read())
        
        return {
            'statusCode': response['StatusCode'],
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': response_payload.get('body', json.dumps({'error': 'Failed to get jobs'}))
        }
        
    except Exception as e:
        print(f"Error getting LoRA training jobs: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Failed to get LoRA training jobs'})
        }

def handle_get_training_images():
    """Handle GET /training-images - Fetch all training images from S3"""
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ.get('S3_BUCKET_NAME', 'ai-influencer-system-dev-content-bkdeyg')
        
        # List objects in the training-images folder
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix='training-images/'
        )
        
        # Group images by job ID (folder name)
        images_by_job = {}
        
        if 'Contents' in response:
            for obj in response['Contents']:
                key = obj['Key']
                # Extract job ID from path: training-images/{job_id}/{filename}
                path_parts = key.split('/')
                if len(path_parts) >= 3 and path_parts[0] == 'training-images':
                    job_id = path_parts[1]
                    filename = path_parts[2]
                    
                    # Skip folders or non-image files
                    if not filename or not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')):
                        continue
                    
                    # Generate presigned URL for the image
                    image_url = s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': bucket_name, 'Key': key},
                        ExpiresIn=3600  # 1 hour expiration
                    )
                    
                    if job_id not in images_by_job:
                        images_by_job[job_id] = {
                            'job_id': job_id,
                            'images': [],
                            'character_name': '',  # We'll try to extract this from filename
                            'total_images': 0,
                            'last_modified': obj['LastModified'],
                            'created_date': obj['LastModified'].strftime('%Y-%m-%d %H:%M UTC')
                        }
                    
                    # Update last modified to the most recent file in this job
                    if obj['LastModified'] > images_by_job[job_id]['last_modified']:
                        images_by_job[job_id]['last_modified'] = obj['LastModified']
                        images_by_job[job_id]['created_date'] = obj['LastModified'].strftime('%Y-%m-%d %H:%M UTC')
                    
                    # Try to extract character name from filename
                    if '_training_' in filename:
                        character_name = filename.split('_training_')[0].replace('_', ' ')
                        images_by_job[job_id]['character_name'] = character_name
                    
                    images_by_job[job_id]['images'].append({
                        'filename': filename,
                        'url': image_url,
                        'size': obj.get('Size', 0),
                        'last_modified': obj['LastModified'].isoformat()
                    })
                    images_by_job[job_id]['total_images'] = len(images_by_job[job_id]['images'])
        
        # Convert to list format and sort by last_modified (newest first)
        training_jobs = list(images_by_job.values())
        training_jobs.sort(key=lambda x: x['last_modified'], reverse=True)
        
        # Sort images within each job by filename to maintain consistent order
        for job in training_jobs:
            job['images'].sort(key=lambda x: x['filename'])
            # Remove the datetime object since it's not JSON serializable
            del job['last_modified']
        
        # Also get all image URLs in a flat list for the UI to use
        all_image_urls = []
        for job_data in training_jobs:
            for image in job_data['images']:
                all_image_urls.append(image['url'])
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'data': {
                    'training_jobs': training_jobs,
                    'all_image_urls': all_image_urls,
                    'total_jobs': len(training_jobs),
                    'total_images': len(all_image_urls)
                }
            })
        }
        
    except Exception as e:
        print(f"Error fetching training images from S3: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Failed to fetch training images'})
        }

def upload_training_images_to_s3(character_id: str, training_images: list):
    """Upload training images to S3 and return list of uploaded/selected image URLs"""
    import base64
    
    s3_client = boto3.client('s3')
    bucket_name = os.environ.get('S3_BUCKET_NAME', 'ai-influencer-system-dev-content-bkdeyg')
    
    selected_image_urls = []
    uploaded_count = 0
    
    for i, image_data in enumerate(training_images):
        try:
            # Handle both base64 strings and URLs
            if image_data.startswith('http'):
                # This is a URL (likely from S3) - add it to selected list
                selected_image_urls.append(image_data)
                print(f"Using existing S3 image {i+1}: {image_data}")
            else:
                # This is base64 encoded image data
                # Decode base64 image
                image_bytes = base64.b64decode(image_data)
                
                # Generate S3 key
                s3_key = f"training-images/{character_id}/image_{i+1:03d}.jpg"
                
                # Upload to S3
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=s3_key,
                    Body=image_bytes,
                    ContentType='image/jpeg'
                )
                
                # Generate presigned URL for the uploaded image
                image_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket_name, 'Key': s3_key},
                    ExpiresIn=3600 * 24  # 24 hours
                )
                
                selected_image_urls.append(image_url)
                uploaded_count += 1
                print(f"Uploaded training image {i+1} to S3: {s3_key}")
                
        except Exception as e:
            print(f"Error processing training image {i+1}: {str(e)}")
            continue
    
    print(f"Successfully processed {len(selected_image_urls)} training images for character {character_id} ({uploaded_count} uploaded, {len(selected_image_urls) - uploaded_count} existing URLs)")
    return selected_image_urls

def handle_replicate_webhook(event: Dict[str, Any]):
    """Handle POST /replicate-webhook - Process Replicate webhook notifications"""
    try:
        # Invoke the dedicated webhook handler Lambda
        lambda_client = boto3.client('lambda')
        
        # Get the webhook handler function name from environment
        webhook_handler_lambda_name = os.environ.get('REPLICATE_WEBHOOK_HANDLER_FUNCTION_NAME', 
                                                     'ai-influencer-system-dev-replicate-webhook-handler')
        
        # Forward the entire event to the webhook handler
        response = lambda_client.invoke(
            FunctionName=webhook_handler_lambda_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(event)
        )
        
        # Parse response from webhook handler
        response_payload = json.loads(response['Payload'].read())
        
        return {
            'statusCode': response['StatusCode'],
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': response_payload.get('body', json.dumps({'error': 'Webhook processing failed'}))
        }
        
    except Exception as e:
        print(f"Error processing Replicate webhook: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Failed to process webhook'})
        }

def handle_generate_content(request_data: Dict[str, Any]):
    """Handle POST /generate-content - Generate images and videos using LoRA + Kling"""
    try:
        # Invoke the content generation service Lambda
        lambda_client = boto3.client('lambda')
        
        # Get the content generation service function name from environment
        content_generation_lambda_name = os.environ.get('CONTENT_GENERATION_SERVICE_FUNCTION_NAME', 
                                                       'ai-influencer-system-dev-content-generation-service')
        
        # Map the mode to the appropriate action for the content generation service
        mode = request_data.get('mode', 'full_pipeline')
        if mode == 'image_only':
            action = 'generate_image'
            payload = {
                'action': action,
                'character_id': request_data.get('character_id'),
                'prompt': request_data.get('image_prompt', request_data.get('prompt', ''))
            }
        elif mode == 'video_only':
            action = 'generate_video'
            payload = {
                'action': action,
                'character_id': request_data.get('character_id'),
                'image_url': request_data.get('image_url'),
                'prompt': request_data.get('video_prompt', request_data.get('prompt', ''))
            }
        else:  # full_pipeline or default
            action = 'generate_complete_content'
            payload = {
                'action': action,
                'character_id': request_data.get('character_id'),
                'prompt': request_data.get('image_prompt', request_data.get('prompt', ''))
            }
        
        # Forward the request to the content generation service
        response = lambda_client.invoke(
            FunctionName=content_generation_lambda_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        # Parse response from content generation service
        response_payload = json.loads(response['Payload'].read())
        
        return {
            'statusCode': response['StatusCode'],
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': response_payload.get('body', json.dumps({'error': 'Content generation failed'}))
        }
        
    except Exception as e:
        print(f"Error processing content generation: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Failed to generate content'})
        }

def handle_get_content_job_status(job_id: str):
    """Handle GET /content-jobs/{job_id} - Get content generation job status"""
    try:
        # Invoke the content generation service Lambda
        lambda_client = boto3.client('lambda')
        
        # Get the content generation service function name from environment
        content_generation_lambda_name = os.environ.get('CONTENT_GENERATION_SERVICE_FUNCTION_NAME', 
                                                       'ai-influencer-system-dev-content-generation-service')
        
        # Prepare payload for status check
        payload = {
            'action': 'status',
            'job_id': job_id
        }
        
        # Invoke the content generation service
        response = lambda_client.invoke(
            FunctionName=content_generation_lambda_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        # Parse response from content generation service
        response_payload = json.loads(response['Payload'].read())
        
        return {
            'statusCode': response['StatusCode'],
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': response_payload.get('body', json.dumps({'error': 'Failed to get job status'}))
        }
        
    except Exception as e:
        print(f"Error getting content job status: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Failed to get content job status'})
        }

def handle_list_content_jobs(request_data: Dict[str, Any]):
    """Handle GET /content-jobs - List content generation jobs"""
    try:
        # Invoke the content generation service Lambda
        lambda_client = boto3.client('lambda')
        
        # Get the content generation service function name from environment
        content_generation_lambda_name = os.environ.get('CONTENT_GENERATION_SERVICE_FUNCTION_NAME', 
                                                       'ai-influencer-system-dev-content-generation-service')
        
        # Prepare payload for job listing
        payload = {
            'action': 'list',
            'character_id': request_data.get('character_id')  # Optional filter
        }
        
        # Invoke the content generation service
        response = lambda_client.invoke(
            FunctionName=content_generation_lambda_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        # Parse response from content generation service
        response_payload = json.loads(response['Payload'].read())
        
        return {
            'statusCode': response['StatusCode'],
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': response_payload.get('body', json.dumps({'error': 'Failed to list content jobs'}))
        }
        
    except Exception as e:
        print(f"Error listing content jobs: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Failed to list content jobs'})
        }

def handle_sync_replicate():
    """Handle POST /sync-replicate - Sync all content generation jobs with Replicate"""
    try:
        # Invoke the sync service Lambda
        lambda_client = boto3.client('lambda')
        
        # Get the sync service function name from environment
        sync_lambda_name = os.environ.get('SYNC_REPLICATE_FUNCTION_NAME', 
                                         'ai-influencer-system-dev-sync-replicate-jobs')
        
        # Invoke the sync service
        response = lambda_client.invoke(
            FunctionName=sync_lambda_name,
            InvocationType='RequestResponse',
            Payload=json.dumps({'action': 'sync'})
        )
        
        # Parse response from sync service
        response_payload = json.loads(response['Payload'].read())
        
        return {
            'statusCode': response['StatusCode'],
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': response_payload.get('body', json.dumps({'error': 'Sync failed'}))
        }
        
    except Exception as e:
        print(f"Error syncing with Replicate: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': f'Failed to sync with Replicate: {str(e)}'})
        }

def start_lora_training(character_id: str):
    """Start LoRA training for a character"""
    try:
        lambda_client = boto3.client('lambda')
        
        # Get the LoRA training service function name from environment
        lora_training_lambda_name = os.environ.get('LORA_TRAINING_SERVICE_FUNCTION_NAME', 
                                                  'ai-influencer-system-dev-lora-training-service')
        
        # Prepare payload for LoRA training
        payload = {
            'action': 'train',
            'character_id': character_id
        }
        
        # Invoke the LoRA training service Lambda asynchronously
        response = lambda_client.invoke(
            FunctionName=lora_training_lambda_name,
            InvocationType='Event',  # Asynchronous invocation
            Payload=json.dumps(payload)
        )
        
        print(f"Started LoRA training for character {character_id}")
        return True
        
    except Exception as e:
        print(f"Error starting LoRA training for character {character_id}: {str(e)}")
        raise e
