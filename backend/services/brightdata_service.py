import os
import logging
import asyncio
import subprocess
import signal
import time
import psutil
import random
import datetime
from typing import List, Dict, Any, Optional
import json
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
    
    # Sample data for mock implementation
    _mock_captions = [
        "When your code works on the first try 😂 #programming #developer #techjokes",
        "POV: You're explaining to your boss why AI won't replace you... yet. #tech #ai #worklife",
        "This is what happens when you don't read the documentation 🤦‍♂️ #coding #developerlife",
        "How it started vs how it's going: coding edition #programming #techhumor",
        "Me debugging my code at 3am vs me explaining it in the morning standup #devlife",
        "The face you make when someone asks if you can 'just add one small feature' #developerproblems",
        "That moment when Stack Overflow goes down #panicmode #coding #developers",
        "Expectation: Clean code. Reality: 500 if statements #codingmemes #programming",
        "My brain after 10 hours of debugging #techlife #programming #needcoffee",
        "When the client says 'it should be easy to implement' #developerlife #techmemes",
        "How non-technical people imagine coding vs how it actually is #programming #reality",
        "The code I wrote 6 months ago vs me trying to understand it now #developerproblems",
        "When you fix one bug but create three more #coding #bugfixing #techhumor",
        "Explaining technical debt to management be like... #programming #techmanagement",
        "My productivity graph throughout the day #developerlife #programming"
    ]
    
    _mock_image_urls = [
        "https://picsum.photos/id/1/800/800",
        "https://picsum.photos/id/20/800/800",
        "https://picsum.photos/id/30/800/800",
        "https://picsum.photos/id/40/800/800",
        "https://picsum.photos/id/50/800/800",
        "https://picsum.photos/id/60/800/800",
        "https://picsum.photos/id/70/800/800",
        "https://picsum.photos/id/80/800/800",
        "https://picsum.photos/id/90/800/800",
        "https://picsum.photos/id/100/800/800",
        "https://picsum.photos/id/110/800/800",
        "https://picsum.photos/id/120/800/800",
        "https://picsum.photos/id/130/800/800",
        "https://picsum.photos/id/140/800/800",
        "https://picsum.photos/id/150/800/800"
    ]
    
    _mock_video_urls = [
        "https://example.com/videos/sample1.mp4",
        "https://example.com/videos/sample2.mp4",
        "https://example.com/videos/sample3.mp4",
        "https://example.com/videos/sample4.mp4",
        "https://example.com/videos/sample5.mp4"
    ]
    
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
        
        # Timeout and retry settings
        self.startup_timeout = 30  # seconds
        self.request_timeout = 60  # seconds
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        
        # Health check settings
        self.health_check_interval = 60  # seconds
        self.last_health_check = 0
        
        # Cache for mock data
        self._mock_data_cache = {}
        
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
        
        For mock implementation, always returns True.
        
        Returns:
            bool: True if MCP is running, False otherwise.
        """
        # For mock implementation, we'll just return True
        # This keeps the API compatible with the real implementation
        logger.info("Mock implementation: MCP considered running")
        return True
    
    async def _start_mcp(self) -> bool:
        """
        Start the Bright Data MCP process.
        
        For mock implementation, always returns True.
        
        Returns:
            bool: True if MCP started successfully, False otherwise.
        """
        # For mock implementation, we'll just return True
        logger.info("Mock implementation: MCP considered started")
        return True
    
    async def _wait_for_mcp_ready(self) -> bool:
        """
        Wait for MCP to be ready by monitoring process output.
        
        For mock implementation, always returns True.
        """
        # For mock implementation, we'll just return True
        return True
    
    async def _read_process_output(self, stream):
        """Read output from process stream until a relevant line is found."""
        # For mock implementation, we'll just return an empty string
        return ""
    
    async def _cleanup_existing_process(self):
        """Clean up existing MCP process with proper signal handling."""
        # For mock implementation, we'll just reset the process tracking
        self.mcp_process = None
        self.mcp_pid = None
    
    async def scrape_instagram_user(
        self, 
        username: str = "austinnasso", 
        limit: int = 10
    ) -> List[InstagramPost]:
        """
        Mock implementation: Generate realistic-looking Instagram posts.
        
        Args:
            username: Instagram username to scrape
            limit: Maximum number of posts to return
            
        Returns:
            List[InstagramPost]: List of mock Instagram posts
        """
        logger.info(f"Mock scraping Instagram posts for user: {username}")
        
        # Simulate network delay
        await asyncio.sleep(1.5)
        
        # Check if we have cached data for this user and limit
        cache_key = f"{username}_{limit}"
        if cache_key in self._mock_data_cache:
            logger.info(f"Returning cached mock data for {username}")
            return self._mock_data_cache[cache_key]
        
        # Generate mock posts
        posts = []
        follower_count = random.randint(10000, 500000)  # Random follower count
        
        for i in range(limit):
            # Generate unique post ID
            post_id = f"post_{username}_{int(time.time())}_{i}"
            
            # Select random caption
            caption = random.choice(self._mock_captions)
            
            # Select random image URL
            image_url = random.choice(self._mock_image_urls)
            
            # Randomly decide if it's a video post
            has_video = random.random() < 0.3  # 30% chance of being a video
            video_url = random.choice(self._mock_video_urls) if has_video else None
            
            # Generate engagement metrics
            likes = random.randint(1000, 50000)
            comments = random.randint(50, 2000)
            
            # Calculate engagement rate
            engagement_rate = round((likes + comments) / follower_count * 100, 2)
            
            # Generate timestamp (random time within the last 30 days)
            days_ago = random.randint(0, 30)
            hours_ago = random.randint(0, 23)
            minutes_ago = random.randint(0, 59)
            post_time = datetime.datetime.now() - datetime.timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)
            timestamp = post_time.isoformat()
            
            # Create InstagramPost
            post = InstagramPost(
                id=post_id,
                caption=caption,
                image_url=image_url,
                video_url=video_url,
                likes=likes,
                comments=comments,
                engagement_rate=engagement_rate,
                timestamp=timestamp
            )
            posts.append(post)
        
        # Sort by timestamp (newest first)
        posts.sort(key=lambda x: x.timestamp or "", reverse=True)
        
        # Cache the results
        self._mock_data_cache[cache_key] = posts
        
        logger.info(f"Generated {len(posts)} mock Instagram posts for {username}")
        return posts
    
    def _transform_instagram_data(
        self, 
        data: Dict[str, Any], 
        username: str, 
        limit: int
    ) -> List[InstagramPost]:
        """
        Transform raw Instagram data from Bright Data MCP to InstagramPost models.
        
        This method is kept for API compatibility but not used in mock implementation.
        
        Args:
            data: Raw data from Bright Data MCP
            username: Instagram username
            limit: Maximum number of posts to return
            
        Returns:
            List[InstagramPost]: List of Instagram posts
        """
        # This method is kept for API compatibility but not used in mock implementation
        return []
    
    async def close(self):
        """Close the service and terminate the MCP process."""
        # For mock implementation, just clean up any resources
        self._mock_data_cache = {}
        
        # Keep the process cleanup code for future real implementation
        await self._cleanup_existing_process()
        
        # Remove PID file
        if os.path.exists(self._pid_file):
            try:
                os.unlink(self._pid_file)
            except Exception as e:
                logger.error(f"Error removing PID file: {str(e)}")
