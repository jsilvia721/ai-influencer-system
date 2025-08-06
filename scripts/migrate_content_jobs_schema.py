#!/usr/bin/env python3
"""
Content Jobs Schema Migration Script

This script migrates the existing content_jobs table to a unified, consistent schema
that properly handles all data from Replicate and provides better error reporting.

New Unified Schema:
- job_id (HASH): Unique job identifier
- character_id: Character this job belongs to
- character_name: Character name (for easier querying)
- type: 'image' | 'video' (simplified, no more 'complete')
- status: 'processing' | 'completed' | 'failed' | 'cancelled'
- prompt: User's generation prompt
- created_at: Job creation timestamp
- updated_at: Last update timestamp
- completed_at: Job completion timestamp (optional)

# Input data
- input_image_url: For video generation (optional)
- trigger_word: LoRA trigger word (for images)
- lora_model_url: LoRA model reference (for images)

# Output data
- result_url: Final output URL (unified field)
- result_type: 'image' | 'video' (what type of result)
- result_metadata: Additional result info (JSON)

# Replicate integration
- replicate_prediction_id: Replicate job ID
- replicate_status: Raw status from Replicate
- replicate_model: Model used on Replicate
- replicate_input: Raw input sent to Replicate (JSON)
- replicate_output: Raw output from Replicate (JSON)

# Error handling
- error_message: Human readable error
- error_details: Technical error details (JSON)
- retry_count: Number of retries attempted
"""

import json
import boto3
import os
from datetime import datetime, timezone
from decimal import Decimal

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')

# Table name
TABLE_NAME = 'ai-influencer-content-jobs'

