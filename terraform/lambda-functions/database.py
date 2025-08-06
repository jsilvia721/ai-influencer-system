import json
import sqlite3
import boto3
import os
from datetime import datetime

def handler(event, context):
    """
    Simple database operations using SQLite stored in S3
    Ultra-cheap alternative to RDS for MVP
    """
    
    s3_client = boto3.client('s3')
    bucket_name = os.environ.get('S3_BUCKET')
    db_key = 'database/ai_influencer.db'
    local_db_path = '/tmp/ai_influencer.db'
    
    # Download database from S3 if it exists
    try:
        s3_client.download_file(bucket_name, db_key, local_db_path)
    except:
        # Database doesn't exist yet, will be created
        pass
    
    # Connect to SQLite database
    conn = sqlite3.connect(local_db_path)
    cursor = conn.cursor()
    
    # Initialize tables if they don't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            personality TEXT,
            platforms TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            content_type TEXT,
            content_text TEXT,
            content_url TEXT,
            platform TEXT,
            posted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (character_id) REFERENCES characters (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER,
            platform TEXT,
            platform_post_id TEXT,
            status TEXT,
            posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (content_id) REFERENCES content (id)
        )
    ''')
    
    # Insert default character if none exist
    cursor.execute('SELECT COUNT(*) FROM characters')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO characters (name, personality, platforms)
            VALUES (?, ?, ?)
        ''', ('AI_Sophia', 'Tech enthusiast and startup advisor', 'twitter,linkedin'))
    
    conn.commit()
    
    # Handle different operations based on event
    operation = event.get('operation', 'get_characters')
    
    if operation == 'get_characters':
        cursor.execute('SELECT * FROM characters')
        characters = []
        for row in cursor.fetchall():
            characters.append({
                'id': row[0],
                'name': row[1],
                'personality': row[2],
                'platforms': row[3].split(',') if row[3] else [],
                'created_at': row[4]
            })
        result = {'characters': characters}
    
    elif operation == 'add_content':
        data = event.get('data', {})
        cursor.execute('''
            INSERT INTO content (character_id, content_type, content_text, content_url, platform)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            data.get('character_id'),
            data.get('content_type'),
            data.get('content_text'),
            data.get('content_url'),
            data.get('platform')
        ))
        conn.commit()
        result = {'success': True, 'content_id': cursor.lastrowid}
    
    elif operation == 'get_content':
        character_id = event.get('character_id')
        if character_id:
            cursor.execute('SELECT * FROM content WHERE character_id = ? ORDER BY created_at DESC LIMIT 10', (character_id,))
        else:
            cursor.execute('SELECT * FROM content ORDER BY created_at DESC LIMIT 10')
        
        content = []
        for row in cursor.fetchall():
            content.append({
                'id': row[0],
                'character_id': row[1],
                'content_type': row[2],
                'content_text': row[3],
                'content_url': row[4],
                'platform': row[5],
                'posted_at': row[6],
                'created_at': row[7]
            })
        result = {'content': content}
    
    else:
        result = {'error': 'Unknown operation'}
    
    conn.close()
    
    # Upload updated database back to S3
    try:
        s3_client.upload_file(local_db_path, bucket_name, db_key)
    except Exception as e:
        print(f"Error uploading database to S3: {e}")
    
    return result
