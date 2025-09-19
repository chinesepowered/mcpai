import os
import logging
import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
import httpx
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
        self.api_key = api_key or os.getenv("MINIMAX_API_KEY")
        if not self.api_key:
            raise ValueError("MiniMax API key not provided and not found in environment")
        
        self.api_host = api_host or os.getenv("MINIMAX_API_HOST", "https://api.minimax.io")
        self.mcp_base_path = mcp_base_path or os.getenv("MINIMAX_MCP_BASE_PATH", "./")
        self.resource_mode = resource_mode or os.getenv("MINIMAX_API_RESOURCE_MODE", "url")
        
        # MCP process management
        self.mcp_process = None
        self.mcp_port = 8192  # Default MiniMax MCP port
        self.mcp_base_url = f"http://localhost:{self.mcp_port}"
        
        # Timeout settings
        self.startup_timeout = 30  # seconds
        self.request_timeout = 300  # seconds for video generation (longer timeout)
        
        # Video tracking
        self.video_status_cache: Dict[str, VideoStatus] = {}
        self.output_dir = Path(tempfile.gettempdir()) / "minimax_videos"
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def ensure_mcp_running(self) -> bool:
        """
        Ensure that the MiniMax MCP is running.
        
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
                    logger.info("MiniMax MCP is already running")
                    return True
            except (httpx.RequestError, asyncio.TimeoutError):
                logger.warning("MiniMax MCP is running but not responsive")
        
        # Start MCP if not running or not responsive
        return await self._start_mcp()
    
    async def _start_mcp(self) -> bool:
        """
        Start the MiniMax MCP process.
        
        Returns:
            bool: True if MCP started successfully, False otherwise.
        """
        logger.info("Starting MiniMax MCP")
        
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
        env["MINIMAX_API_KEY"] = self.api_key
        env["MINIMAX_MCP_BASE_PATH"] = self.mcp_base_path
        env["MINIMAX_API_HOST"] = self.api_host
        env["MINIMAX_API_RESOURCE_MODE"] = self.resource_mode
        
        try:
            self.mcp_process = subprocess.Popen(
                ["uvx", "minimax-mcp", "-y"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            logger.info(f"MiniMax MCP started with PID {self.mcp_process.pid}")
            
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
                        logger.info("MiniMax MCP is ready")
                        return True
                except (httpx.RequestError, asyncio.TimeoutError):
                    await asyncio.sleep(1)
            
            logger.error("Timed out waiting for MiniMax MCP to start")
            return False
        except Exception as e:
            logger.error(f"Failed to start MiniMax MCP: {str(e)}")
            return False
    
    async def generate_video(self, request: VideoGenerationRequest) -> VideoGenerationResponse:
        """
        Generate a viral video based on Instagram post content.
        
        Args:
            request: Video generation request parameters
            
        Returns:
            VideoGenerationResponse: Response with video ID and initial status
        """
        # Ensure MCP is running
        if not await self.ensure_mcp_running():
            raise RuntimeError("Failed to start MiniMax MCP")
        
        logger.info(f"Generating video for post: {request.post_id} with style: {request.style}")
        
        # Prepare the request payload
        payload = {
            "type": "video_generation",
            "inputs": {
                "content": {
                    "post_id": request.post_id,
                    "caption": request.caption,
                    "image_url": request.image_url,
                    "style": request.style,
                    "duration": request.duration,
                    "voice_type": request.voice_type,
                    "include_captions": request.include_captions
                }
            },
            "parameters": {
                "output_format": "mp4",
                "resolution": "720p",
                "max_duration": request.duration,
                "output_dir": str(self.output_dir)
            }
        }
        
        if request.music_style:
            payload["inputs"]["content"]["music_style"] = request.music_style
        
        try:
            # Send request to MCP
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.mcp_base_url}/generate",
                    json=payload,
                    timeout=self.request_timeout
                )
                
            if response.status_code != 200:
                logger.error(f"Error from MiniMax MCP: {response.status_code} - {response.text}")
                raise RuntimeError(f"MiniMax MCP returned error: {response.status_code}")
            
            # Parse response
            data = response.json()
            
            # Get video ID
            video_id = data.get("video_id", f"video_{request.post_id}")
            
            # Create initial response
            video_response = VideoGenerationResponse(
                video_id=video_id,
                status="processing",
                created_at=data.get("created_at")
            )
            
            # Store status in cache
            self.video_status_cache[video_id] = VideoStatus(
                video_id=video_id,
                status="processing",
                progress=0.0
            )
            
            # Start background task to monitor video generation
            asyncio.create_task(self._monitor_video_generation(video_id))
            
            return video_response
        except httpx.RequestError as e:
            logger.error(f"Request error when generating video: {str(e)}")
            raise RuntimeError(f"Error communicating with MiniMax MCP: {str(e)}")
        except Exception as e:
            logger.error(f"Error generating video: {str(e)}", exc_info=True)
            raise RuntimeError(f"Error generating video: {str(e)}")
    
    async def _monitor_video_generation(self, video_id: str):
        """
        Monitor the status of a video generation task.
        
        Args:
            video_id: ID of the video to monitor
        """
        try:
            # Initial delay to allow processing to start
            await asyncio.sleep(2)
            
            # Check status periodically
            max_checks = 60  # Maximum number of status checks
            check_interval = 5  # Seconds between checks
            
            for i in range(max_checks):
                status = await self.get_video_status(video_id)
                
                # If completed or failed, stop checking
                if status.status in ["completed", "failed"]:
                    break
                
                # Update progress
                if status.progress is not None:
                    self.video_status_cache[video_id].progress = status.progress
                
                # Wait before next check
                await asyncio.sleep(check_interval)
            
            # If still processing after max checks, mark as failed
            if video_id in self.video_status_cache and self.video_status_cache[video_id].status == "processing":
                self.video_status_cache[video_id].status = "failed"
                self.video_status_cache[video_id].error = "Timed out waiting for video generation"
                logger.error(f"Video generation timed out for video ID: {video_id}")
        except Exception as e:
            logger.error(f"Error monitoring video generation for video ID {video_id}: {str(e)}")
            if video_id in self.video_status_cache:
                self.video_status_cache[video_id].status = "failed"
                self.video_status_cache[video_id].error = str(e)
    
    async def get_video_status(self, video_id: str) -> VideoStatus:
        """
        Get the status of a video generation task.
        
        Args:
            video_id: ID of the video to check
            
        Returns:
            VideoStatus: Current status of the video
        """
        # Check cache first
        if video_id in self.video_status_cache:
            cached_status = self.video_status_cache[video_id]
            
            # If already completed or failed, return cached status
            if cached_status.status in ["completed", "failed"]:
                return cached_status
        
        # Ensure MCP is running
        if not await self.ensure_mcp_running():
            raise RuntimeError("Failed to start MiniMax MCP")
        
        try:
            # Send request to MCP
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.mcp_base_url}/status/{video_id}",
                    timeout=10
                )
                
            if response.status_code != 200:
                logger.error(f"Error from MiniMax MCP: {response.status_code} - {response.text}")
                
                # Update cache with error
                if video_id in self.video_status_cache:
                    self.video_status_cache[video_id].status = "failed"
                    self.video_status_cache[video_id].error = f"MCP returned error: {response.status_code}"
                
                # Return current status
                return VideoStatus(
                    video_id=video_id,
                    status="failed",
                    error=f"MCP returned error: {response.status_code}"
                )
            
            # Parse response
            data = response.json()
            
            # Extract status information
            status = data.get("status", "processing")
            progress = data.get("progress", 0.0)
            video_url = data.get("video_url")
            thumbnail_url = data.get("thumbnail_url")
            duration = data.get("duration")
            error = data.get("error")
            
            # Create status object
            video_status = VideoStatus(
                video_id=video_id,
                status=status,
                progress=progress,
                video_url=video_url,
                thumbnail_url=thumbnail_url,
                duration=duration,
                error=error
            )
            
            # Update cache
            self.video_status_cache[video_id] = video_status
            
            return video_status
        except httpx.RequestError as e:
            logger.error(f"Request error when checking video status: {str(e)}")
            
            # Update cache with error
            if video_id in self.video_status_cache:
                # Don't override status if already completed
                if self.video_status_cache[video_id].status != "completed":
                    self.video_status_cache[video_id].error = f"Error communicating with MCP: {str(e)}"
            
            # Return current status from cache or create new failed status
            return self.video_status_cache.get(
                video_id,
                VideoStatus(
                    video_id=video_id,
                    status="failed",
                    error=f"Error communicating with MCP: {str(e)}"
                )
            )
        except Exception as e:
            logger.error(f"Error checking video status: {str(e)}", exc_info=True)
            
            # Update cache with error
            if video_id in self.video_status_cache:
                # Don't override status if already completed
                if self.video_status_cache[video_id].status != "completed":
                    self.video_status_cache[video_id].error = str(e)
            
            # Return current status from cache or create new failed status
            return self.video_status_cache.get(
                video_id,
                VideoStatus(
                    video_id=video_id,
                    status="failed",
                    error=str(e)
                )
            )
    
    async def get_completed_video(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the details of a completed video.
        
        Args:
            video_id: ID of the video
            
        Returns:
            Optional[Dict[str, Any]]: Video details if completed, None otherwise
        """
        status = await self.get_video_status(video_id)
        
        if status.status != "completed":
            return None
        
        return {
            "video_id": video_id,
            "video_url": status.video_url,
            "thumbnail_url": status.thumbnail_url,
            "duration": status.duration,
            "status": status.status
        }
    
    async def close(self):
        """Close the service and terminate the MCP process."""
        if self.mcp_process and self.mcp_process.poll() is None:
            logger.info(f"Terminating MiniMax MCP (PID: {self.mcp_process.pid})")
            try:
                self.mcp_process.terminate()
                await asyncio.sleep(2)
                if self.mcp_process.poll() is None:
                    logger.warning(f"Force killing MiniMax MCP (PID: {self.mcp_process.pid})")
                    self.mcp_process.kill()
            except Exception as e:
                logger.error(f"Error terminating MiniMax MCP: {str(e)}")
