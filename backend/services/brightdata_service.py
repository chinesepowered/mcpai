import os
import logging
import asyncio
import subprocess
import signal
import time
import psutil
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
        self.mcp_port = 8191  # Default MCP port
        self.mcp_base_url = f"http://localhost:{self.mcp_port}"
        
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
    
    async def _check_mcp_health(self) -> bool:
        """Check if the MCP server is healthy and responsive."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.mcp_base_url}/status",
                    timeout=5
                )
            return response.status_code == 200
        except (httpx.RequestError, asyncio.TimeoutError):
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
            
            # Check if process is still running and healthy
            if not self._is_process_running(self.mcp_pid) or not await self._check_mcp_health():
                logger.warning(f"Bright Data MCP (PID: {self.mcp_pid}) is not responsive, will restart")
                self.mcp_pid = None
                # Clean up PID file
                if os.path.exists(self._pid_file):
                    os.unlink(self._pid_file)
        
        # If we have a valid PID, check if it's responsive
        if self.mcp_pid:
            try:
                # Verify MCP is responsive
                if await self._check_mcp_health():
                    return True
                logger.warning(f"Bright Data MCP (PID: {self.mcp_pid}) is not responsive, will restart")
                self.mcp_pid = None
            except Exception as e:
                logger.warning(f"Error checking Bright Data MCP health: {str(e)}")
                self.mcp_pid = None
        
        # Acquire lock to prevent concurrent startup attempts
        async with self._startup_lock:
            # Double-check if another thread started the process while we were waiting
            if self.mcp_pid and await self._check_mcp_health():
                return True
            
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
        await self._cleanup_existing_process()
        
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
                preexec_fn=os.setsid  # Use process group for better cleanup
            )
            self.mcp_pid = self.mcp_process.pid
            logger.info(f"Bright Data MCP started with PID {self.mcp_pid}")
            
            # Save PID to file
            with open(self._pid_file, 'w') as f:
                f.write(str(self.mcp_pid))
            
            # Wait for MCP to be ready with retries
            success = await self._wait_for_mcp_ready()
            
            if not success:
                # Cleanup on failure
                await self._cleanup_existing_process()
                if os.path.exists(self._pid_file):
                    os.unlink(self._pid_file)
                return False
                
            return True
        except Exception as e:
            logger.error(f"Failed to start Bright Data MCP: {str(e)}")
            # Cleanup on error
            await self._cleanup_existing_process()
            if os.path.exists(self._pid_file):
                os.unlink(self._pid_file)
            return False
    
    async def _wait_for_mcp_ready(self) -> bool:
        """Wait for MCP to be ready with exponential backoff retries."""
        start_time = asyncio.get_event_loop().time()
        retry_count = 0
        
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
                # Check if process is still running
                if self.mcp_process and self.mcp_process.poll() is not None:
                    logger.error("Bright Data MCP process terminated unexpectedly")
                    return False
                
                # Calculate backoff delay
                retry_count += 1
                delay = min(self.retry_delay * (2 ** (retry_count - 1)), 10)
                logger.debug(f"MCP not ready yet, retrying in {delay} seconds (attempt {retry_count})")
                await asyncio.sleep(delay)
        
        logger.error("Timed out waiting for Bright Data MCP to start")
        return False
    
    async def _cleanup_existing_process(self):
        """Clean up existing MCP process with proper signal handling."""
        # First try to terminate the process we started
        if self.mcp_process and self.mcp_process.poll() is None:
            try:
                logger.info(f"Terminating Bright Data MCP process (PID: {self.mcp_process.pid})")
                # Try graceful termination first
                self.mcp_process.terminate()
                
                # Wait for process to terminate
                for _ in range(5):  # Wait up to 5 seconds
                    if self.mcp_process.poll() is not None:
                        break
                    await asyncio.sleep(1)
                
                # Force kill if still running
                if self.mcp_process.poll() is None:
                    logger.warning(f"Force killing Bright Data MCP process (PID: {self.mcp_process.pid})")
                    self.mcp_process.kill()
            except Exception as e:
                logger.error(f"Error terminating Bright Data MCP process: {str(e)}")
        
        # Also try to terminate by PID (in case we restored from PID file)
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
        
        # Implement retry logic for API requests
        for attempt in range(self.max_retries):
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
                    
                    # Check if we should retry
                    if attempt < self.max_retries - 1 and response.status_code >= 500:
                        delay = self.retry_delay * (2 ** attempt)
                        logger.info(f"Retrying in {delay} seconds (attempt {attempt + 1}/{self.max_retries})")
                        await asyncio.sleep(delay)
                        continue
                    
                    raise RuntimeError(f"Bright Data MCP returned error: {response.status_code}")
                
                # Parse response
                data = response.json()
                
                # Transform to InstagramPost model
                return self._transform_instagram_data(data, username, limit)
            
            except httpx.RequestError as e:
                logger.error(f"Request error when scraping Instagram (attempt {attempt + 1}/{self.max_retries}): {str(e)}")
                
                # Check if we should retry
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay} seconds")
                    await asyncio.sleep(delay)
                    continue
                
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
        await self._cleanup_existing_process()
        
        # Remove PID file
        if os.path.exists(self._pid_file):
            try:
                os.unlink(self._pid_file)
            except Exception as e:
                logger.error(f"Error removing PID file: {str(e)}")
