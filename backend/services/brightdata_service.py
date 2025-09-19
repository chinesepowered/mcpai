import os
import logging
import asyncio
import signal
import time
import psutil
import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

# Import MCP client libraries
import mcp
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client

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
    
    # Class-level lock to prevent concurrent MCP startup attempts
    _startup_lock = asyncio.Lock()
    _instance = None
    _pid_file = os.path.join(os.path.expanduser("~"), ".brightdata_mcp.pid")
    
    def __new__(cls, *args, **kwargs):
        """Implement singleton pattern to ensure only one service instance exists."""
        if cls._instance is None:
            cls._instance = super(BrightDataService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize the Bright Data service.
        
        Args:
            api_token: Bright Data API token. If not provided, will be loaded from environment.
        """
        # Only initialize once (singleton pattern)
        if hasattr(self, 'initialized') and self.initialized:
            return
            
        self.api_token = api_token or os.getenv("BRIGHTDATA_API_TOKEN")
        if not self.api_token:
            raise ValueError("Bright Data API token not provided and not found in environment")
        
        # MCP process management
        self.mcp_process = None
        self.mcp_pid = None
        self.mcp_client = None
        self.mcp_session = None
        self.mcp_context = None  # async context returned by stdio_client
        
        # Timeout and retry settings
        self.startup_timeout = 30  # seconds
        self.request_timeout = 60  # seconds
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        
        # Health check settings
        self.health_check_interval = 60  # seconds
        self.last_health_check = 0
        
        # Mark as initialized
        self.initialized = True
        
        # Try to restore existing process if PID file exists
        self._restore_from_pid_file()
    
    def _restore_from_pid_file(self):
        """Attempt to restore MCP process from PID file if it exists."""
        try:
            if os.path.exists(self._pid_file):
                with open(self._pid_file, 'r') as f:
                    pid = int(f.read().strip())
                
                # Check if process is running
                if self._is_process_running(pid):
                    logger.info(f"Restored Bright Data MCP process from PID file: {pid}")
                    self.mcp_pid = pid
                else:
                    logger.info(f"Found stale PID file for Bright Data MCP: {pid}")
                    os.unlink(self._pid_file)
        except Exception as e:
            logger.warning(f"Error restoring from PID file: {str(e)}")
            # Remove potentially corrupted PID file
            if os.path.exists(self._pid_file):
                os.unlink(self._pid_file)
    
    def _is_process_running(self, pid: int) -> bool:
        """Check if a process with the given PID is running."""
        try:
            process = psutil.Process(pid)
            # Check if it's actually our MCP process
            if "brightdata" in " ".join(process.cmdline()).lower() or "@brightdata/mcp" in " ".join(process.cmdline()).lower():
                return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
            return False
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
    
    async def ensure_mcp_running(self) -> bool:
        """
        Ensure that the Bright Data MCP is running.
        Uses a lock to prevent concurrent startup attempts.
        
        Returns:
            bool: True if MCP is running, False otherwise.
        """
        # First check if we need to do a health check
        current_time = time.time()
        if self.mcp_pid and (current_time - self.last_health_check) > self.health_check_interval:
            self.last_health_check = current_time
            
            # Check if process is still running
            if not self._is_process_running(self.mcp_pid):
                logger.warning(f"Bright Data MCP (PID: {self.mcp_pid}) is not running, will restart")
                self.mcp_pid = None
                self.mcp_client = None
                self.mcp_session = None
                # Clean up PID file
                if os.path.exists(self._pid_file):
                    os.unlink(self._pid_file)
        
        # If we have a valid PID and client, check if it's responsive
        if self.mcp_pid and self.mcp_client and self.mcp_session:
            try:
                # Ping the MCP server to check if it's responsive
                await self.mcp_session.ping()
                return True
            except Exception as e:
                logger.warning(f"Bright Data MCP client is not responsive: {str(e)}")
                self.mcp_pid = None
                self.mcp_client = None
                self.mcp_session = None
        
        # Acquire lock to prevent concurrent startup attempts
        async with self._startup_lock:
            # Double-check if another thread started the process while we were waiting
            if self.mcp_pid and self.mcp_client and self.mcp_session:
                return True
            
            # Start MCP if not running
            return await self._start_mcp()
    
    async def _start_mcp(self) -> bool:
        """
        Start the Bright Data MCP process and connect to it.
        
        Returns:
            bool: True if MCP started successfully, False otherwise.
        """
        logger.info("Starting Bright Data MCP")
        
        # Kill existing process if it exists
        await self._cleanup_existing_process()
        
        try:
            # Create stdio server parameters
            server_params = mcp.StdioServerParameters(
                command="npx",
                args=["@brightdata/mcp"],
                env={**os.environ, "API_TOKEN": self.api_token}
            )
            
            # Create MCP streams and session
            self.mcp_context = stdio_client(server_params)
            read_stream, write_stream = await self.mcp_context.__aenter__()
            self.mcp_session = ClientSession(read_stream, write_stream)
            
            # Get the PID of the process
            # Note: We need to find a way to get the PID from the MCP client
            # For now, we'll use psutil to find the process
            for proc in psutil.process_iter(['pid', 'cmdline']):
                try:
                    if proc.info['cmdline'] and "@brightdata/mcp" in " ".join(proc.info['cmdline']):
                        self.mcp_pid = proc.info['pid']
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            if self.mcp_pid:
                logger.info(f"Bright Data MCP started with PID {self.mcp_pid}")
                
                # Save PID to file
                with open(self._pid_file, 'w') as f:
                    f.write(str(self.mcp_pid))
            
            # Initialize the session (MCP client handles the protocol automatically)
            await self.mcp_session.initialize()
            
            # Ping to verify connection
            await self.mcp_session.ping()
            
            logger.info("Bright Data MCP client connected successfully")
            return True
                
        except Exception as e:
            logger.error(f"Failed to start Bright Data MCP: {str(e)}")
            # Cleanup on error
            await self._cleanup_existing_process()
            if os.path.exists(self._pid_file):
                os.unlink(self._pid_file)
            return False
    
    async def _cleanup_existing_process(self):
        """Clean up existing MCP process with proper signal handling."""
        # Close MCP client and session if they exist
        if self.mcp_session:
            try:
                # ClientSession has no close() – context closed separately
                pass
            except Exception as e:
                logger.error(f"Error closing MCP session: {str(e)}")
            self.mcp_client = None
            self.mcp_session = None
        # Exit stdio_client context
        if self.mcp_context:
            try:
                await self.mcp_context.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error exiting MCP stdio context: {e}")
            self.mcp_context = None
        
        # Try to terminate by PID if we have it
        if self.mcp_pid and self._is_process_running(self.mcp_pid):
            try:
                logger.info(f"Terminating Bright Data MCP by PID: {self.mcp_pid}")
                # Try to kill the process group
                os.killpg(os.getpgid(self.mcp_pid), signal.SIGTERM)
                
                # Wait for process to terminate
                for _ in range(5):  # Wait up to 5 seconds
                    if not self._is_process_running(self.mcp_pid):
                        break
                    await asyncio.sleep(1)
                
                # Force kill if still running
                if self._is_process_running(self.mcp_pid):
                    logger.warning(f"Force killing Bright Data MCP by PID: {self.mcp_pid}")
                    os.killpg(os.getpgid(self.mcp_pid), signal.SIGKILL)
            except Exception as e:
                logger.error(f"Error terminating Bright Data MCP by PID: {str(e)}")
        
        # Reset process tracking
        self.mcp_process = None
        self.mcp_pid = None
    
    async def scrape_instagram_user(
        self, 
        username: str = "austinnasso", 
        limit: int = 10
    ) -> List[InstagramPost]:
        """
        Scrape Instagram posts from a specific user using Bright Data MCP.
        
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
        
        # Implement retry logic for API requests
        for attempt in range(self.max_retries):
            try:
                # Call the Instagram scraping tool
                tool_result = await self.mcp_session.call_tool(
                    mcp.CallToolRequest(
                        name="instagram",
                        arguments=payload
                    )
                )
                
                # Parse the result
                result_data = json.loads(tool_result.result)
                
                # Transform to InstagramPost models
                posts = self._transform_instagram_data(result_data, username, limit)
                logger.info(f"Successfully scraped {len(posts)} Instagram posts for {username}")
                return posts
                
            except Exception as e:
                logger.error(f"Error scraping Instagram (attempt {attempt + 1}/{self.max_retries}): {str(e)}")
                
                # Check if we should retry
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay} seconds")
                    await asyncio.sleep(delay)
                    
                    # Check if MCP is still responsive
                    if not await self.ensure_mcp_running():
                        logger.warning("MCP became unresponsive, restarting")
                    
                    continue
                
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
        # Close MCP session if it exists
        if self.mcp_session:
            # ClientSession does not expose an explicit close method.
            # Simply drop the references so the GC can clean them up.
            self.mcp_client = None
            self.mcp_session = None
        # Exit stdio context
        if self.mcp_context:
            try:
                await self.mcp_context.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error exiting MCP stdio context: {e}")
            self.mcp_context = None
        
        # Clean up process
        await self._cleanup_existing_process()
        
        # Remove PID file
        if os.path.exists(self._pid_file):
            try:
                os.unlink(self._pid_file)
            except Exception as e:
                logger.error(f"Error removing PID file: {str(e)}")
