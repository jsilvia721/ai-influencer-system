import json
import boto3
import os
import requests
import base64
from datetime import datetime
import uuid
import time

class CharacterMediaGenerator:
    """
    Generate character-consistent images and videos using LoRA models
    with Flux 1.0 for images and Kling for videos
    """
    
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.secrets_client = boto3.client('secretsmanager')
        self.bucket_name = os.environ.get('S3_BUCKET_NAME')
        
        # Get API keys from Secrets Manager
        self.api_keys = self._get_api_keys()
        
        # API endpoints for Flux (via Replicate) and Kling
        self.replicate_api_url = "https://api.replicate.com/v1"
        self.kling_api_url = "https://api.kling.ai/v1/videos/generations"  # Kling API
        
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
    
    def _get_character_config(self, character_id):
        """Retrieve character configuration from S3"""
        try:
            key = f"characters/{character_id}/config.json"
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return json.loads(response['Body'].read())
        except Exception as e:
            print(f"Error retrieving character config {character_id}: {e}")
            return None
    
    def generate_character_image(self, character_id, prompt, style_settings=None):
        """
        Generate a character-consistent image using Flux 1.0 + LoRA model
        
        Args:
            character_id: ID of the character model to use
            prompt: Text prompt for image generation
            style_settings: Optional style overrides
        """
        # Get character configuration
        character_config = self._get_character_config(character_id)
        if not character_config:
            raise ValueError(f"Character {character_id} not found")
        
        if character_config.get('model_status') != 'ready':
            raise ValueError(f"Character model {character_id} is not ready (status: {character_config.get('model_status')})")
        
        # Prepare generation settings
        generation_settings = character_config.get('generation_settings', {})
        if style_settings:
            generation_settings.update(style_settings)
        
        # Get the character trigger word for LoRA
        trigger_word = f"character_{character_id[:8]}"
        
        # Enhance prompt with character-specific elements
        enhanced_prompt = self._enhance_prompt_for_character(prompt, character_config, trigger_word)
        
        # Use Replicate's Flux model with LoRA support
        return self._generate_with_replicate_flux(
            character_id, enhanced_prompt, generation_settings, character_config
        )
    
    def generate_character_video(self, character_id, prompt, reference_image_key=None, style_settings=None):
        """
        Generate a character-consistent video using Kling model
        
        Args:
            character_id: ID of the character model to use
            prompt: Text prompt for video generation
            reference_image_key: Optional reference image for video generation
            style_settings: Optional style overrides
        """
        # Get character configuration
        character_config = self._get_character_config(character_id)
        if not character_config:
            raise ValueError(f"Character {character_id} not found")
        
        if character_config.get('model_status') != 'ready':
            raise ValueError(f"Character model {character_id} is not ready")
        
        # Prepare generation settings
        generation_settings = character_config.get('generation_settings', {})
        if style_settings:
            generation_settings.update(style_settings)
        
        # If no reference image provided, generate one first
        if not reference_image_key:
            print("No reference image provided, generating one first...")
            image_result = self.generate_character_image(
                character_id, 
                f"portrait of {character_config.get('name', 'character')}, {prompt}",
                {'width': 1024, 'height': 1024}
            )
            reference_image_key = image_result['image_key']
        
        # Get reference image data
        reference_image_data = self._get_s3_object_as_base64(reference_image_key)
        
        # Enhance prompt for video generation
        enhanced_prompt = self._enhance_video_prompt_for_character(prompt, character_config)
        
        # Prepare Kling API request
        kling_request = {
            'model': generation_settings.get('kling_model', 'kling-v1'),
            'prompt': enhanced_prompt,
            'image': reference_image_data,
            'duration': generation_settings.get('video_duration', 5),  # seconds
            'fps': generation_settings.get('fps', 24),
            'resolution': generation_settings.get('video_resolution', '1024x1024'),
            'motion_intensity': generation_settings.get('motion_intensity', 0.7),
            'camera_movement': generation_settings.get('camera_movement', 'static')
        }
        
        # Call Kling API
        try:
            headers = {
                'Authorization': f"Bearer {self.api_keys.get('kling_api_key')}",
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                self.kling_api_url,
                json=kling_request,
                headers=headers,
                timeout=600  # 10 minute timeout for video generation
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Check if generation is async
                if 'job_id' in result:
                    return self._handle_async_video_generation(
                        character_id, result['job_id'], prompt, generation_settings
                    )
                
                # Store generated video in S3
                video_data = base64.b64decode(result['video'])
                video_key = self._store_generated_media(
                    character_id, 'video', video_data,
                    {'prompt': prompt, 'reference_image': reference_image_key, 'settings': generation_settings}
                )
                
                return {
                    'success': True,
                    'video_url': f"s3://{self.bucket_name}/{video_key}",
                    'video_key': video_key,
                    'reference_image_key': reference_image_key,
                    'generation_id': result.get('id'),
                    'prompt': enhanced_prompt,
                    'settings': generation_settings
                }
            else:
                raise Exception(f"Kling API error: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"Error generating video with Kling: {e}")
            raise
    
    def _generate_with_replicate_flux(self, character_id, enhanced_prompt, generation_settings, character_config):
        """Generate image using Replicate's Flux model with LoRA support"""
        try:
            # Get the S3 URL for the trained LoRA model
            lora_model_key = character_config.get('lora_model_path')
            if lora_model_key:
                lora_model_url = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.bucket_name, 'Key': lora_model_key},
                    ExpiresIn=3600
                )
            else:
                lora_model_url = None
            
            # Prepare Replicate request for Flux with LoRA
            replicate_request = {
                "input": {
                    "prompt": enhanced_prompt,
                    "width": generation_settings.get('width', 1024),
                    "height": generation_settings.get('height', 1024),
                    "num_outputs": 1,
                    "num_inference_steps": generation_settings.get('steps', 28),
                    "guidance_scale": generation_settings.get('guidance_scale', 3.5),
                    "seed": generation_settings.get('seed') if generation_settings.get('seed', -1) != -1 else None
                }
            }
            
            # Add LoRA model if available
            if lora_model_url:
                replicate_request["input"]["lora"] = lora_model_url
                replicate_request["input"]["lora_scale"] = generation_settings.get('consistency_weight', 0.8)
            
            # Use Flux model on Replicate
            model = "black-forest-labs/flux-schnell"
            
            headers = {
                'Authorization': f"Token {self.api_keys.get('replicate_api_key')}",
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f"{self.replicate_api_url}/predictions",
                json={
                    "version": model,
                    **replicate_request
                },
                headers=headers,
                timeout=300
            )
            
            if response.status_code == 201:
                result = response.json()
                prediction_id = result['id']
                
                # Poll for completion (simplified - in production use webhooks)
                max_attempts = 60  # 5 minutes
                for attempt in range(max_attempts):
                    status_response = requests.get(
                        f"{self.replicate_api_url}/predictions/{prediction_id}",
                        headers=headers
                    )
                    
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        
                        if status_data['status'] == 'succeeded':
                            # Download image from URL
                            image_url = status_data['output'][0]  # First output
                            image_response = requests.get(image_url)
                            
                            if image_response.status_code == 200:
                                image_data = image_response.content
                                
                                # Store generated image in S3
                                image_key = self._store_generated_media(
                                    character_id, 'image', image_data,
                                    {'prompt': enhanced_prompt, 'settings': generation_settings}
                                )
                                
                                return {
                                    'success': True,
                                    'image_url': f"s3://{self.bucket_name}/{image_key}",
                                    'image_key': image_key,
                                    'generation_id': prediction_id,
                                    'prompt': enhanced_prompt,
                                    'settings': generation_settings,
                                    'platform': 'replicate_flux'
                                }
                            else:
                                raise Exception(f"Failed to download image: {image_response.status_code}")
                        
                        elif status_data['status'] == 'failed':
                            raise Exception(f"Flux generation failed: {status_data.get('error', 'Unknown error')}")
                        
                        elif status_data['status'] in ['starting', 'processing']:
                            time.sleep(5)  # Wait before next check
                            continue
                
                raise Exception("Generation timed out after 5 minutes")
            
            else:
                raise Exception(f"Replicate API error: {response.status_code} - {response.text}")
        
        except Exception as e:
            print(f"Error generating image with Replicate Flux: {e}")
            raise
    
    def _enhance_prompt_for_character(self, prompt, character_config, trigger_word):
        """Enhance prompt with character-specific elements for image generation"""
        personality = character_config.get('personality', '')
        style_prefs = character_config.get('style_preferences', {})
        
        enhanced_elements = [
            trigger_word,  # LoRA trigger word
            prompt,
            personality,
            style_prefs.get('aesthetic', ''),
            style_prefs.get('mood', ''),
            "high quality, detailed, professional"
        ]
        
        enhanced_prompt = ', '.join([elem for elem in enhanced_elements if elem])
        
        # Add negative prompt elements
        negative_elements = [
            "blurry", "low quality", "distorted", "deformed",
            style_prefs.get('avoid', '')
        ]
        negative_prompt = ', '.join([elem for elem in negative_elements if elem])
        
        return f"{enhanced_prompt} | negative: {negative_prompt}"
    
    def _enhance_video_prompt_for_character(self, prompt, character_config):
        """Enhance prompt for video generation"""
        personality = character_config.get('personality', '')
        name = character_config.get('name', 'character')
        
        enhanced_prompt = f"{name} with {personality} personality, {prompt}, smooth motion, cinematic quality"
        
        return enhanced_prompt
    
    def _get_s3_object_as_base64(self, key):
        """Get S3 object and return as base64 string"""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            image_data = response['Body'].read()
            return base64.b64encode(image_data).decode('utf-8')
        except Exception as e:
            print(f"Error getting S3 object {key}: {e}")
            raise
    
    def _store_generated_media(self, character_id, media_type, media_data, metadata):
        """Store generated media in S3 with metadata"""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        media_id = str(uuid.uuid4())[:8]
        
        # Determine file extension
        ext = 'jpg' if media_type == 'image' else 'mp4'
        
        # Store media file
        media_key = f"generated/{character_id}/{media_type}s/{timestamp}_{media_id}.{ext}"
        
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=media_key,
            Body=media_data,
            ContentType=f"{media_type}/{'jpeg' if media_type == 'image' else 'mp4'}"
        )
        
        # Store metadata
        metadata_key = f"generated/{character_id}/{media_type}s/{timestamp}_{media_id}_metadata.json"
        
        full_metadata = {
            'character_id': character_id,
            'media_type': media_type,
            'media_key': media_key,
            'generated_at': datetime.utcnow().isoformat(),
            'generation_id': media_id,
            **metadata
        }
        
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=metadata_key,
            Body=json.dumps(full_metadata, indent=2),
            ContentType='application/json'
        )
        
        return media_key
    
    def _handle_async_video_generation(self, character_id, job_id, prompt, settings):
        """Handle async video generation job"""
        # Store job information for later retrieval
        job_info = {
            'job_id': job_id,
            'character_id': character_id,
            'prompt': prompt,
            'settings': settings,
            'status': 'processing',
            'created_at': datetime.utcnow().isoformat()
        }
        
        job_key = f"jobs/video_generation/{job_id}.json"
        
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=job_key,
            Body=json.dumps(job_info, indent=2),
            ContentType='application/json'
        )
        
        return {
            'success': True,
            'status': 'processing',
            'job_id': job_id,
            'message': 'Video generation started. Check status with job_id.'
        }
    
    def check_generation_status(self, job_id):
        """Check the status of an async generation job"""
        try:
            # Get job info from S3
            job_key = f"jobs/video_generation/{job_id}.json"
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=job_key)
            job_info = json.loads(response['Body'].read())
            
            # Check status with Kling API
            headers = {
                'Authorization': f"Bearer {self.api_keys.get('kling_api_key')}",
                'Content-Type': 'application/json'
            }
            
            status_response = requests.get(
                f"{self.kling_api_url}/jobs/{job_id}",
                headers=headers
            )
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                
                if status_data['status'] == 'completed':
                    # Download and store the video
                    video_data = base64.b64decode(status_data['video'])
                    video_key = self._store_generated_media(
                        job_info['character_id'], 'video', video_data,
                        {'prompt': job_info['prompt'], 'settings': job_info['settings']}
                    )
                    
                    # Update job status
                    job_info.update({
                        'status': 'completed',
                        'video_key': video_key,
                        'completed_at': datetime.utcnow().isoformat()
                    })
                    
                    self.s3_client.put_object(
                        Bucket=self.bucket_name,
                        Key=job_key,
                        Body=json.dumps(job_info, indent=2),
                        ContentType='application/json'
                    )
                    
                    return {
                        'status': 'completed',
                        'video_url': f"s3://{self.bucket_name}/{video_key}",
                        'video_key': video_key
                    }
                
                return {'status': status_data['status']}
            
            return {'status': 'unknown', 'error': 'Failed to check status'}
            
        except Exception as e:
            print(f"Error checking generation status: {e}")
            return {'status': 'error', 'error': str(e)}

def handler(event, context):
    """
    Lambda handler for character media generation
    """
    try:
        generator = CharacterMediaGenerator()
        
        # Parse the request
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        action = body.get('action')
        character_id = body.get('character_id')
        
        if action == 'generate_image':
            result = generator.generate_character_image(
                character_id=character_id,
                prompt=body.get('prompt', ''),
                style_settings=body.get('style_settings')
            )
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(result)
            }
        
        elif action == 'generate_video':
            result = generator.generate_character_video(
                character_id=character_id,
                prompt=body.get('prompt', ''),
                reference_image_key=body.get('reference_image_key'),
                style_settings=body.get('style_settings')
            )
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(result)
            }
        
        elif action == 'check_status':
            job_id = body.get('job_id')
            result = generator.check_generation_status(job_id)
            
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
