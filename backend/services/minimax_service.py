import os
import logging
import asyncio
import subprocess
import signal
import time
import psutil
import tempfile
import json
import random
import datetime
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

# Configure logging
logger = logging.getLogger(__name__)

class VideoGenerationRequest(BaseModel):
    """Model for video generation request parameters."""
    post_id: str
    caption: str
    image_url: str
    style: str = Field(default="comedy")
    duration: int = Field(default=30, ge=10, le=120)
    voice_type: str = Field(default="male")
    include_captions: bool = Field(default=True)
    music_style: Optional[str] = None

class VideoGenerationResponse(BaseModel):
    """Model for video generation response."""
    video_id: str
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration: Optional[int] = None
    status: str = "processing"
    message: Optional[str] = None
    created_at: Optional[str] = None

class VideoStatus(BaseModel):
    """Model for video generation status."""
    video_id: str
    status: str
    progress: Optional[float] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration: Optional[int] = None
    error: Optional[str] = None

class MiniMaxService:
    """Service for interacting with MiniMax MCP to generate viral videos."""
    
    # Class-level lock to prevent concurrent MCP startup attempts
    _startup_lock = asyncio.Lock()
    _instance = None
    _pid_file = os.path.join(os.path.expanduser("~"), ".minimax_mcp.pid")
    
    # Sample data for mock implementation
    _mock_video_urls = [
        "https://example.com/videos/viral_comedy_1.mp4",
        "https://example.com/videos/viral_comedy_2.mp4",
        "https://example.com/videos/viral_tech_1.mp4",
        "https://example.com/videos/viral_tech_2.mp4",
        "https://example.com/videos/viral_lifestyle_1.mp4",
    ]
    
    _mock_thumbnail_urls = [
        "https://example.com/thumbnails/viral_comedy_1.jpg",
        "https://example.com/thumbnails/viral_comedy_2.jpg",
        "https://example.com/thumbnails/viral_tech_1.jpg",
        "https://example.com/thumbnails/viral_tech_2.jpg",
        "https://example.com/thumbnails/viral_lifestyle_1.jpg",
    ]
    
    _mock_styles = {
        "comedy": {
            "duration_range": (20, 45),
            "progress_speed": 1.0,
            "success_rate": 0.95
        },
        "dramatic": {
            "duration_range": (30, 60),
            "progress_speed": 0.8,
            "success_rate": 0.9
        },
        "inspirational": {
            "duration_range": (25, 50),
            "progress_speed": 0.9,
            "success_rate": 0.95
        },
        "educational": {
            "duration_range": (40, 90),
            "progress_speed": 0.7,
            "success_rate": 0.85
        },
        "cinematic": {
            "duration_range": (45, 120),
            "progress_speed": 0.6,
            "success_rate": 0.8
        }
    }
    
    def __new__(cls, *args, **kwargs):
        """Implement singleton pattern to ensure only one service instance exists."""
        if cls._instance is None:
            cls._instance = super(MiniMaxService, cls).__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_host: Optional[str] = None,
        mcp_base_path: Optional[str] = None,
        resource_mode: Optional[str] = None
    ):
        """
        Initialize the MiniMax service.
        
        Args:
            api_key: MiniMax API key. If not provided, will be loaded from environment.
            api_host: MiniMax API host. If not provided, will be loaded from environment.
            mcp_base_path: MiniMax MCP base path. If not provided, will be loaded from environment.
            resource_mode: MiniMax API resource mode. If not provided, will be loaded from environment.
        """
        # Only initialize once (singleton pattern)
        if hasattr(self, 'initialized') and self.initialized:
            return
            
        self.api_key = api_key or os.getenv("MINIMAX_API_KEY")
        if not self.api_key:
            raise ValueError("MiniMax API key not provided and not found in environment")
        
        self.api_host = api_host or os.getenv("MINIMAX_API_HOST", "https://api.minimax.io")
        self.mcp_base_path = mcp_base_path or os.getenv("MINIMAX_MCP_BASE_PATH", "./")
        self.resource_mode = resource_mode or os.getenv("MINIMAX_API_RESOURCE_MODE", "url")
        
        # MCP process management
        self.mcp_process = None
        self.mcp_pid = None
        
        # Timeout and retry settings
        self.startup_timeout = 30  # seconds
        self.request_timeout = 300  # seconds for video generation (longer timeout)
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        
        # Health check settings
        self.health_check_interval = 60  # seconds
        self.last_health_check = 0
        
        # Video tracking
        self.video_status_cache: Dict[str, VideoStatus] = {}
        self.output_dir = Path(tempfile.gettempdir()) / "minimax_videos"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Active generation tasks
        self._active_tasks: Dict[str, asyncio.Task] = {}
        
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
                    logger.info(f"Restored MiniMax MCP process from PID file: {pid}")
                    self.mcp_pid = pid
                else:
                    logger.info(f"Found stale PID file for MiniMax MCP: {pid}")
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
            if "minimax" in " ".join(process.cmdline()).lower() or "uvx" in " ".join(process.cmdline()).lower():
                return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
            return False
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
    
    async def ensure_mcp_running(self) -> bool:
        """
        Ensure that the MiniMax MCP is running.
        
        For mock implementation, always returns True.
        
        Returns:
            bool: True if MCP is running, False otherwise.
        """
        # For mock implementation, we'll just return True
        # This keeps the API compatible with the real implementation
        logger.info("Mock implementation: MiniMax MCP considered running")
        return True
    
    async def _start_mcp(self) -> bool:
        """
        Start the MiniMax MCP process.
        
        For mock implementation, always returns True.
        
        Returns:
            bool: True if MCP started successfully, False otherwise.
        """
        # For mock implementation, we'll just return True
        logger.info("Mock implementation: MiniMax MCP considered started")
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
        
        # Cancel any active tasks
        for task_id, task in list(self._active_tasks.items()):
            if not task.done():
                task.cancel()
        self._active_tasks.clear()
    
    async def generate_video(self, request: VideoGenerationRequest) -> VideoGenerationResponse:
        """
        Mock implementation: Generate a viral video based on Instagram post content.
        
        Args:
            request: Video generation request parameters
            
        Returns:
            VideoGenerationResponse: Response with video ID and initial status
        """
        logger.info(f"Mock implementation: Generating video for post: {request.post_id} with style: {request.style}")
        
        # Simulate network delay
        await asyncio.sleep(0.5)
        
        # Generate a unique video ID
        video_id = f"video_{uuid.uuid4().hex[:8]}_{request.post_id}"
        
        # Get current timestamp
        created_at = datetime.datetime.now().isoformat()
        
        # Create initial response
        video_response = VideoGenerationResponse(
            video_id=video_id,
            status="processing",
            message="Video generation started",
            created_at=created_at
        )
        
        # Store initial status in cache
        self.video_status_cache[video_id] = VideoStatus(
            video_id=video_id,
            status="processing",
            progress=0.0
        )
        
        # Start background task to simulate video generation
        task = asyncio.create_task(self._mock_video_generation(video_id, request))
        self._active_tasks[video_id] = task
        
        return video_response
    
    async def _mock_video_generation(self, video_id: str, request: VideoGenerationRequest):
        """
        Mock implementation: Simulate video generation process with progress updates.
        
        Args:
            video_id: ID of the video being generated
            request: Original video generation request
        """
        try:
            # Get style configuration or use default
            style_config = self._mock_styles.get(
                request.style, 
                {"duration_range": (20, 45), "progress_speed": 1.0, "success_rate": 0.9}
            )
            
            # Determine if generation will succeed based on success rate
            will_succeed = random.random() < style_config["success_rate"]
            
            # Calculate total generation time based on style and requested duration
            base_time = request.duration / 10  # Base time in seconds
            style_factor = 1.0 / style_config["progress_speed"]
            total_time = base_time * style_factor
            
            # Calculate number of progress updates
            num_updates = min(10, int(total_time / 2))
            update_interval = total_time / num_updates if num_updates > 0 else total_time
            
            # Simulate generation process with progress updates
            for i in range(num_updates):
                # Calculate progress percentage
                progress = (i + 1) / num_updates
                
                # Update status in cache
                if video_id in self.video_status_cache:
                    self.video_status_cache[video_id].progress = progress
                
                # Simulate processing delay
                await asyncio.sleep(update_interval)
                
                # If we should fail, do it randomly during generation
                if not will_succeed and random.random() < 0.3 and i > num_updates / 2:
                    if video_id in self.video_status_cache:
                        self.video_status_cache[video_id].status = "failed"
                        self.video_status_cache[video_id].error = "Mock error: Video generation failed"
                    logger.warning(f"Mock implementation: Video generation failed for {video_id}")
                    return
            
            # Finalize video if successful
            if will_succeed:
                # Generate random duration within range based on style
                min_duration, max_duration = style_config["duration_range"]
                actual_duration = random.randint(min_duration, max_duration)
                
                # Select random video and thumbnail URLs
                video_url = random.choice(self._mock_video_urls)
                thumbnail_url = random.choice(self._mock_thumbnail_urls)
                
                # Update status in cache
                if video_id in self.video_status_cache:
                    self.video_status_cache[video_id].status = "completed"
                    self.video_status_cache[video_id].progress = 1.0
                    self.video_status_cache[video_id].video_url = video_url
                    self.video_status_cache[video_id].thumbnail_url = thumbnail_url
                    self.video_status_cache[video_id].duration = actual_duration
                
                logger.info(f"Mock implementation: Video generation completed for {video_id}")
            else:
                # Mark as failed
                if video_id in self.video_status_cache:
                    self.video_status_cache[video_id].status = "failed"
                    self.video_status_cache[video_id].error = "Mock error: Video generation failed"
                logger.warning(f"Mock implementation: Video generation failed for {video_id}")
        
        except asyncio.CancelledError:
            logger.info(f"Mock implementation: Video generation cancelled for {video_id}")
            if video_id in self.video_status_cache:
                self.video_status_cache[video_id].status = "failed"
                self.video_status_cache[video_id].error = "Generation cancelled"
            raise
        
        except Exception as e:
            logger.error(f"Mock implementation: Error in video generation for {video_id}: {str(e)}")
            if video_id in self.video_status_cache:
                self.video_status_cache[video_id].status = "failed"
                self.video_status_cache[video_id].error = f"Error: {str(e)}"
        
        finally:
            # Remove from active tasks
            if video_id in self._active_tasks:
                del self._active_tasks[video_id]
    
    async def get_video_status(self, video_id: str) -> VideoStatus:
        """
        Mock implementation: Get the status of a video generation task.
        
        Args:
            video_id: ID of the video to check
            
        Returns:
            VideoStatus: Current status of the video
        """
        logger.info(f"Mock implementation: Getting status for video {video_id}")
        
        # Check if we have status in cache
        if video_id in self.video_status_cache:
            return self.video_status_cache[video_id]
        
        # If not in cache, return not found status
        return VideoStatus(
            video_id=video_id,
            status="failed",
            error="Video not found"
        )
    
    async def get_completed_video(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Mock implementation: Get the details of a completed video.
        
        Args:
            video_id: ID of the video
            
        Returns:
            Optional[Dict[str, Any]]: Video details if completed, None otherwise
        """
        # Get current status
        status = await self.get_video_status(video_id)
        
        # Return None if not completed
        if status.status != "completed":
            return None
        
        # Return video details
        return {
            "video_id": video_id,
            "video_url": status.video_url,
            "thumbnail_url": status.thumbnail_url,
            "duration": status.duration,
            "status": status.status
        }
    
    async def close(self):
        """Close the service and clean up resources."""
        # Cancel any active generation tasks
        for task_id, task in list(self._active_tasks.items()):
            if not task.done():
                task.cancel()
        self._active_tasks.clear()
        
        # Clear status cache
        self.video_status_cache.clear()
        
        # Keep the process cleanup code for future real implementation
        await self._cleanup_existing_process()
        
        # Remove PID file
        if os.path.exists(self._pid_file):
            try:
                os.unlink(self._pid_file)
            except Exception as e:
                logger.error(f"Error removing PID file: {str(e)}")
