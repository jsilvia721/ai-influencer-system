import json
import boto3
import os
import requests
import base64
from datetime import datetime
import uuid
import time
import zipfile
import io

class LoRATrainingService:
    """
    Service for training LoRA models on various platforms
    Supports Replicate, RunPod, and custom training infrastructure
    """
    
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.secrets_client = boto3.client('secretsmanager')
        self.bucket_name = os.environ.get('S3_BUCKET_NAME')
        
        # Get API keys from Secrets Manager
        self.api_keys = self._get_api_keys()
        
        # Training platform endpoints
        self.replicate_api_url = "https://api.replicate.com/v1"
        self.runpod_api_url = "https://api.runpod.io/v2"
        
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
    
    def start_lora_training(self, character_id, training_config, training_images):
        """
        Start LoRA training using Replicate (recommended platform)
        
        Args:
            character_id: ID of the character
            training_config: Training configuration
            training_images: List of training images
        """
        # Always use Replicate for optimal reliability and ease of use
        return self._train_with_replicate(character_id, training_config, training_images)
    
    def _train_with_replicate(self, character_id, training_config, training_images):
        """Train LoRA model using Replicate"""
        
        # Upload training images to a zip file in S3
        zip_url = self._create_training_zip(character_id, training_images)
        
        replicate_request = {
            "input": {
                "input_images": zip_url,
                "trigger_word": f"character_{character_id[:8]}",
                "max_train_steps": training_config.get('max_train_steps', 1000),
                "learning_rate": training_config.get('learning_rate', 1e-4),
                "batch_size": training_config.get('batch_size', 1),
                "resolution": training_config.get('resolution', 1024),
                "train_text_encoder": training_config.get('train_text_encoder', False),
                "auto_augment": training_config.get('auto_augment', True),
                "seed": training_config.get('seed', 42)
            },
            "model": "ostris/flux-dev-lora-trainer",
            "webhook": f"{os.environ.get('API_GATEWAY_URL')}/training-webhook"
        }
        
        try:
            headers = {
                'Authorization': f"Token {self.api_keys.get('replicate_api_key')}",
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f"{self.replicate_api_url}/predictions",
                json=replicate_request,
                headers=headers
            )
            
            if response.status_code == 201:
                result = response.json()
                
                job_info = {
                    'platform': 'replicate',
                    'character_id': character_id,
                    'job_id': result['id'],
                    'status': result['status'],
                    'created_at': datetime.utcnow().isoformat(),
                    'training_config': training_config,
                    'training_zip_url': zip_url
                }
                
                self._store_training_job(character_id, result['id'], job_info)
                
                return {
                    'success': True,
                    'platform': 'replicate',
                    'job_id': result['id'],
                    'status': result['status'],
                    'estimated_duration': '15-30 minutes'
                }
            else:
                raise Exception(f"Replicate API error: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"Error starting Replicate training: {e}")
            raise
    
    def _train_with_runpod(self, character_id, training_config, training_images):
        """Train LoRA model using RunPod serverless"""
        
        zip_url = self._create_training_zip(character_id, training_images)
        
        runpod_request = {
            "input": {
                "training_data_url": zip_url,
                "character_id": character_id,
                "trigger_word": f"character_{character_id[:8]}",
                "base_model": "black-forest-labs/FLUX.1-dev",
                "learning_rate": training_config.get('learning_rate', 1e-4),
                "max_train_steps": training_config.get('max_train_steps', 1000),
                "batch_size": training_config.get('batch_size', 1),
                "resolution": training_config.get('resolution', 1024),
                "webhook_url": f"{os.environ.get('API_GATEWAY_URL')}/training-webhook"
            }
        }
        
        try:
            headers = {
                'Authorization': f"Bearer {self.api_keys.get('runpod_api_key')}",
                'Content-Type': 'application/json'
            }
            
            endpoint_id = self.api_keys.get('runpod_endpoint_id', 'your-lora-training-endpoint')
            
            response = requests.post(
                f"{self.runpod_api_url}/{endpoint_id}/run",
                json=runpod_request,
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                
                job_info = {
                    'platform': 'runpod',
                    'character_id': character_id,
                    'job_id': result['id'],
                    'status': 'IN_QUEUE',
                    'created_at': datetime.utcnow().isoformat(),
                    'training_config': training_config,
                    'training_zip_url': zip_url
                }
                
                self._store_training_job(character_id, result['id'], job_info)
                
                return {
                    'success': True,
                    'platform': 'runpod',
                    'job_id': result['id'],
                    'status': 'IN_QUEUE',
                    'estimated_duration': '10-20 minutes'
                }
            else:
                raise Exception(f"RunPod API error: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"Error starting RunPod training: {e}")
            raise
    
    def _create_training_zip(self, character_id, training_images):
        """Create a zip file of training images and upload to S3"""
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for i, image_data in enumerate(training_images):
                if isinstance(image_data, str):
                    image_data = base64.b64decode(image_data)
                
                zip_file.writestr(f"image_{i:03d}.jpg", image_data)
        
        zip_data = zip_buffer.getvalue()
        zip_key = f"training/{character_id}/training_images.zip"
        
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=zip_key,
            Body=zip_data,
            ContentType='application/zip'
        )
        
        zip_url = self.s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket_name, 'Key': zip_key},
            ExpiresIn=3600 * 24
        )
        
        return zip_url
    
    def _store_training_job(self, character_id, job_id, job_info):
        """Store training job information in S3"""
        job_key = f"training/{character_id}/jobs/{job_id}.json"
        
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=job_key,
            Body=json.dumps(job_info, indent=2),
            ContentType='application/json'
        )
    
    def check_training_status(self, character_id, job_id):
        """Check the status of a training job"""
        try:
            job_key = f"training/{character_id}/jobs/{job_id}.json"
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=job_key)
            job_info = json.loads(response['Body'].read())
            
            platform = job_info['platform']
            
            if platform == 'replicate':
                return self._check_replicate_status(job_info)
            elif platform == 'runpod':
                return self._check_runpod_status(job_info)
            else:
                return {'status': 'unknown', 'error': f'Unknown platform: {platform}'}
                
        except Exception as e:
            print(f"Error checking training status: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _check_replicate_status(self, job_info):
        """Check Replicate training status"""
        try:
            headers = {
                'Authorization': f"Token {self.api_keys.get('replicate_api_key')}"
            }
            
            response = requests.get(
                f"{self.replicate_api_url}/predictions/{job_info['job_id']}",
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result['status'] == 'succeeded':
                    model_url = result['output']
                    model_key = self._download_trained_model(
                        job_info['character_id'], 
                        job_info['job_id'], 
                        model_url
                    )
                    
                    self._update_character_model_status(
                        job_info['character_id'], 
                        'ready', 
                        model_key
                    )
                    
                    return {
                        'status': 'completed',
                        'model_key': model_key,
                        'platform': 'replicate'
                    }
                
                elif result['status'] == 'failed':
                    return {
                        'status': 'failed',
                        'error': result.get('error', 'Training failed'),
                        'platform': 'replicate'
                    }
                
                else:
                    return {
                        'status': result['status'],
                        'platform': 'replicate'
                    }
            
            return {'status': 'unknown', 'error': 'Failed to check status'}
            
        except Exception as e:
            print(f"Error checking Replicate status: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _download_trained_model(self, character_id, job_id, model_url):
        """Download trained LoRA model and store in S3"""
        try:
            response = requests.get(model_url, timeout=300)
            
            if response.status_code == 200:
                model_key = f"characters/{character_id}/lora_model.safetensors"
                
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=model_key,
                    Body=response.content,
                    ContentType='application/octet-stream'
                )
                
                return model_key
            else:
                raise Exception(f"Failed to download model: {response.status_code}")
                
        except Exception as e:
            print(f"Error downloading trained model: {e}")
            raise
    
    def _update_character_model_status(self, character_id, status, model_path=None):
        """Update character model status in S3"""
        try:
            config_key = f"characters/{character_id}/config.json"
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=config_key)
            character_config = json.loads(response['Body'].read())
            
            character_config['model_status'] = status
            character_config['updated_at'] = datetime.utcnow().isoformat()
            
            if model_path:
                character_config['lora_model_path'] = model_path
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=config_key,
                Body=json.dumps(character_config, indent=2),
                ContentType='application/json'
            )
            
        except Exception as e:
            print(f"Error updating character model status: {e}")
            raise

def handler(event, context):
    """
    Lambda handler for LoRA training service
    """
    try:
        service = LoRATrainingService()
        
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        action = body.get('action')
        
        if action == 'start_training':
            result = service.start_lora_training(
                character_id=body.get('character_id'),
                training_config=body.get('training_config', {}),
                training_images=body.get('training_images', [])
            )
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(result)
            }
        
        elif action == 'check_status':
            result = service.check_training_status(
                character_id=body.get('character_id'),
                job_id=body.get('job_id')
            )
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(result)
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
