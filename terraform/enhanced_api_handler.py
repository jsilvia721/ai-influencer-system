import json
import boto3
import os
from datetime import datetime
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
lambda_client = boto3.client('lambda')
s3_client = boto3.client('s3')
secrets_client = boto3.client('secretsmanager')

def lambda_handler(event, context):
    """
    Enhanced API Gateway Lambda handler for AI Influencer System
    Handles all API routes and operations
    """
    try:
        # Get request details
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '/')
        query_params = event.get('queryStringParameters') or {}
        body = event.get('body')
        
        logger.info(f"Request: {http_method} {path}")
        
        # Parse body if present
        request_data = {}
        if body:
            try:
                request_data = json.loads(body)
            except json.JSONDecodeError:
                return create_response(400, {'error': 'Invalid JSON in request body'})
        
        # Route handling
        if path == '/' or path == '':
            return handle_health_check()
        elif path == '/characters':
            return handle_characters(http_method, request_data, query_params)
        elif path == '/content':
            return handle_content(http_method, request_data, query_params)
        elif path == '/generate':
            return handle_generate_content(http_method, request_data)
        elif path == '/generate-training-images':
            return handle_generate_training_images(http_method, request_data)
        elif path == '/schedule':
            return handle_schedule(http_method, request_data)
        elif path == '/status':
            return handle_status(query_params)
        else:
            return create_response(404, {'error': 'Endpoint not found'})
            
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return create_response(500, {'error': 'Internal server error'})

def create_response(status_code, body, headers=None):
    """Create a standardized API response"""
    default_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization'
    }
    
    if headers:
        default_headers.update(headers)
    
    return {
        'statusCode': status_code,
        'headers': default_headers,
        'body': json.dumps(body, indent=2)
    }

def handle_health_check():
    """Health check endpoint"""
    return create_response(200, {
        'message': 'AI Influencer System API',
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0-mvp'
    })

def handle_characters(method, data, params):
    """Handle character management endpoints"""
    if method == 'GET':
        # Return list of characters
        characters = [
            {
                'id': 'char-1',
                'name': 'Tech Influencer',
                'persona': 'Technology enthusiast and early adopter',
                'platforms': ['twitter', 'instagram'],
                'status': 'active'
            },
            {
                'id': 'char-2', 
                'name': 'Lifestyle Guru',
                'persona': 'Health, wellness, and lifestyle content creator',
                'platforms': ['instagram', 'twitter'],
                'status': 'active'
            },
            {
                'id': 'char-3',
                'name': 'Business Coach',
                'persona': 'Entrepreneurship and business growth expert',
                'platforms': ['twitter', 'instagram'],
                'status': 'active'
            }
        ]
        return create_response(200, {'characters': characters})
    
    elif method == 'POST':
        # Create new character (placeholder)
        return create_response(201, {
            'message': 'Character creation endpoint',
            'note': 'Implementation pending - will create new AI character'
        })
    
    return create_response(405, {'error': 'Method not allowed'})

def handle_content(method, data, params):
    """Handle content management endpoints"""
    if method == 'GET':
        # Get content history
        character_id = params.get('character_id')
        limit = int(params.get('limit', 10))
        
        # Simulate content retrieval
        content_list = []
        for i in range(min(limit, 5)):  # Simulate some content
            content_list.append({
                'id': f'content-{i+1}',
                'character_id': character_id or 'char-1',
                'type': 'text',
                'content': f'Sample AI-generated content {i+1}',
                'platforms': ['twitter', 'instagram'],
                'status': 'published',
                'created_at': datetime.utcnow().isoformat()
            })
        
        return create_response(200, {
            'content': content_list,
            'total': len(content_list)
        })
    
    return create_response(405, {'error': 'Method not allowed'})

def handle_generate_content(method, data):
    """Handle content generation requests"""
    if method == 'POST':
        character_id = data.get('character_id', 'char-1')
        content_type = data.get('type', 'text')
        prompt = data.get('prompt', '')
        
        # Invoke content generator Lambda
        try:
            payload = {
                'character_id': character_id,
                'content_type': content_type,
                'prompt': prompt,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            response = lambda_client.invoke(
                FunctionName=os.environ.get('CONTENT_GENERATOR_FUNCTION', 
                                           'ai-influencer-system-dev-content-generator'),
                InvocationType='Event',  # Async invocation
                Payload=json.dumps(payload)
            )
            
            return create_response(202, {
                'message': 'Content generation started',
                'job_id': f'job-{datetime.utcnow().timestamp()}',
                'character_id': character_id,
                'type': content_type
            })
            
        except Exception as e:
            logger.error(f"Error invoking content generator: {str(e)}")
            return create_response(500, {'error': 'Failed to start content generation'})
    
    return create_response(405, {'error': 'Method not allowed'})

def handle_generate_training_images(method, data):
    """Handle training image generation requests"""
    if method == 'POST':
        character_description = data.get('character_description', '')
        character_name = data.get('character_name', 'character')
        
        if not character_description:
            return create_response(400, {'error': 'character_description is required'})
        
        # Invoke training image generator Lambda
        try:
            payload = {
                'character_description': character_description,
                'character_name': character_name,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            response = lambda_client.invoke(
                FunctionName=os.environ.get('TRAINING_IMAGE_GENERATOR_FUNCTION', 
                                           'ai-influencer-mvp-dev-training-image-generator'),
                InvocationType='Event',  # Async invocation
                Payload=json.dumps(payload)
            )
            
            return create_response(202, {
                'message': 'Training image generation started',
                'job_id': f'training-job-{datetime.utcnow().timestamp()}',
                'character_name': character_name,
                'character_description': character_description,
                'expected_images': 25,
                'estimated_completion': '10-15 minutes'
            })
            
        except Exception as e:
            logger.error(f"Error invoking training image generator: {str(e)}")
            return create_response(500, {'error': 'Failed to start training image generation'})
    
    return create_response(405, {'error': 'Method not allowed'})

def handle_schedule(method, data):
    """Handle scheduling endpoints"""
    if method == 'GET':
        return create_response(200, {
            'schedule': {
                'daily_generation': 'cron(0 8 * * ? *)',  # 8 AM daily
                'status': 'active',
                'next_run': 'Next run at 8:00 AM UTC'
            }
        })
    
    elif method == 'POST':
        return create_response(200, {
            'message': 'Schedule update endpoint',
            'note': 'Implementation pending - will update content generation schedule'
        })
    
    return create_response(405, {'error': 'Method not allowed'})

def handle_status(params):
    """Handle system status endpoint"""
    try:
        # Check S3 bucket
        bucket_name = os.environ.get('S3_BUCKET', '')
        s3_status = 'unknown'
        
        if bucket_name:
            try:
                s3_client.head_bucket(Bucket=bucket_name)
                s3_status = 'healthy'
            except:
                s3_status = 'error'
        
        # Check database Lambda
        db_function = os.environ.get('DATABASE_LAMBDA', '')
        db_status = 'unknown'
        
        if db_function:
            try:
                lambda_client.get_function(FunctionName=db_function)
                db_status = 'healthy'
            except:
                db_status = 'error'
        
        return create_response(200, {
            'system_status': 'operational',
            'components': {
                'api': 'healthy',
                's3_storage': s3_status,
                'database': db_status,
                'content_generator': 'healthy',
                'social_poster': 'healthy'
            },
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return create_response(500, {'error': f'Status check failed: {str(e)}'})
