import json
import boto3
import os
import random
from datetime import datetime
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')
secrets_client = boto3.client('secretsmanager')

def lambda_handler(event, context):
    """
    Enhanced Content Generator for AI Influencer System
    Generates content using AI APIs and manages content workflow
    """
    try:
        logger.info(f"Content generation request: {json.dumps(event)}")
        
        # Parse event data
        character_id = event.get('character_id', 'char-1')
        content_type = event.get('content_type', 'text')
        prompt = event.get('prompt', '')
        source = event.get('source', 'api')  # 'api' or 'scheduled'
        
        # Get character configuration
        character_config = get_character_config(character_id)
        
        # Generate content based on type
        if content_type == 'text':
            content = generate_text_content(character_config, prompt)
        elif content_type == 'image':
            content = generate_image_content(character_config, prompt)
        elif content_type == 'video':
            content = generate_video_content(character_config, prompt)
        else:
            return create_error_response(f"Unsupported content type: {content_type}")
        
        # Save content to S3
        content_id = save_content_to_s3(content, character_id, content_type)
        
        # Store metadata in database
        store_content_metadata(content_id, character_id, content_type, content)
        
        # If this is scheduled content, trigger social posting
        if source == 'scheduled':
            schedule_social_posting(content_id, character_config)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Content generated successfully',
                'content_id': content_id,
                'character_id': character_id,
                'type': content_type,
                'timestamp': datetime.utcnow().isoformat()
            })
        }
        
    except Exception as e:
        logger.error(f"Error generating content: {str(e)}")
        return create_error_response(f"Content generation failed: {str(e)}")

def get_character_config(character_id):
    """Get character configuration and persona"""
    characters = {
        'char-1': {
            'name': 'Tech Influencer',
            'persona': 'Technology enthusiast and early adopter who loves sharing insights about the latest tech trends, gadgets, and innovations.',
            'tone': 'enthusiastic, informative, forward-thinking',
            'topics': ['AI', 'startups', 'gadgets', 'software', 'innovation', 'future tech'],
            'platforms': ['twitter', 'instagram'],
            'hashtags': ['#TechTrends', '#Innovation', '#AI', '#TechReview', '#FutureTech']
        },
        'char-2': {
            'name': 'Lifestyle Guru', 
            'persona': 'Health, wellness, and lifestyle content creator focused on helping people live their best lives.',
            'tone': 'inspiring, motivational, caring',
            'topics': ['wellness', 'fitness', 'mindfulness', 'nutrition', 'self-care', 'productivity'],
            'platforms': ['instagram', 'twitter'],
            'hashtags': ['#WellnessJourney', '#HealthyLifestyle', '#SelfCare', '#Mindfulness', '#Motivation']
        },
        'char-3': {
            'name': 'Business Coach',
            'persona': 'Entrepreneurship and business growth expert who helps others build successful businesses.',
            'tone': 'authoritative, encouraging, practical',
            'topics': ['entrepreneurship', 'business growth', 'leadership', 'marketing', 'productivity', 'success'],
            'platforms': ['twitter', 'instagram'],
            'hashtags': ['#Entrepreneurship', '#BusinessGrowth', '#Leadership', '#Success', '#BusinessTips']
        }
    }
    
    return characters.get(character_id, characters['char-1'])

def generate_text_content(character_config, custom_prompt=''):
    """Generate text content for the character"""
    try:
        # For MVP, we'll use template-based generation
        # In production, this would call OpenAI API
        
        if custom_prompt:
            base_content = f"Exploring: {custom_prompt}"
        else:
            # Generate content based on character topics
            topic = random.choice(character_config['topics'])
            base_content = get_template_content(character_config, topic)
        
        # Add character personality
        personality_touch = add_personality_touch(base_content, character_config)
        
        # Add hashtags
        hashtags = ' '.join(random.sample(character_config['hashtags'], 
                                        min(3, len(character_config['hashtags']))))
        
        final_content = f"{personality_touch}\n\n{hashtags}"
        
        return {
            'text': final_content,
            'topic': custom_prompt or random.choice(character_config['topics']),
            'character_tone': character_config['tone'],
            'platforms': character_config['platforms']
        }
        
    except Exception as e:
        logger.error(f"Error generating text content: {str(e)}")
        return {'text': 'Error generating content', 'error': str(e)}

def get_template_content(character_config, topic):
    """Get template-based content for different topics"""
    templates = {
        'AI': [
            "The future of AI is happening now! Excited to see how artificial intelligence is transforming industries and creating new possibilities.",
            "Just discovered an amazing AI tool that's revolutionizing the way we work. The pace of innovation is incredible!",
            "AI isn't replacing humans - it's amplifying our capabilities. Here's how I'm leveraging AI to boost productivity."
        ],
        'wellness': [
            "Starting the day with intention makes all the difference. What's one small wellness habit that has transformed your life?",
            "Self-care isn't selfish - it's essential. Taking time to recharge helps you show up better for everything else.",
            "Mindfulness isn't about perfection, it's about presence. Small moments of awareness can create big shifts."
        ],
        'entrepreneurship': [
            "Every successful business started with someone brave enough to take the first step. What's holding you back from yours?",
            "The biggest risk in business isn't failure - it's not trying at all. Here's why taking calculated risks is essential for growth.",
            "Building a business isn't just about the product - it's about solving real problems for real people."
        ]
    }
    
    # Get templates for the topic or default to generic ones
    topic_templates = templates.get(topic, [
        f"Thoughts on {topic} and how it's shaping our future.",
        f"Diving deep into {topic} - here's what I'm learning.",
        f"The impact of {topic} continues to amaze me."
    ])
    
    return random.choice(topic_templates)