def decimal_default(obj):
    """JSON serializer for DynamoDB Decimal types"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def migrate_job_record(old_job):
    """Migrate a single job record to the new schema"""
    
    # Start with the core fields that should always exist
    new_job = {
        'job_id': old_job.get('job_id'),
        'character_id': old_job.get('character_id', ''),
        'character_name': old_job.get('character_name', 'Unknown'),
        'prompt': old_job.get('prompt', ''),
        'created_at': old_job.get('created_at', datetime.now(timezone.utc).isoformat()),
        'updated_at': old_job.get('updated_at', datetime.now(timezone.utc).isoformat())
    }
    
    # Handle job type - simplify to just 'image' or 'video'
    old_type = old_job.get('type', 'image')
    if old_type == 'complete':
        # For complete jobs, determine type based on what was actually produced
        if old_job.get('video_url'):
            new_job['type'] = 'video'
            new_job['result_type'] = 'video'
        else:
            new_job['type'] = 'image'
            new_job['result_type'] = 'image'
    else:
        new_job['type'] = old_type
        new_job['result_type'] = old_type
    
    # Standardize status
    old_status = old_job.get('status', 'processing')
    status_mapping = {
        'generating': 'processing',
        'generating_image': 'processing',
        'generating_video': 'processing',
        'completed': 'completed',
        'failed': 'failed',
        'processing': 'processing',
        'starting': 'processing',
        'succeeded': 'completed'
    }
    new_job['status'] = status_mapping.get(old_status, old_status)
    
    # Handle completion timestamp
    if old_job.get('completed_at'):
        new_job['completed_at'] = old_job['completed_at']
    
    # Unify result URLs - prioritize the most appropriate URL
    result_url = None
    
    # Priority order: output_url -> video_url -> image_url
    if old_job.get('output_url'):
        result_url = old_job['output_url']
    elif old_job.get('video_url'):
        result_url = old_job['video_url']
        new_job['result_type'] = 'video'
    elif old_job.get('image_url'):
        result_url = old_job['image_url']
        new_job['result_type'] = 'image'
    
    if result_url:
        new_job['result_url'] = result_url
    
    # Handle input data
    if old_job.get('input_image_url'):
        new_job['input_image_url'] = old_job['input_image_url']
    
    if old_job.get('trigger_word'):
        new_job['trigger_word'] = old_job['trigger_word']
    
    if old_job.get('lora_model_url'):
        new_job['lora_model_url'] = old_job['lora_model_url']
    
    # Handle Replicate data
    if old_job.get('replicate_prediction_id'):
        new_job['replicate_prediction_id'] = old_job['replicate_prediction_id']
    
    if old_job.get('replicate_status'):
        new_job['replicate_status'] = old_job['replicate_status']
    
    # Handle errors - unify error fields
    error_message = old_job.get('error')
    if error_message:
        new_job['error_message'] = error_message
        
        # Try to provide more context for common errors
        if 'LoRA' in error_message:
            new_job['error_details'] = {
                'category': 'model_error',
                'component': 'lora',
                'original_error': error_message
            }
        elif 'Kling' in error_message:
            new_job['error_details'] = {
                'category': 'model_error', 
                'component': 'kling',
                'original_error': error_message
            }
        else:
            new_job['error_details'] = {
                'category': 'unknown',
                'original_error': error_message
            }
    
    # Initialize retry count
    new_job['retry_count'] = 0
    
    # Create result metadata if we have extra info
    result_metadata = {}
    for key in ['aspect_ratio', 'duration', 'quality', 'style']:
        if old_job.get(key):
            result_metadata[key] = old_job[key]
    
    if result_metadata:
        new_job['result_metadata'] = result_metadata
    
    return new_job

def backup_table():
    """Create a backup of the current table"""
    print("Creating backup of current table...")
    
    table = dynamodb.Table(TABLE_NAME)
    response = table.scan()
    items = response.get('Items', [])
    
    # Handle pagination
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))
    
    backup_filename = f"content_jobs_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(backup_filename, 'w') as f:
        json.dump(items, f, default=decimal_default, indent=2)
    
    print(f"Backup saved to {backup_filename} ({len(items)} items)")
    return items

def migrate_all_records(items):
    """Migrate all records to the new schema"""
    print(f"Migrating {len(items)} records...")
    
    table = dynamodb.Table(TABLE_NAME)
    migrated_count = 0
    error_count = 0
    
    for item in items:
        try:
            # Migrate the record
            new_item = migrate_job_record(item)
            
            # Update the record in place
            table.put_item(Item=new_item)
            migrated_count += 1
            
            if migrated_count % 10 == 0:
                print(f"Migrated {migrated_count} records...")
                
        except Exception as e:
            print(f"Error migrating record {item.get('job_id', 'unknown')}: {str(e)}")
            error_count += 1
    
    print(f"Migration complete: {migrated_count} successful, {error_count} errors")
    return migrated_count, error_count

def verify_migration():
    """Verify the migration was successful"""
    print("Verifying migration...")
    
    table = dynamodb.Table(TABLE_NAME)
    response = table.scan()
    items = response.get('Items', [])
    
    # Check for required fields
    required_fields = ['job_id', 'type', 'status', 'created_at', 'updated_at']
    
    valid_count = 0
    invalid_count = 0
    
    for item in items:
        valid = all(field in item for field in required_fields)
        if valid:
            valid_count += 1
        else:
            invalid_count += 1
            missing_fields = [field for field in required_fields if field not in item]
            print(f"Invalid record {item.get('job_id', 'unknown')}: missing {missing_fields}")
    
    print(f"Verification complete: {valid_count} valid records, {invalid_count} invalid records")
    
    # Show some statistics
    types = {}
    statuses = {}
    
    for item in items:
        item_type = item.get('type', 'unknown')
        item_status = item.get('status', 'unknown')
        
        types[item_type] = types.get(item_type, 0) + 1
        statuses[item_status] = statuses.get(item_status, 0) + 1
    
    print(f"Types: {dict(types)}")
    print(f"Statuses: {dict(statuses)}")
    
    # Show error statistics
    error_count = sum(1 for item in items if item.get('error_message'))
    print(f"Jobs with errors: {error_count}")

def main():
    """Main migration function"""
    print("Starting Content Jobs Schema Migration")
    print("=====================================")
    
    try:
        # Step 1: Backup current data
        items = backup_table()
        
        # Step 2: Migrate all records
        migrated_count, error_count = migrate_all_records(items)
        
        # Step 3: Verify migration
        verify_migration()
        
        print("\nMigration Summary:")
        print(f"- Original records: {len(items)}")
        print(f"- Successfully migrated: {migrated_count}")
        print(f"- Migration errors: {error_count}")
        
        if error_count == 0:
            print("\n✅ Migration completed successfully!")
        else:
            print(f"\n⚠️ Migration completed with {error_count} errors. Check logs above.")
            
    except Exception as e:
        print(f"Migration failed: {str(e)}")
        raise

if __name__ == "__main__":
    main()
