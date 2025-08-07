"""
Comprehensive test suite for training image generator with retry mechanism.
Mocks Replicate API calls to avoid API costs during testing.
"""

import pytest
import json
import uuid
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timezone
from decimal import Decimal
import sys
import os

# Add the lambda directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambda'))

# Import the improved training image generator
from training_image_generator_improved import (
    lambda_handler,
    generate_training_images_with_retry,
    generate_single_image_with_replicate,
    upload_image_to_s3,
    get_secret
)

class TestTrainingImageGenerator:
    
    def setup_method(self):
        """Set up test fixtures"""
        self.job_id = str(uuid.uuid4())
        self.character_name = "Emma Test"
        self.character_description = "A 25-year-old test character"
        self.mock_api_token = "mock_replicate_token"
        self.mock_table = Mock()
        
        # Mock environment variables
        os.environ['S3_BUCKET_NAME'] = 'test-bucket'
        os.environ['REPLICATE_API_TOKEN_SECRET'] = 'test-secret'
    
    @patch('training_image_generator_improved.get_secret')
    @patch('training_image_generator_improved.dynamodb')
    def test_lambda_handler_success(self, mock_dynamodb, mock_get_secret):
        """Test successful lambda handler execution"""
        # Setup mocks
        mock_get_secret.return_value = self.mock_api_token
        mock_table = Mock()
        mock_dynamodb.Table.return_value = mock_table
        
        # Mock the entire generation process
        with patch('training_image_generator_improved.generate_training_images_with_retry') as mock_generate:
            mock_generate.return_value = {
                'status': 'completed',
                'completed_images': 5,
                'current_attempt': 7,
                'success_rate': 71.43,
                'image_urls': ['url1', 'url2', 'url3', 'url4', 'url5']
            }
            
            event = {
                'character_name': self.character_name,
                'character_description': self.character_description,
                'num_images': 5
            }
            
            result = lambda_handler(event, {})
            
            assert result['statusCode'] == 200
            body = json.loads(result['body'])
            assert body['status'] == 'completed'
            assert body['completed_images'] == 5
            assert body['current_attempt'] == 7
            assert body['success_rate'] == 71.43
            assert len(body['image_urls']) == 5
    
    def test_lambda_handler_validation_errors(self):
        """Test lambda handler input validation"""
        # Missing character name
        event = {
            'character_description': self.character_description,
            'num_images': 5
        }
        result = lambda_handler(event, {})
        assert result['statusCode'] == 400
        assert 'Missing character_name' in json.loads(result['body'])['error']
        
        # Invalid num_images
        event = {
            'character_name': self.character_name,
            'character_description': self.character_description,
            'num_images': 100
        }
        result = lambda_handler(event, {})
        assert result['statusCode'] == 400
        assert 'must be between 1 and 50' in json.loads(result['body'])['error']
    
    @patch('training_image_generator_improved.get_secret')
    def test_lambda_handler_no_api_token(self, mock_get_secret):
        """Test handling when API token is not available"""
        mock_get_secret.return_value = None
        
        event = {
            'character_name': self.character_name,
            'character_description': self.character_description,
            'num_images': 5
        }
        
        result = lambda_handler(event, {})
        assert result['statusCode'] == 500
        assert 'Replicate API token not configured' in json.loads(result['body'])['error']
    
    @patch('training_image_generator_improved.generate_single_image_with_replicate')
    @patch('training_image_generator_improved.upload_image_to_s3')
    def test_generate_training_images_perfect_success(self, mock_upload, mock_generate):
        """Test perfect success scenario - all images generated on first attempts"""
        # Mock successful generation and upload for all attempts
        mock_generate.return_value = 'https://replicate.com/mock-image.jpg'
        mock_upload.return_value = 'https://s3.amazonaws.com/bucket/image.jpg'
        
        result = generate_training_images_with_retry(
            api_token=self.mock_api_token,
            job_id=self.job_id,
            character_name=self.character_name,
            character_description=self.character_description,
            folder_id=self.job_id,
            num_images=3,
            max_attempts=10,
            table=self.mock_table
        )
        
        assert result['status'] == 'completed'
        assert result['completed_images'] == 3
        assert result['current_attempt'] == 3
        assert result['success_rate'] == 100.0
        assert len(result['image_urls']) == 3
        
        # Verify DynamoDB was updated correctly
        assert self.mock_table.update_item.call_count >= 3  # At least one update per successful generation
    
    @patch('training_image_generator_improved.generate_single_image_with_replicate')
    @patch('training_image_generator_improved.upload_image_to_s3')
    def test_generate_training_images_with_failures(self, mock_upload, mock_generate):
        """Test scenario with some failures requiring retries"""
        # Mock a pattern: fail, succeed, fail, succeed, succeed
        mock_generate.side_effect = [
            None,  # First attempt fails
            'https://replicate.com/mock-image-1.jpg',  # Second succeeds
            None,  # Third fails
            'https://replicate.com/mock-image-2.jpg',  # Fourth succeeds
            'https://replicate.com/mock-image-3.jpg'   # Fifth succeeds
        ]
        mock_upload.return_value = 'https://s3.amazonaws.com/bucket/image.jpg'
        
        result = generate_training_images_with_retry(
            api_token=self.mock_api_token,
            job_id=self.job_id,
            character_name=self.character_name,
            character_description=self.character_description,
            folder_id=self.job_id,
            num_images=3,
            max_attempts=10,
            table=self.mock_table
        )
        
        assert result['status'] == 'completed'
        assert result['completed_images'] == 3
        assert result['current_attempt'] == 5  # Took 5 attempts to get 3 images
        assert result['success_rate'] == 60.0  # 3/5 = 60%
        assert len(result['image_urls']) == 3
    
    @patch('training_image_generator_improved.generate_single_image_with_replicate')
    @patch('training_image_generator_improved.upload_image_to_s3')
    def test_generate_training_images_max_attempts_reached(self, mock_upload, mock_generate):
        """Test scenario where max attempts is reached before target is met"""
        # Mock failures for first 4 attempts, then successes
        mock_generate.side_effect = [None] * 4 + ['https://replicate.com/mock-image.jpg'] * 2
        mock_upload.return_value = 'https://s3.amazonaws.com/bucket/image.jpg'
        
        result = generate_training_images_with_retry(
            api_token=self.mock_api_token,
            job_id=self.job_id,
            character_name=self.character_name,
            character_description=self.character_description,
            folder_id=self.job_id,
            num_images=5,  # Want 5 images
            max_attempts=6,  # But only allow 6 attempts
            table=self.mock_table
        )
        
        assert result['status'] == 'completed'  # Still completed, but with partial results
        assert result['completed_images'] == 2  # Only got 2 images
        assert result['current_attempt'] == 6  # Used all attempts
        assert result['success_rate'] == pytest.approx(33.33, rel=1e-2)  # 2/6 ≈ 33.33%
        assert len(result['image_urls']) == 2
    
    @patch('training_image_generator_improved.generate_single_image_with_replicate')
    def test_generate_training_images_upload_failures(self, mock_generate):
        """Test scenario where image generation succeeds but S3 upload fails"""
        mock_generate.return_value = 'https://replicate.com/mock-image.jpg'
        
        with patch('training_image_generator_improved.upload_image_to_s3') as mock_upload:
            # Mock upload failures
            mock_upload.return_value = None
            
            result = generate_training_images_with_retry(
                api_token=self.mock_api_token,
                job_id=self.job_id,
                character_name=self.character_name,
                character_description=self.character_description,
                folder_id=self.job_id,
                num_images=2,
                max_attempts=5,
                table=self.mock_table
            )
            
            assert result['status'] == 'completed'
            assert result['completed_images'] == 0  # No images successfully stored
            assert result['current_attempt'] == 5  # Used all attempts
            assert result['success_rate'] == 0.0
            assert len(result['image_urls']) == 0
    
    def test_generate_single_image_with_replicate_success(self):
        """Test successful single image generation"""
        with patch('training_image_generator_improved.http') as mock_http:
            # Mock prediction creation response
            create_response = Mock()
            create_response.status = 201
            create_response.data.decode.return_value = json.dumps({
                'id': 'test-prediction-id'
            })
            
            # Mock status polling - first processing, then succeeded
            status_response_processing = Mock()
            status_response_processing.status = 200
            status_response_processing.data.decode.return_value = json.dumps({
                'status': 'processing'
            })
            
            status_response_succeeded = Mock()
            status_response_succeeded.status = 200
            status_response_succeeded.data.decode.return_value = json.dumps({
                'status': 'succeeded',
                'output': ['https://replicate.com/generated-image.jpg']
            })
            
            # Setup side effects
            mock_http.request.side_effect = [
                create_response,  # POST to create prediction
                status_response_processing,  # First status check
                status_response_succeeded   # Second status check
            ]
            
            with patch('time.sleep'):  # Mock sleep to speed up test
                result = generate_single_image_with_replicate(
                    self.mock_api_token, 
                    "test prompt"
                )
            
            assert result == 'https://replicate.com/generated-image.jpg'
            assert mock_http.request.call_count == 3
    
    def test_generate_single_image_with_replicate_failure(self):
        """Test failed single image generation"""
        with patch('training_image_generator_improved.http') as mock_http:
            # Mock prediction creation response
            create_response = Mock()
            create_response.status = 201
            create_response.data.decode.return_value = json.dumps({
                'id': 'test-prediction-id'
            })
            
            # Mock status polling - return failed
            status_response_failed = Mock()
            status_response_failed.status = 200
            status_response_failed.data.decode.return_value = json.dumps({
                'status': 'failed',
                'error': 'Generation failed due to safety checker'
            })
            
            mock_http.request.side_effect = [
                create_response,
                status_response_failed
            ]
            
            result = generate_single_image_with_replicate(
                self.mock_api_token, 
                "test prompt"
            )
            
            assert result is None
    
    def test_generate_single_image_with_replicate_timeout(self):
        """Test timeout scenario"""
        with patch('training_image_generator_improved.http') as mock_http:
            # Mock prediction creation response
            create_response = Mock()
            create_response.status = 201
            create_response.data.decode.return_value = json.dumps({
                'id': 'test-prediction-id'
            })
            
            # Mock status polling - always processing (causes timeout)
            status_response_processing = Mock()
            status_response_processing.status = 200
            status_response_processing.data.decode.return_value = json.dumps({
                'status': 'processing'
            })
            
            mock_http.request.side_effect = [create_response] + [status_response_processing] * 50
            
            with patch('time.sleep'):  # Mock sleep to speed up test
                result = generate_single_image_with_replicate(
                    self.mock_api_token, 
                    "test prompt"
                )
            
            assert result is None
    
    def test_upload_image_to_s3_success(self):
        """Test successful S3 upload"""
        with patch('training_image_generator_improved.http') as mock_http:
            # Mock image download
            download_response = Mock()
            download_response.status = 200
            download_response.data = b'mock_image_data'
            mock_http.request.return_value = download_response
            
            with patch('training_image_generator_improved.s3_client') as mock_s3:
                result = upload_image_to_s3(
                    'https://replicate.com/test-image.jpg',
                    'test-folder/test-image.jpg'
                )
                
                assert result == 'https://test-bucket.s3.amazonaws.com/test-folder/test-image.jpg'
                mock_s3.put_object.assert_called_once()
    
    def test_upload_image_to_s3_download_failure(self):
        """Test S3 upload when image download fails"""
        with patch('training_image_generator_improved.http') as mock_http:
            # Mock failed download
            download_response = Mock()
            download_response.status = 404
            mock_http.request.return_value = download_response
            
            result = upload_image_to_s3(
                'https://replicate.com/test-image.jpg',
                'test-folder/test-image.jpg'
            )
            
            assert result is None
    
    def test_get_secret_success(self):
        """Test successful secret retrieval"""
        with patch('training_image_generator_improved.secrets_client') as mock_secrets:
            mock_secrets.get_secret_value.return_value = {
                'SecretString': 'test-secret-value'
            }
            
            result = get_secret('test-secret-name')
            assert result == 'test-secret-value'
    
    def test_get_secret_failure(self):
        """Test secret retrieval failure"""
        with patch('training_image_generator_improved.secrets_client') as mock_secrets:
            mock_secrets.get_secret_value.side_effect = Exception('Secret not found')
            
            result = get_secret('test-secret-name')
            assert result is None
    
    @patch('training_image_generator_improved.generate_single_image_with_replicate')
    @patch('training_image_generator_improved.upload_image_to_s3')
    def test_max_attempts_calculation(self, mock_upload, mock_generate):
        """Test that max attempts are calculated correctly"""
        # Test the formula: min(num_images * 2 + 3, 25)
        test_cases = [
            (5, 13),   # 5 * 2 + 3 = 13
            (10, 23),  # 10 * 2 + 3 = 23
            (15, 25),  # 15 * 2 + 3 = 33, but capped at 25
            (20, 25),  # 20 * 2 + 3 = 43, but capped at 25
        ]
        
        for num_images, expected_max_attempts in test_cases:
            with patch('training_image_generator_improved.get_secret') as mock_get_secret:
                with patch('training_image_generator_improved.dynamodb') as mock_dynamodb:
                    mock_get_secret.return_value = self.mock_api_token
                    mock_table = Mock()
                    mock_dynamodb.Table.return_value = mock_table
                    
                    event = {
                        'character_name': self.character_name,
                        'character_description': self.character_description,
                        'num_images': num_images
                    }
                    
                    with patch('training_image_generator_improved.generate_training_images_with_retry') as mock_generate_func:
                        mock_generate_func.return_value = {
                            'status': 'completed',
                            'completed_images': 0,
                            'current_attempt': 0,
                            'success_rate': 0,
                            'image_urls': []
                        }
                        
                        result = lambda_handler(event, {})
                        
                        # Verify max_attempts was calculated correctly
                        body = json.loads(result['body'])
                        assert body['max_attempts'] == expected_max_attempts
                        
                        # Verify the function was called with correct max_attempts
                        mock_generate_func.assert_called_once()
                        call_args = mock_generate_func.call_args
                        assert call_args.kwargs['max_attempts'] == expected_max_attempts

