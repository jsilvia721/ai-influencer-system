# Replicate Disaster Recovery Sync System

## Overview
This system provides complete disaster recovery capabilities by syncing all content generation jobs with Replicate's API. It can rebuild the entire DynamoDB table from scratch using real Replicate data.

## Features

### 🚀 Enhanced Pagination Support
- Fetches **ALL** predictions from Replicate using cursor-based pagination
- Processes up to 2,000 predictions (configurable)
- Handles API rate limiting with automatic backoff
- Shows real-time progress during data fetching

### 🎯 OpenAPI Schema Compliant
Based on Replicate's official OpenAPI schema, the system handles:
- **5 status values**: `starting`, `processing`, `succeeded`, `failed`, `canceled`
- **Complete data fields**: `id`, `input`, `logs`, `metrics`, `model`, `output`, `urls`, `version`, etc.
- **Additional fields**: `data_removed`, `deployment`, error categorization

### 💾 Optimal Schema v2.0
Stores comprehensive Replicate data in organized structure:

#### Core Fields
- `job_id` - Unique identifier
- `created_at`, `updated_at` - Timestamps
- `status` - Internal status mapping

#### Job Request Data
- `job_type` - image|video|complete_content
- `user_prompt` - Original user input
- `character_id`, `character_name` - Character references
- `character_trigger_word`, `lora_model_url` - Model info

#### Replicate Prediction Data
- `prediction_id` - Replicate prediction ID
- `prediction_status` - Raw Replicate status
- `prediction_created_at`, `prediction_started_at`, `prediction_completed_at` - Full timing
- `input_params` - Complete input parameters
- `model_info` - Parsed model owner/name/version
- `execution_logs` - Full execution logs
- `metrics` - Performance data
- `urls` - API endpoints
- `output_data` - Raw output

#### Error Handling
- `error_message` - Human readable
- `error_details` - Structured categorization
- `data_removed` - Replicate data removal flag

## Usage

### Disaster Recovery (Bootstrap Mode)
Completely rebuild DynamoDB from Replicate data:

```bash
curl -X POST {API_ENDPOINT}/sync-replicate-jobs \
  -H "Content-Type: application/json" \
  -d '{"bootstrap": true}'
```

### Regular Sync
Update existing jobs with latest Replicate status:

```bash
curl -X POST {API_ENDPOINT}/sync-replicate-jobs \
  -H "Content-Type: application/json" \
  -d '{}'
```

## API Response Structure

### Bootstrap Response
```json
{
  "message": "Bootstrap sync completed successfully",
  "mode": "bootstrap", 
  "predictions_processed": 150,
  "jobs_created": 145,
  "bootstrap_results": [...]
}
```

### Regular Sync Response
```json
{
  "message": "Sync completed successfully",
  "jobs_processed": 50,
  "predictions_checked": 150,
  "jobs_updated": 12,
  "sync_results": [...]
}
```

## System Architecture

### Lambda Configuration
- **Function**: `ai-influencer-system-dev-sync-replicate-jobs`
- **Timeout**: 15 minutes (900 seconds)
- **Memory**: 512 MB
- **Environment Variables**:
  - `CONTENT_JOBS_TABLE_NAME`: `ai-influencer-content-jobs`
  - `REPLICATE_API_TOKEN_SECRET`: Secret name for API token

### Data Flow
1. **Authentication** - Retrieve Replicate API token from AWS Secrets Manager
2. **Data Retrieval** - Paginated fetch of ALL predictions from Replicate
3. **Processing** - Match/create jobs with optimal schema
4. **Storage** - Save complete data to DynamoDB
5. **Response** - Return detailed sync results

### Error Handling
- **Rate Limiting**: Automatic 5-second backoff
- **Network Errors**: Continue with partial data
- **Data Validation**: Skip malformed predictions
- **DynamoDB Errors**: Log and continue processing

## Disaster Recovery Scenarios

### Complete System Recovery
1. Clear DynamoDB table (if needed)
2. Run bootstrap sync
3. System rebuilds from Replicate with all rich data
4. Frontend displays complete job history

### Partial Data Loss
1. Run regular sync to update missing data
2. System matches existing jobs with Replicate predictions
3. Updates missing fields and status changes

### Data Validation
All data stored matches Replicate's OpenAPI schema exactly, ensuring:
- Complete audit trail
- Rich debugging information
- Full error context
- Performance metrics
- Execution logs

## Frontend Integration
The frontend automatically displays all synced data including:
- Job status and results
- Complete execution logs
- Performance metrics
- Error details with categorization
- Model and version information
- Full input parameters

## Monitoring
The sync system provides comprehensive logging:
- Batch processing progress
- Individual job sync status
- Error categorization and details
- Performance metrics
- API rate limiting status

This system ensures complete disaster recovery capabilities while maintaining rich data for debugging, analytics, and user transparency.