def add_personality_touch(content, character_config):
    """Add personality-specific touches to content"""
    tone = character_config['tone']
    
    if 'enthusiastic' in tone:
        content += " 🚀"
    elif 'inspiring' in tone:
        content += " ✨"
    elif 'authoritative' in tone:
        content += " 💼"
    
    return content

def generate_image_content(character_config, prompt=''):
    """Generate image content (placeholder for DALL-E integration)"""
    try:
        # For MVP, return image generation request info
        # In production, this would call DALL-E API
        
        image_prompt = prompt or f"Create an image related to {random.choice(character_config['topics'])}"
        
        return {
            'type': 'image',
            'prompt': image_prompt,
            'style': f"Professional image in the style of {character_config['name']}",
            'status': 'pending',
            'note': 'Image generation would use DALL-E API in production'
        }
        
    except Exception as e:
        logger.error(f"Error generating image content: {str(e)}")
        return {'error': str(e)}

def generate_video_content(character_config, prompt=''):
    """Generate video content (placeholder for video generation)"""
    try:
        # For MVP, return video generation request info
        # In production, this would integrate with video generation services
        
        video_concept = prompt or f"Short video about {random.choice(character_config['topics'])}"
        
        return {
            'type': 'video',
            'concept': video_concept,
            'duration': '30-60 seconds',
            'style': f"Educational video in the voice of {character_config['name']}",
            'status': 'pending',
            'note': 'Video generation would use video AI services in production'
        }
        
    except Exception as e:
        logger.error(f"Error generating video content: {str(e)}")
        return {'error': str(e)}

def save_content_to_s3(content, character_id, content_type):
    """Save generated content to S3"""
    try:
        bucket_name = os.environ.get('S3_BUCKET')
        if not bucket_name:
            raise Exception("S3_BUCKET environment variable not set")
        
        # Generate unique content ID
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        content_id = f"{character_id}_{content_type}_{timestamp}"
        
        # Create S3 key
        s3_key = f"content/{character_id}/{content_type}/{content_id}.json"
        
        # Prepare content for storage
        storage_content = {
            'content_id': content_id,
            'character_id': character_id,
            'type': content_type,
            'data': content,
            'created_at': datetime.utcnow().isoformat(),
            'status': 'generated'
        }
        
        # Upload to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json.dumps(storage_content, indent=2),
            ContentType='application/json'
        )
        
        logger.info(f"Content saved to S3: {s3_key}")
        return content_id
        
    except Exception as e:
        logger.error(f"Error saving content to S3: {str(e)}")
        raise

def store_content_metadata(content_id, character_id, content_type, content):
    """Store content metadata in database"""
    try:
        # For MVP, we'll just log the metadata
        # In production, this would call the database Lambda
        
        metadata = {
            'content_id': content_id,
            'character_id': character_id,
            'type': content_type,
            'created_at': datetime.utcnow().isoformat(),
            'status': 'generated'
        }
        
        logger.info(f"Content metadata: {json.dumps(metadata)}")
        
        # TODO: Invoke database Lambda to store metadata
        # lambda_client.invoke(
        #     FunctionName=os.environ.get('DATABASE_LAMBDA'),
        #     InvocationType='Event',
        #     Payload=json.dumps({
        #         'action': 'store_content',
        #         'data': metadata
        #     })
        # )
        
    except Exception as e:
        logger.error(f"Error storing content metadata: {str(e)}")

def schedule_social_posting(content_id, character_config):
    """Schedule content for social media posting"""
    try:
        # Invoke social poster Lambda
        payload = {
            'content_id': content_id,
            'platforms': character_config['platforms'],
            'character_name': character_config['name'],
            'action': 'schedule_post'
        }
        
        lambda_client.invoke(
            FunctionName=os.environ.get('SOCIAL_POSTER_FUNCTION', 
                                       'ai-influencer-system-dev-social-poster'),
            InvocationType='Event',
            Payload=json.dumps(payload)
        )
        
        logger.info(f"Social posting scheduled for content: {content_id}")
        
    except Exception as e:
        logger.error(f"Error scheduling social posting: {str(e)}")

def create_error_response(error_message):
    """Create standardized error response"""
    return {
        'statusCode': 500,
        'body': json.dumps({
            'error': error_message,
            'timestamp': datetime.utcnow().isoformat()
        })
    }