class TestIntegrationScenarios:
    """Integration tests that simulate real-world scenarios"""
    
    def setup_method(self):
        """Set up test fixtures"""
        os.environ['S3_BUCKET_NAME'] = 'test-bucket'
        os.environ['REPLICATE_API_TOKEN_SECRET'] = 'test-secret'
    
    @patch('training_image_generator_improved.get_secret')
    @patch('training_image_generator_improved.dynamodb')
    @patch('training_image_generator_improved.generate_single_image_with_replicate')
    @patch('training_image_generator_improved.upload_image_to_s3')
    def test_realistic_scenario_70_percent_success_rate(
        self, mock_upload, mock_generate, mock_dynamodb, mock_get_secret
    ):
        """Test a realistic scenario with ~70% success rate like shown in Replicate UI"""
        mock_get_secret.return_value = 'mock_token'
        mock_table = Mock()
        mock_dynamodb.Table.return_value = mock_table
        mock_upload.return_value = 'https://s3.amazonaws.com/bucket/image.jpg'
        
        # Simulate 70% success rate: 7 successes out of 10 attempts
        # Pattern: S=Success, F=Failure
        # S, F, S, S, F, S, S, F, S, S (7 successes, 3 failures)
        mock_generate.side_effect = [
            'https://replicate.com/image1.jpg',  # Success
            None,                                # Failure
            'https://replicate.com/image2.jpg',  # Success
            'https://replicate.com/image3.jpg',  # Success
            None,                                # Failure
            'https://replicate.com/image4.jpg',  # Success
            'https://replicate.com/image5.jpg',  # Success
            None,                                # Failure
        ]
        
        event = {
            'character_name': 'Test Character',
            'character_description': 'A test character description',
            'num_images': 5,
            'job_id': 'test-job-123'
        }
        
        result = lambda_handler(event, {})
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        
        # Should get 5 images (target reached)
        assert body['completed_images'] == 5
        # Should take 8 attempts (7 for the 5 successful + 1 initial failure)
        assert body['current_attempt'] == 8
        # Success rate should be 5/8 = 62.5%
        assert body['success_rate'] == pytest.approx(62.5, rel=1e-1)
        assert body['status'] == 'completed'
        assert len(body['image_urls']) == 5
    
    @patch('training_image_generator_improved.get_secret')
    @patch('training_image_generator_improved.dynamodb')
    @patch('training_image_generator_improved.generate_single_image_with_replicate')
    @patch('training_image_generator_improved.upload_image_to_s3')
    def test_poor_success_rate_scenario(
        self, mock_upload, mock_generate, mock_dynamodb, mock_get_secret
    ):
        """Test scenario with poor success rate - should still try to reach max attempts"""
        mock_get_secret.return_value = 'mock_token'
        mock_table = Mock()
        mock_dynamodb.Table.return_value = mock_table
        mock_upload.return_value = 'https://s3.amazonaws.com/bucket/image.jpg'
        
        # Simulate very poor success rate: only 3 successes out of 15 attempts
        failures = [None] * 12  # 12 failures
        successes = ['https://replicate.com/image.jpg'] * 3  # 3 successes
        
        # Interleave failures and successes: F,F,F,F,S,F,F,F,S,F,F,F,S,F,F
        mock_generate.side_effect = [
            None, None, None, None,  # 4 failures
            'https://replicate.com/image1.jpg',  # Success
            None, None, None,  # 3 failures
            'https://replicate.com/image2.jpg',  # Success
            None, None, None,  # 3 failures
            'https://replicate.com/image3.jpg',  # Success
            None, None  # 2 more failures (hit max attempts)
        ]
        
        event = {
            'character_name': 'Test Character',
            'character_description': 'A test character description',
            'num_images': 10,  # Want 10 images
            'job_id': 'test-job-456'
        }
        
        result = lambda_handler(event, {})
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        
        # Should only get 3 images (poor success rate)
        assert body['completed_images'] == 3
        # Max attempts for 10 images = min(10*2+3, 25) = 23
        assert body['max_attempts'] == 23
        # Should use all 23 attempts (since we need 10 but only got 3)
        assert body['current_attempt'] == 23
        # Success rate should be 3/23 ≈ 13%
        assert body['success_rate'] == pytest.approx(13.04, rel=1e-1)
        assert body['status'] == 'completed'  # Still completed, just with fewer images
        assert len(body['image_urls']) == 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
