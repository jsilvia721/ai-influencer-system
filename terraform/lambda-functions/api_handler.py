import json
import boto3
import os

def handler(event, context):
    """
    Enhanced API handler for AI Influencer System with character-consistent media generation
    Handles all API Gateway requests including LoRA training and Flux/Kling integration
    """
    
    # Get path and method from API Gateway event
    path = event.get('path', '/')
    method = event.get('httpMethod', 'GET')
    
    # Standard headers for all responses
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization'
    }
    
    # Handle CORS preflight requests
    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': headers,
            'body': ''
        }
    
    # Lambda client for invoking other functions
    lambda_client = boto3.client('lambda')
    
    try:
        # Route based on path and method
        if path == '/' and method == 'GET':
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({
                    'message': 'AI Influencer System API - Character-Consistent Content Generation',
                    'version': '2.0.0',
                    'features': ['LoRA Character Models', 'Flux Image Generation', 'Kling Video Generation'],
                    'endpoints': {
                        'Character Management': {
                            'POST /characters': 'Create new character model',
                            'GET /characters': 'List all characters',
                            'GET /characters/{id}': 'Get character details',
                            'PUT /characters/{id}': 'Update character'
                        },
                        'Content Generation': {
                            'POST /generate/image': 'Generate character-consistent image',
                            'POST /generate/video': 'Generate character-consistent video',
                            'GET /generate/status/{job_id}': 'Check generation status'
                        },
                        'LoRA Training': {
                            'POST /training/start': 'Start LoRA model training',
                            'GET /training/status/{job_id}': 'Check training status'
                        },
                        'Social Media': {
                            'POST /post': 'Post to social media'
                        }
                    }
                })
            }
        
        # Character Management Endpoints
        elif path == '/characters' and method == 'GET':
            return invoke_lambda_function(
                lambda_client,
                os.environ.get('CHARACTER_MODEL_MANAGER_FUNCTION'),
                {'action': 'list_characters'},
                headers
            )
        
        elif path == '/characters' and method == 'POST':
            return invoke_lambda_function(
                lambda_client,
                os.environ.get('CHARACTER_MODEL_MANAGER_FUNCTION'),
                parse_request_body(event, {'action': 'create_character'}),
                headers
            )
        
        elif path.startswith('/characters/') and method == 'GET':
            character_id = path.split('/')[-1]
            return invoke_lambda_function(
                lambda_client,
                os.environ.get('CHARACTER_MODEL_MANAGER_FUNCTION'),
                {'action': 'get_character', 'character_id': character_id},
                headers
            )
        
        # Image Generation Endpoints
        elif path == '/generate/image' and method == 'POST':
            return invoke_lambda_function(
                lambda_client,
                os.environ.get('CHARACTER_MEDIA_GENERATOR_FUNCTION'),
                parse_request_body(event, {'action': 'generate_image'}),
                headers
            )
        
        # Video Generation Endpoints
        elif path == '/generate/video' and method == 'POST':
            return invoke_lambda_function(
                lambda_client,
                os.environ.get('CHARACTER_MEDIA_GENERATOR_FUNCTION'),
                parse_request_body(event, {'action': 'generate_video'}),
                headers
            )
        
        # Generation Status Check
        elif path.startswith('/generate/status/') and method == 'GET':
            job_id = path.split('/')[-1]
            return invoke_lambda_function(
                lambda_client,
                os.environ.get('CHARACTER_MEDIA_GENERATOR_FUNCTION'),
                {'action': 'check_status', 'job_id': job_id},
                headers
            )
        
        # LoRA Training Endpoints
        elif path == '/training/start' and method == 'POST':
            return invoke_lambda_function(
                lambda_client,
                os.environ.get('LORA_TRAINING_SERVICE_FUNCTION'),
                parse_request_body(event, {'action': 'start_training'}),
                headers
            )
        
        elif path.startswith('/training/status/') and method == 'GET':
            job_id = path.split('/')[-1]
            return invoke_lambda_function(
                lambda_client,
                os.environ.get('LORA_TRAINING_SERVICE_FUNCTION'),
                {'action': 'check_status', 'job_id': job_id},
                headers
            )
        
        # Social Media Posting
        elif path == '/post' and method == 'POST':
            return invoke_lambda_function(
                lambda_client,
                os.environ.get('SOCIAL_POSTER_FUNCTION'),
                parse_request_body(event),
                headers
            )
        
        else:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Endpoint not found',
                    'path': path,
                    'method': method,
                    'message': 'Check the API documentation for available endpoints'
                })
            }
    
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }

def parse_request_body(event, default_payload=None):
    """Parse and return request body, handling both string and dict formats"""
    try:
        body = event.get('body', '{}')
        if isinstance(body, str):
            parsed_body = json.loads(body) if body else {}
        else:
            parsed_body = body or {}
        
        # Merge with default payload if provided
        if default_payload:
            parsed_body.update(default_payload)
        
        return parsed_body
    except json.JSONDecodeError:
        return default_payload or {}

def invoke_lambda_function(lambda_client, function_name, payload, headers):
    """Helper function to invoke another Lambda function and handle the response"""
    try:
        if not function_name:
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Function not configured',
                    'message': 'The required Lambda function is not properly configured'
                })
            }
        
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        # Parse the response
        response_payload = json.loads(response['Payload'].read())
        
        # If the invoked function returned a proper API Gateway response, use it
        if 'statusCode' in response_payload:
            response_payload['headers'] = headers  # Ensure CORS headers
            return response_payload
        
        # Otherwise, wrap the response
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(response_payload)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': 'Lambda invocation failed',
                'message': str(e)
            })
        }
