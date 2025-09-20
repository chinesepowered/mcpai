#!/usr/bin/env python3
"""
Standalone script to retrieve MiniMax generated files using file ID.
Usage: python retrieve_minimax_file.py [file_id]
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

async def retrieve_file(file_id: str, api_key: str, output_dir: str = "downloads"):
    """
    Retrieve a file from MiniMax using file ID.
    
    Args:
        file_id: The file ID to retrieve
        api_key: MiniMax API key
        output_dir: Directory to save the downloaded file
    """
    base_url = os.getenv("MINIMAX_API_BASE_URL", "https://api.minimax.io")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            print(f"Retrieving file ID: {file_id}")
            print(f"API Base URL: {base_url}")
            print(f"Using API key: {api_key[:10]}...")
            print(f"Output directory: {output_path.absolute()}")
            print()
            
            # Get file information and download URL
            response = await client.get(
                f"{base_url}/v1/files/retrieve",
                params={"file_id": file_id},
                headers=headers
            )
            
            print(f"Response Status: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            print()
            
            if response.status_code != 200:
                print(f"❌ HTTP Error: {response.status_code}")
                print(f"Response: {response.text}")
                return False
            
            # Parse response
            result_data = response.json()
            print("Response JSON:")
            print(json.dumps(result_data, indent=2, ensure_ascii=False))
            print()
            
            # Check for success
            base_resp = result_data.get("base_resp", {})
            if base_resp.get("status_code") != 0:
                status_msg = base_resp.get("status_msg", "Unknown error")
                print(f"❌ API Error: {status_msg}")
                return False
            
            # Extract file information
            file_info = result_data.get("file", {})
            download_url = file_info.get("download_url")
            filename = file_info.get("filename", f"{file_id}.mp4")
            file_size = file_info.get("bytes")
            
            if not download_url:
                print("❌ No download URL found in response")
                return False
            
            print(f"📁 File: {filename}")
            if file_size:
                print(f"📏 Size: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")
            print(f"🔗 Download URL: {download_url}")
            print()
            
            # Download the file
            print("⬇️ Downloading file...")
            download_response = await client.get(download_url)
            
            if download_response.status_code != 200:
                print(f"❌ Download failed: {download_response.status_code}")
                return False
            
            # Save the file
            output_file = output_path / filename
            with open(output_file, "wb") as f:
                f.write(download_response.content)
            
            actual_size = output_file.stat().st_size
            print(f"✅ File downloaded successfully!")
            print(f"📂 Saved to: {output_file.absolute()}")
            print(f"📏 Downloaded size: {actual_size} bytes ({actual_size / 1024 / 1024:.2f} MB)")
            
            return True
            
        except Exception as e:
            print(f"❌ Error retrieving file: {e}")
            return False

def main():
    """Main function."""
    # Load .env file
    load_env_file()
    
    # Get file ID from command line
    if len(sys.argv) > 1:
        file_id = sys.argv[1]
    else:
        print("Usage: python retrieve_minimax_file.py <file_id> [output_directory]")
        print("Example: python retrieve_minimax_file.py abc123def456")
        sys.exit(1)
    
    # Get output directory from command line (optional)
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "downloads"
    
    # Get API key from environment
    api_key = os.getenv("MINIMAX_API_KEY")
    if not api_key:
        print("❌ Error: MINIMAX_API_KEY not found in environment variables.")
        print("Please set it in your .env file or environment.")
        print("Example .env file:")
        print("MINIMAX_API_KEY=your_api_key_here")
        sys.exit(1)
    
    # Run the retrieval
    success = asyncio.run(retrieve_file(file_id, api_key, output_dir))
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
