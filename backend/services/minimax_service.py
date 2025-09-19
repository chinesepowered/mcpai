import os
import logging
import asyncio
import subprocess
import signal
import time
import psutil
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
    
    # Class-level lock to prevent concurrent MCP startup attempts
    _startup_lock = asyncio.Lock()
    _instance = None
    _pid_file = os.path.join(os.path.expanduser("~"), ".minimax_mcp.pid")
    
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
        self.mcp_port = 8192  # Default MiniMax MCP port
        self.mcp_base_url = f"http://localhost:{self.mcp_port}"
        
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
        Ensure that the MiniMax MCP is running.
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
                logger.warning(f"MiniMax MCP (PID: {self.mcp_pid}) is not responsive, will restart")
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
                logger.warning(f"MiniMax MCP (PID: {self.mcp_pid}) is not responsive, will restart")
                self.mcp_pid = None
            except Exception as e:
                logger.warning(f"Error checking MiniMax MCP health: {str(e)}")
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
        Start the MiniMax MCP process.
        
        Returns:
            bool: True if MCP started successfully, False otherwise.
        """
        logger.info("Starting MiniMax MCP")
        
        # Kill existing process if it exists
        await self._cleanup_existing_process()
        
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
                preexec_fn=os.setsid  # Use process group for better cleanup
            )
            self.mcp_pid = self.mcp_process.pid
            logger.info(f"MiniMax MCP started with PID {self.mcp_pid}")
            
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
            logger.error(f"Failed to start MiniMax MCP: {str(e)}")
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
                    logger.info("MiniMax MCP is ready")
                    return True
            except (httpx.RequestError, asyncio.TimeoutError):
                # Check if process is still running
                if self.mcp_process and self.mcp_process.poll() is not None:
                    logger.error("MiniMax MCP process terminated unexpectedly")
                    return False
                
                # Calculate backoff delay
                retry_count += 1
                delay = min(self.retry_delay * (2 ** (retry_count - 1)), 10)
                logger.debug(f"MCP not ready yet, retrying in {delay} seconds (attempt {retry_count})")
                await asyncio.sleep(delay)
        
        logger.error("Timed out waiting for MiniMax MCP to start")
        return False
    
    async def _cleanup_existing_process(self):
        """Clean up existing MCP process with proper signal handling."""
        # First try to terminate the process we started
        if self.mcp_process and self.mcp_process.poll() is None:
            try:
                logger.info(f"Terminating MiniMax MCP process (PID: {self.mcp_process.pid})")
                # Try graceful termination first
                self.mcp_process.terminate()
                
                # Wait for process to terminate
                for _ in range(5):  # Wait up to 5 seconds
                    if self.mcp_process.poll() is not None:
                        break
                    await asyncio.sleep(1)
                
                # Force kill if still running
                if self.mcp_process.poll() is None:
                    logger.warning(f"Force killing MiniMax MCP process (PID: {self.mcp_process.pid})")
                    self.mcp_process.kill()
            except Exception as e:
                logger.error(f"Error terminating MiniMax MCP process: {str(e)}")
        
        # Also try to terminate by PID (in case we restored from PID file)
        if self.mcp_pid and self._is_process_running(self.mcp_pid):
            try:
                logger.info(f"Terminating MiniMax MCP by PID: {self.mcp_pid}")
                # Try to kill the process group
                os.killpg(os.getpgid(self.mcp_pid), signal.SIGTERM)
                
                # Wait for process to terminate
                for _ in range(5):  # Wait up to 5 seconds
                    if not self._is_process_running(self.mcp_pid):
                        break
                    await asyncio.sleep(1)
                
                # Force kill if still running
                if self._is_process_running(self.mcp_pid):
                    logger.warning(f"Force killing MiniMax MCP by PID: {self.mcp_pid}")
                    os.killpg(os.getpgid(self.mcp_pid), signal.SIGKILL)
            except Exception as e:
                logger.error(f"Error terminating MiniMax MCP by PID: {str(e)}")
        
        # Reset process tracking
        self.mcp_process = None
        self.mcp_pid = None
    
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
        
        # Implement retry logic for API requests
        for attempt in range(self.max_retries):
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
                    
                    # Check if we should retry
                    if attempt < self.max_retries - 1 and response.status_code >= 500:
                        delay = self.retry_delay * (2 ** attempt)
                        logger.info(f"Retrying in {delay} seconds (attempt {attempt + 1}/{self.max_retries})")
                        await asyncio.sleep(delay)
                        continue
                    
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
                logger.error(f"Request error when generating video (attempt {attempt + 1}/{self.max_retries}): {str(e)}")
                
                # Check if we should retry
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay} seconds")
                    await asyncio.sleep(delay)
                    continue
                
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
        
        # Implement retry logic for API requests
        for attempt in range(self.max_retries):
            try:
                # Send request to MCP
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.mcp_base_url}/status/{video_id}",
                        timeout=10
                    )
                    
                if response.status_code != 200:
                    logger.error(f"Error from MiniMax MCP: {response.status_code} - {response.text}")
                    
                    # Check if we should retry
                    if attempt < self.max_retries - 1 and response.status_code >= 500:
                        delay = self.retry_delay * (2 ** attempt)
                        logger.info(f"Retrying in {delay} seconds (attempt {attempt + 1}/{self.max_retries})")
                        await asyncio.sleep(delay)
                        continue
                    
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
                logger.error(f"Request error when checking video status (attempt {attempt + 1}/{self.max_retries}): {str(e)}")
                
                # Check if we should retry
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay} seconds")
                    await asyncio.sleep(delay)
                    continue
                
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
        await self._cleanup_existing_process()
        
        # Remove PID file
        if os.path.exists(self._pid_file):
            try:
                os.unlink(self._pid_file)
            except Exception as e:
                logger.error(f"Error removing PID file: {str(e)}")
