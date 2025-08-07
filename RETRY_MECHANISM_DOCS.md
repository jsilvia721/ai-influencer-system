# Training Image Generation with Retry Mechanism

This document describes the robust retry mechanism implemented for training image generation, designed to ensure consistent generation of the requested number of images while handling Replicate API failures gracefully.

## Problem Description

The Replicate API for image generation can have varying success rates, as shown in your prediction table where some requests succeed and others fail. To ensure users get the requested number of training images, we need a robust retry system that:

1. Continues attempting until the target number is reached or max attempts is hit
2. Provides real-time progress feedback
3. Shows meaningful success rate statistics
4. Handles various failure scenarios gracefully

## Implementation Overview

### Backend Implementation (`training_image_generator_improved.py`)

The improved backend implementation includes:

- **Robust Retry Logic**: Continues generating until `num_images` successful images or `max_attempts` is reached
- **Real-time Progress Tracking**: Updates DynamoDB with current progress after each attempt
- **Success Rate Calculation**: Tracks and reports success percentage in real-time
- **Smart Max Attempts Formula**: `min(num_images * 2 + 3, 25)` to balance cost and success probability

#### Key Features:
- Cycles through 24 varied prompts to ensure diversity
- Updates DynamoDB after every attempt (success or failure)
- Implements proper error handling and logging
- Uses Decimal type for precise success rate calculations

### Frontend Implementation (`CharacterManagement.tsx`)

The frontend provides rich visual feedback:

- **Real-time Progress Bars**: Show image completion and attempt progress
- **Success Rate Display**: Color-coded success percentage
- **Retry Configuration Preview**: Shows max attempts before starting
- **Live Status Updates**: Polls backend every 10 seconds for updates

### Testing Infrastructure

#### Mock API (`mockApi.ts`)
- Simulates realistic success/failure patterns
- Provides three success rate scenarios: high (85%), medium (65%), low (35%)
- Generates progress updates every 2 seconds
- No API costs during testing

#### Comprehensive Test Suite (`test_training_image_generator.py`)
- 15+ test cases covering all scenarios
- Mocks all external dependencies (Replicate, S3, DynamoDB, Secrets Manager)
- Tests success, failure, timeout, and edge cases
- Validates retry logic and max attempts calculation

## Key Metrics and Configuration

### Max Attempts Formula
```
max_attempts = min(num_images * 2 + 3, 25)
```

Examples:
- 5 images → 13 max attempts
- 10 images → 23 max attempts  
- 20 images → 25 max attempts (capped)

### Success Rate Calculation
```
success_rate = (completed_images / current_attempt) * 100
```

Updated in real-time after each attempt.

### Retry Strategy
1. **Generate**: Attempt to create image with Replicate
2. **Upload**: If generation succeeds, upload to S3
3. **Track**: Update progress regardless of success/failure
4. **Continue**: Retry until target reached or max attempts hit
5. **Complete**: Mark job as completed (may have partial results)

## Usage Instructions

### For Development/Testing (No API Costs)

1. **Enable Mock Mode**:
   ```bash
   # In ai-influencer-ui/.env.local
   REACT_APP_USE_MOCK_API=true
   ```

2. **Run Tests**:
   ```bash
   cd /Users/josh/dev/ai-influencer-system
   python run_tests.py
   ```

3. **Test in UI**: 
   - Start development server
   - Go to "Generate Images" tab
   - Submit a generation request
   - Watch real-time progress with simulated failures/successes

### For Production Use

1. **Disable Mock Mode**:
   ```bash
   # In ai-influencer-ui/.env.local
   REACT_APP_USE_MOCK_API=false
   # OR remove the variable entirely
   ```

2. **Deploy Backend**: Deploy the improved `training_image_generator_improved.py`

3. **Monitor Progress**: Use the UI to track job progress and success rates

## Real-World Scenarios Handled

### High Success Rate (85%+)
- Typical scenario with good prompts and stable API
- Usually completes with fewer attempts than maximum
- Green success rate indicator in UI

### Medium Success Rate (50-80%)
- Common scenario with some prompt/content restrictions
- May require 60-80% of max attempts
- Yellow/orange success rate indicator

### Low Success Rate (20-50%)
- Challenging scenarios (content restrictions, API issues)
- Uses most or all available attempts
- Red success rate indicator
- Still delivers partial results

### Edge Cases
- **All Attempts Fail**: Job completes with 0 images, clear error message
- **Network Issues**: Individual failures don't stop the process
- **Partial Success**: Completes with fewer than requested images
- **Perfect Success**: Gets exact number on first attempts

## Monitoring and Debugging

### Console Logs
The system provides detailed logging:
```
Mock Job job_123: Attempt 3/13, Images: 2/5, Success Rate: 66.7%
```

### DynamoDB Updates
Each job record includes:
- `current_attempt`: Current attempt number
- `completed_images`: Successfully generated images
- `success_rate`: Real-time success percentage
- `max_attempts`: Configured maximum attempts
- `status`: 'processing' or 'completed'

### UI Indicators
- Progress bars for image completion and attempt usage
- Color-coded success rates
- Real-time status updates
- Detailed job information cards

## Cost Control Features

1. **Max Attempts Cap**: Never exceed 25 attempts regardless of image count
2. **Smart Retry Logic**: Only retry on actual failures, not successes
3. **Real-time Monitoring**: Stop early if needed via UI
4. **Transparent Reporting**: Always shows total attempts and costs

## Testing Results

The test suite validates:
- ✅ Perfect success scenarios (100% success rate)
- ✅ Partial success scenarios (60-80% success rate)  
- ✅ Poor success scenarios (20-40% success rate)
- ✅ Complete failure scenarios (0% success rate)
- ✅ Max attempts calculations for various image counts
- ✅ Real-time progress updates
- ✅ Error handling and recovery
- ✅ Mock API functionality

## Future Enhancements

Potential improvements:
1. **Adaptive Retry Delays**: Longer delays after failures
2. **Prompt Optimization**: Learn which prompts succeed more often
3. **Batch Processing**: Generate multiple images per API call
4. **Cost Tracking**: Show estimated costs based on attempts
5. **Success Prediction**: Predict likelihood of reaching target

## Files Modified/Created

### Backend
- `lambda/training_image_generator_improved.py` - Enhanced with retry logic
- `tests/test_training_image_generator.py` - Comprehensive test suite
- `run_tests.py` - Test runner script

### Frontend  
- `ai-influencer-ui/src/utils/mockApi.ts` - Mock API for testing
- `ai-influencer-ui/src/pages/CharacterManagement.tsx` - Enhanced UI
- `ai-influencer-ui/.env.example` - Environment configuration

### Documentation
- `RETRY_MECHANISM_DOCS.md` - This documentation

This implementation provides a robust, user-friendly, and cost-effective solution for generating training images with built-in resilience against API failures.
