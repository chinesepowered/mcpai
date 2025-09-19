import os
import logging
import asyncio
import subprocess
from typing import List, Dict, Any, Optional
import httpx
from pydantic import BaseModel

# Configure logging
logger = logging.getLogger(__name__)

class InstagramPost(BaseModel):
    """Model representing an Instagram post."""
    id: str
    caption: str
    image_url: str
    video_url: Optional[str] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    engagement_rate: Optional[float] = None
    timestamp: Optional[str] = None

class BrightDataService:
    """Service for interacting with Bright Data MCP to scrape Instagram content."""
    
    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize the Bright Data service.
        
        Args:
            api_token: Bright Data API token. If not provided, will be loaded from environment.
        """
        self.api_token = api_token or os.getenv("BRIGHTDATA_API_TOKEN")
        if not self.api_token:
            raise ValueError("Bright Data API token not provided and not found in environment")
        
        # MCP process management
        self.mcp_process = None
        self.mcp_port = 8191  # Default MCP port
        self.mcp_base_url = f"http://localhost:{self.mcp_port}"
        
        # Timeout settings
        self.startup_timeout = 30  # seconds
        self.request_timeout = 60  # seconds
    
    async def ensure_mcp_running(self) -> bool:
        """
        Ensure that the Bright Data MCP is running.
        
        Returns:
            bool: True if MCP is running, False otherwise.
        """
        # Check if process is already running
        if self.mcp_process and self.mcp_process.poll() is None:
            try:
                # Verify MCP is responsive
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.mcp_base_url}/status",
                        timeout=5
                    )
                if response.status_code == 200:
                    logger.info("Bright Data MCP is already running")
                    return True
            except (httpx.RequestError, asyncio.TimeoutError):
                logger.warning("Bright Data MCP is running but not responsive")
        
        # Start MCP if not running or not responsive
        return await self._start_mcp()
    
    async def _start_mcp(self) -> bool:
        """
        Start the Bright Data MCP process.
        
        Returns:
            bool: True if MCP started successfully, False otherwise.
        """
        logger.info("Starting Bright Data MCP")
        
        # Kill existing process if it exists
        if self.mcp_process:
            try:
                self.mcp_process.terminate()
                await asyncio.sleep(1)
                if self.mcp_process.poll() is None:
                    self.mcp_process.kill()
            except Exception as e:
                logger.error(f"Error terminating existing MCP process: {str(e)}")
        
        # Start new process
        env = os.environ.copy()
        env["API_TOKEN"] = self.api_token
        
        try:
            self.mcp_process = subprocess.Popen(
                ["npx", "@brightdata/mcp"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            logger.info(f"Bright Data MCP started with PID {self.mcp_process.pid}")
            
            # Wait for MCP to be ready
            start_time = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start_time < self.startup_timeout:
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(
                            f"{self.mcp_base_url}/status",
                            timeout=5
                        )
                    if response.status_code == 200:
                        logger.info("Bright Data MCP is ready")
                        return True
                except (httpx.RequestError, asyncio.TimeoutError):
                    await asyncio.sleep(1)
            
            logger.error("Timed out waiting for Bright Data MCP to start")
            return False
        except Exception as e:
            logger.error(f"Failed to start Bright Data MCP: {str(e)}")
            return False
    
    async def scrape_instagram_user(
        self, 
        username: str = "austinnasso", 
        limit: int = 10
    ) -> List[InstagramPost]:
        """
        Scrape Instagram posts from a specific user.
        
        Args:
            username: Instagram username to scrape
            limit: Maximum number of posts to return
            
        Returns:
            List[InstagramPost]: List of Instagram posts
        """
        # Ensure MCP is running
        if not await self.ensure_mcp_running():
            raise RuntimeError("Failed to start Bright Data MCP")
        
        logger.info(f"Scraping Instagram posts for user: {username}")
        
        # Prepare the request payload
        payload = {
            "url": f"https://www.instagram.com/{username}/",
            "country": "us",
            "collect": {
                "posts": {
                    "limit": limit,
                    "fields": [
                        "id",
                        "shortcode",
                        "caption",
                        "display_url",
                        "video_url",
                        "taken_at_timestamp",
                        "edge_media_preview_like.count",
                        "edge_media_to_comment.count"
                    ]
                },
                "user": {
                    "fields": [
                        "id",
                        "username",
                        "full_name",
                        "biography",
                        "edge_followed_by.count",
                        "edge_follow.count"
                    ]
                }
            }
        }
        
        try:
            # Send request to MCP
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.mcp_base_url}/instagram",
                    json=payload,
                    timeout=self.request_timeout
                )
                
            if response.status_code != 200:
                logger.error(f"Error from Bright Data MCP: {response.status_code} - {response.text}")
                raise RuntimeError(f"Bright Data MCP returned error: {response.status_code}")
            
            # Parse response
            data = response.json()
            
            # Transform to InstagramPost model
            return self._transform_instagram_data(data, username, limit)
        except httpx.RequestError as e:
            logger.error(f"Request error when scraping Instagram: {str(e)}")
            raise RuntimeError(f"Error communicating with Bright Data MCP: {str(e)}")
        except Exception as e:
            logger.error(f"Error scraping Instagram: {str(e)}", exc_info=True)
            raise RuntimeError(f"Error scraping Instagram: {str(e)}")
    
    def _transform_instagram_data(
        self, 
        data: Dict[str, Any], 
        username: str, 
        limit: int
    ) -> List[InstagramPost]:
        """
        Transform raw Instagram data from Bright Data MCP to InstagramPost models.
        
        Args:
            data: Raw data from Bright Data MCP
            username: Instagram username
            limit: Maximum number of posts to return
            
        Returns:
            List[InstagramPost]: List of Instagram posts
        """
        posts = []
        
        try:
            # Extract user data for engagement calculation
            user_data = data.get("user", {})
            follower_count = user_data.get("edge_followed_by", {}).get("count", 0)
            
            # Extract posts
            raw_posts = data.get("posts", [])
            
            for post in raw_posts[:limit]:
                try:
                    # Extract post data
                    post_id = post.get("id") or post.get("shortcode", f"unknown_{len(posts)}")
                    caption = post.get("caption", "")
                    image_url = post.get("display_url", "")
                    video_url = post.get("video_url")
                    
                    # Extract engagement metrics
                    likes = post.get("edge_media_preview_like", {}).get("count", 0)
                    comments = post.get("edge_media_to_comment", {}).get("count", 0)
                    
                    # Calculate engagement rate if follower count is available
                    engagement_rate = None
                    if follower_count > 0:
                        engagement_rate = round((likes + comments) / follower_count * 100, 2)
                    
                    # Extract timestamp
                    timestamp = None
                    if "taken_at_timestamp" in post:
                        from datetime import datetime
                        timestamp_value = post.get("taken_at_timestamp")
                        if isinstance(timestamp_value, (int, float)):
                            timestamp = datetime.fromtimestamp(timestamp_value).isoformat()
                    
                    # Create InstagramPost
                    instagram_post = InstagramPost(
                        id=post_id,
                        caption=caption,
                        image_url=image_url,
                        video_url=video_url,
                        likes=likes,
                        comments=comments,
                        engagement_rate=engagement_rate,
                        timestamp=timestamp
                    )
                    posts.append(instagram_post)
                except Exception as e:
                    logger.warning(f"Error processing Instagram post: {str(e)}")
            
            logger.info(f"Successfully processed {len(posts)} Instagram posts for {username}")
            return posts
        except Exception as e:
            logger.error(f"Error transforming Instagram data: {str(e)}", exc_info=True)
            # Return whatever posts were successfully processed
            return posts
    
    async def close(self):
        """Close the service and terminate the MCP process."""
        if self.mcp_process and self.mcp_process.poll() is None:
            logger.info(f"Terminating Bright Data MCP (PID: {self.mcp_process.pid})")
            try:
                self.mcp_process.terminate()
                await asyncio.sleep(2)
                if self.mcp_process.poll() is None:
                    logger.warning(f"Force killing Bright Data MCP (PID: {self.mcp_process.pid})")
                    self.mcp_process.kill()
            except Exception as e:
                logger.error(f"Error terminating Bright Data MCP: {str(e)}")
