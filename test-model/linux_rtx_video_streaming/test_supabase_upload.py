#!/usr/bin/env python3
"""
Test Supabase Upload - Created 2025-10-22 19:04 CST
Tests Supabase connection and uploads a small test file
"""

import os
from datetime import datetime
from supabase import create_client, Client

# Supabase Configuration
SUPABASE_URL = "https://wdpeoyugsxqnpwwtkqsl.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndkcGVveXVnc3hxbnB3d3RrcXNsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQxNDgwNzgsImV4cCI6MjA1OTcyNDA3OH0.9bUpuZCOZxDSH3KsIu6FwWZyAvnV5xPJGNpO3luxWOE"
STORAGE_BUCKET = "ASE"

def test_upload():
    """Test Supabase connection and upload"""
    print("Testing Supabase connection...")

    try:
        # Initialize Supabase client
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        print("✓ Supabase client initialized")

        # Create a small test file
        test_content = f"Test upload at {datetime.now().isoformat()}"
        test_filename = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        test_path = f"test_uploads/{test_filename}"

        print(f"Uploading test file: {test_path}")

        # Upload to Supabase
        response = supabase.storage.from_(STORAGE_BUCKET).upload(
            path=test_path,
            file=test_content.encode('utf-8'),
            file_options={"content-type": "text/plain"}
        )

        print(f"✓ Upload successful!")
        print(f"Response: {response}")

        # Generate public URL
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{STORAGE_BUCKET}/{test_path}"
        print(f"Public URL: {public_url}")

        return True

    except Exception as e:
        print(f"✗ Upload failed: {str(e)}")
        return False

if __name__ == "__main__":
    test_upload()