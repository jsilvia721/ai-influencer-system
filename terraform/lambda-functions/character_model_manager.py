import json
import boto3
import os
import requests
import base64
from datetime import datetime
import uuid

class CharacterModelManager:
    """
    Manages LoRA character models for consistent image/video generation
    """
    
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.secrets_client = boto3.client('secretsmanager')
        self.bucket_name = os.environ.get('S3_BUCKET_NAME')
        
        # Get API keys from Secrets Manager
        self.api_keys = self._get_api_keys()
        
    def _get_api_keys(self):
        """Retrieve API keys from AWS Secrets Manager"""
        try:
            response = self.secrets_client.get_secret_value(
                SecretId='ai-influencer-api-keys'
            )
            return json.loads(response['SecretString'])
        except Exception as e:
            print(f"Error getting API keys: {e}")
            return {}
    
    def create_character_model(self, character_data, training_images):
        """
        Create a new LoRA character model
        
        Args:
            character_data: Character metadata (name, personality, etc.)
            training_images: List of training images for LoRA model
        """
        character_id = str(uuid.uuid4())
        
        # Store character metadata
        character_config = {
            'id': character_id,
            'name': character_data.get('name'),
            'personality': character_data.get('personality'),
            'style_preferences': character_data.get('style_preferences', {}),
            'created_at': datetime.utcnow().isoformat(),
            'model_status': 'training',
            'training_images_count': len(training_images),
            'lora_model_path': f"characters/{character_id}/lora_model.safetensors",
            'reference_images': f"characters/{character_id}/references/",
            'generation_settings': {
                'flux_model': 'flux-1.0-pro',
                'kling_model': 'kling-v1',
                'default_style': character_data.get('default_style', 'photorealistic'),
                'consistency_weight': 0.8
            }
        }
        
        # Store character config in S3
        self._store_character_config(character_id, character_config)
        
        # Store reference images
        self._store_reference_images(character_id, training_images)
        
        # Start LoRA training (this would call your training API)
        training_job_id = self._start_lora_training(character_id, training_images)
        
        character_config['training_job_id'] = training_job_id
        self._store_character_config(character_id, character_config)
        
        return character_config
    
    def _store_character_config(self, character_id, config):
        """Store character configuration in S3"""
        key = f"characters/{character_id}/config.json"
        
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=json.dumps(config, indent=2),
            ContentType='application/json'
        )
    
    def _store_reference_images(self, character_id, images):
        """Store reference images for character in S3"""
        for i, image_data in enumerate(images):
            key = f"characters/{character_id}/references/ref_{i:03d}.jpg"
            
            # Decode base64 image if needed
            if isinstance(image_data, str):
                image_data = base64.b64decode(image_data)
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=image_data,
                ContentType='image/jpeg'
            )
    
    def _start_lora_training(self, character_id, training_images):
        """
        Start LoRA model training
        This would integrate with your LoRA training service/API
        """
        # This is a placeholder - you'd integrate with actual LoRA training service
        # Could be Replicate, RunPod, or your own training infrastructure
        
        training_config = {
            'character_id': character_id,
            'base_model': 'flux-1.0-dev',
            'training_steps': 1000,
            'learning_rate': 1e-4,
            'batch_size': 1,
            'resolution': 1024,
            'trigger_word': f"character_{character_id[:8]}"
        }
        
        # For now, return a mock training job ID
        # In production, this would call your training API
        training_job_id = f"lora_training_{uuid.uuid4()}"
        
        print(f"Started LoRA training for character {character_id}: {training_job_id}")
        
        return training_job_id
    
    def get_character_model(self, character_id):
        """Retrieve character model configuration"""
        try:
            key = f"characters/{character_id}/config.json"
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return json.loads(response['Body'].read())
        except Exception as e:
            print(f"Error retrieving character model {character_id}: {e}")
            return None
    
    def list_characters(self):
        """List all available character models"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix='characters/',
                Delimiter='/'
            )
            
            characters = []
            for prefix in response.get('CommonPrefixes', []):
                character_id = prefix['Prefix'].split('/')[1]
                character_config = self.get_character_model(character_id)
                if character_config:
                    characters.append(character_config)
            
            return characters
        except Exception as e:
            print(f"Error listing characters: {e}")
            return []
    
    def update_model_status(self, character_id, status, model_path=None):
        """Update character model training status"""
        character_config = self.get_character_model(character_id)
        if character_config:
            character_config['model_status'] = status
            character_config['updated_at'] = datetime.utcnow().isoformat()
            
            if model_path:
                character_config['lora_model_path'] = model_path
            
            self._store_character_config(character_id, character_config)
            return True
        return False

def handler(event, context):
    """
    Lambda handler for character model management
    """
    try:
        manager = CharacterModelManager()
        
        # Parse the request
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        action = body.get('action')
        
        if action == 'create_character':
            result = manager.create_character_model(
                character_data=body.get('character_data', {}),
                training_images=body.get('training_images', [])
            )
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'character': result
                })
            }
        
        elif action == 'list_characters':
            characters = manager.list_characters()
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'characters': characters
                })
            }
        
        elif action == 'get_character':
            character_id = body.get('character_id')
            character = manager.get_character_model(character_id)
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'character': character
                })
            }
        
        elif action == 'update_status':
            character_id = body.get('character_id')
            status = body.get('status')
            model_path = body.get('model_path')
            
            success = manager.update_model_status(character_id, status, model_path)
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': success
                })
            }
        
        else:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Invalid action specified'
                })
            }
    
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': str(e)
            })
        }
