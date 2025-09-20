#!/usr/bin/env python3
"""
Standalone script to query MiniMax video generation task status.
Usage: python query_minimax_task.py [task_id]
"""

import os
import sys
import json
import asyncio
import httpx
from pathlib import Path

# Load environment variables from .env file if it exists
def load_env_file():
    """Load environment variables from .env file."""
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

async def query_minimax_task(task_id: str, api_key: str):
    """
    Query MiniMax video generation task status.
    
    Args:
        task_id: The MiniMax task ID to query
        api_key: MiniMax API key
    """
    base_url = os.getenv("MINIMAX_API_BASE_URL", "https://api.minimax.io")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            print(f"Querying task ID: {task_id}")
            print(f"API Base URL: {base_url}")
            print(f"Using API key: {api_key[:10]}...")
            print()
            
            # Query the task status
            response = await client.get(
                f"{base_url}/v1/query/video_generation",
                params={"task_id": task_id},
                headers=headers
            )
            
            print(f"Response Status: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            print()
            
            # Parse response
            result_data = response.json()
            print("Response JSON:")
            print(json.dumps(result_data, indent=2, ensure_ascii=False))
            
            # Check for success
            if response.status_code == 200:
                base_resp = result_data.get("base_resp", {})
                if base_resp.get("status_code") == 0:
                    status = result_data.get("status", "UNKNOWN")
                    print(f"\n✅ Task Status: {status}")
                    
                    if status == "SUCCEEDED":
                        print("🎉 Video generation completed successfully!")
                        
                        # Extract file_id if available
                        file_id = result_data.get("file_id")
                        if file_id:
                            print(f"📁 File ID: {file_id}")
                            print(f"💡 To download the file, run:")
                            print(f"   python retrieve_minimax_file.py {file_id}")
                        
                        # Try to get download URL
                        try:
                            download_response = await client.get(
                                f"{base_url}/v1/video_generation_download",
                                params={"task_id": task_id},
                                headers=headers
                            )
                            if download_response.status_code == 200:
                                download_data = download_response.json()
                                download_url = download_data.get('url')
                                if download_url:
                                    print(f"🔗 Direct Download URL: {download_url}")
                        except Exception as e:
                            print(f"Could not get download URL: {e}")
                            
                    elif status == "PROCESSING":
                        print("⏳ Video is still being generated...")
                    elif status == "FAILED":
                        error_msg = result_data.get("error_msg", "Unknown error")
                        print(f"❌ Video generation failed: {error_msg}")
                else:
                    status_msg = base_resp.get("status_msg", "Unknown error")
                    print(f"❌ API Error: {status_msg}")
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error querying task: {e}")
            return False
    
    return True

def main():
    """Main function."""
    # Load .env file
    load_env_file()
    
    # Get task ID from command line or use default
    if len(sys.argv) > 1:
        task_id = sys.argv[1]
    else:
        task_id = "314470384890055"  # Default task ID from user query
    
    # Get API key from environment
    api_key = os.getenv("MINIMAX_API_KEY")
    if not api_key:
        print("❌ Error: MINIMAX_API_KEY not found in environment variables.")
        print("Please set it in your .env file or environment.")
        print("Example .env file:")
        print("MINIMAX_API_KEY=your_api_key_here")
        sys.exit(1)
    
    # Run the query
    asyncio.run(query_minimax_task(task_id, api_key))

if __name__ == "__main__":
    main()
