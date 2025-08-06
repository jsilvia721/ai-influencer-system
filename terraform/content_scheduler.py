import json
import os
import boto3
from datetime import datetime

def handler(event, context):
    """
    Lambda function to schedule daily content generation
    """
    print(f"Content scheduler triggered at {datetime.now()}")
    
    # Get environment variables
    database_url = os.environ.get('DATABASE_URL')
    s3_bucket = os.environ.get('S3_BUCKET')
    sqs_queues = json.loads(os.environ.get('SQS_QUEUES', '[]'))
    
    print(f"Database URL: {database_url}")
    print(f"S3 Bucket: {s3_bucket}")
    print(f"SQS Queues: {len(sqs_queues)}")
    
    # Initialize SQS client
    sqs = boto3.client('sqs')
    
    # Send messages to each character's queue
    for i, queue_config in enumerate(sqs_queues):
        character_id = i + 1
        
        # Send image generation message
        image_message = {
            'character_id': character_id,
            'task_type': 'image_generation',
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            sqs.send_message(
                QueueUrl=queue_config['image_queue'],
                MessageBody=json.dumps(image_message)
            )
            print(f"Sent image generation message for character {character_id}")
        except Exception as e:
            print(f"Error sending image message for character {character_id}: {e}")
        
        # Send video generation message
        video_message = {
            'character_id': character_id,
            'task_type': 'video_generation',
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            sqs.send_message(
                QueueUrl=queue_config['video_queue'],
                MessageBody=json.dumps(video_message)
            )
            print(f"Sent video generation message for character {character_id}")
        except Exception as e:
            print(f"Error sending video message for character {character_id}: {e}")
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'Successfully scheduled content for {len(sqs_queues)} characters',
            'timestamp': datetime.now().isoformat()
        })
    }
