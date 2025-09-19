import os
import logging
import asyncio
import time
import json
import uuid
import httpx
import tempfile
from pathlib import Path
from datetime import datetime
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
    """Service for interacting with MiniMax API to generate viral videos."""
    
    # Class-level lock to prevent concurrent API initialization
    _startup_lock = asyncio.Lock()
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        """Implement singleton pattern to ensure only one service instance exists."""
        if cls._instance is None:
            cls._instance = super(MiniMaxService, cls).__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base_url: Optional[str] = None
    ):
        """
        Initialize the MiniMax service.
        
        Args:
            api_key: MiniMax API key. If not provided, will be loaded from environment.
            api_base_url: MiniMax API base URL. If not provided, will use default.
        """
        # Only initialize once (singleton pattern)
        if hasattr(self, 'initialized') and self.initialized:
            return
            
        self.api_key = api_key or os.getenv("MINIMAX_API_KEY")
        if not self.api_key:
            raise ValueError("MiniMax API key not provided and not found in environment")
        
        # Official MiniMax API base URL
        self.api_base_url = api_base_url or os.getenv(
            "MINIMAX_API_BASE_URL",
            "https://api.minimax.io",
        )
        
        # Timeout and retry settings
        self.startup_timeout = 30  # seconds
        # Allow up to 10 minutes for long-running video generation jobs
        self.request_timeout = 600  # seconds
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        
        # HTTP client
        self.http_client = None
        
        # Video tracking
        self.video_status_cache: Dict[str, VideoStatus] = {}
        self.output_dir = Path(tempfile.gettempdir()) / "minimax_videos"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Mark as initialized
        self.initialized = True
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """
        Get or create an HTTP client for API requests.
        
        Returns:
            httpx.AsyncClient: Configured HTTP client
        """
        if self.http_client is None or self.http_client.is_closed:
            # Create a new client with appropriate timeouts
            self.http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.request_timeout),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
            )
        return self.http_client
    
    async def generate_video(self, request: VideoGenerationRequest) -> VideoGenerationResponse:
        """
        Generate a viral video based on Instagram post content using MiniMax API.
        
        Args:
            request: Video generation request parameters
            
        Returns:
            VideoGenerationResponse: Response with video ID and initial status
        """
        logger.info(f"Generating video for post: {request.post_id} with style: {request.style}")
        
        # Generate a unique video ID
        video_id = f"video_{request.post_id}_{int(time.time())}"
        
        # Prepare the request payload for text-to-video API
        # Based on MiniMax API documentation
        payload = {
            "model": "MiniMax-Hailuo-02",  # Use the latest video model
            "prompt": request.caption,
            # MiniMax video API currently supports only 6 s and 10 s clips.
            # To keep turnaround fast (better UX for viral content) we default
            # to 6 seconds regardless of the requested duration.
            # TODO: expose 6 / 10 s choice to the frontend if needed.
            "duration": 6,
            # 768P is the default / recommended resolution per docs
            "resolution": "768P",
            "aigc_watermark": False  # No watermark for viral marketing
        }
        
        # Add music style if provided
        if request.music_style:
            payload["music_style"] = request.music_style
        
        # Implement retry logic for API requests
        for attempt in range(self.max_retries):
            try:
                client = await self._get_http_client()
                
                # Call the video generation API endpoint
                response = await client.post(
                    f"{self.api_base_url}/v1/video_generation",
                    json=payload
                )
                
                # Raise exception for error status codes
                response.raise_for_status()
                
                # Parse the response
                result_data = response.json()
                # Log full response for debugging – helps diagnose missing task_id issues
                logger.debug(
                    "MiniMax video_generation raw response: %s",
                    json.dumps(result_data, ensure_ascii=False),
                )
                
                # Extract task ID from response
                task_id = result_data.get("task_id")
                if not task_id:
                    # If base_resp is present, include status code/msg for easier debugging
                    base_resp = result_data.get("base_resp", {})
                    status_code = base_resp.get("status_code")
                    status_msg = base_resp.get("status_msg")
                    logger.error(
                        "MiniMax API returned no task_id. status_code=%s, status_msg=%s",
                        status_code,
                        status_msg,
                    )
                    raise ValueError("No task_id in API response")
                
                # Create initial response
                video_response = VideoGenerationResponse(
                    video_id=video_id,
                    status="processing",
                    message="Video generation started",
                    created_at=datetime.now().isoformat()
                )
                
                # Store status in cache with mapping from our video_id to MiniMax task_id
                self.video_status_cache[video_id] = VideoStatus(
                    video_id=video_id,
                    status="processing",
                    progress=0.0
                )
                
                # Store task_id mapping
                self.video_status_cache[video_id].task_id = task_id
                
                # Start background task to monitor video generation
                asyncio.create_task(self._monitor_video_generation(video_id))
                
                return video_response
                
            except Exception as e:
                logger.error(f"Error generating video (attempt {attempt + 1}/{self.max_retries}): {str(e)}")
                
                # Check if we should retry
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay} seconds")
                    await asyncio.sleep(delay)
                    
                    # Create a new client if needed
                    if self.http_client and not self.http_client.is_closed:
                        await self.http_client.aclose()
                        self.http_client = None
                    
                    continue
                
                # Create failed status in cache
                self.video_status_cache[video_id] = VideoStatus(
                    video_id=video_id,
                    status="failed",
                    error=str(e)
                )
                
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
            # 120 × 5 s  ≈ 10 minutes total polling window
            max_checks = 120  # Maximum number of status checks
            check_interval = 5  # Seconds between checks
            
            for i in range(max_checks):
                status = await self.get_video_status(video_id)
                
                # If completed or failed, stop checking
                if status.status in ["completed", "failed"]:
                    break
                
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
        Get the status of a video generation task from MiniMax API.
        
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
            
            # Get the MiniMax task_id
            task_id = getattr(cached_status, "task_id", None)
            if not task_id:
                # No task ID found, return error status
                cached_status.status = "failed"
                cached_status.error = "No task ID found for video"
                return cached_status
        else:
            # No cached status found
            return VideoStatus(
                video_id=video_id,
                status="failed",
                error="Video not found"
            )
        
        # Implement retry logic for API requests
        for attempt in range(self.max_retries):
            try:
                client = await self._get_http_client()
                
                # Call the video status API endpoint
                response = await client.get(
                    f"{self.api_base_url}/v1/video_generation_query",
                    params={"task_id": task_id}
                )
                
                # Raise exception for error status codes
                response.raise_for_status()
                
                # Parse the response
                result_data = response.json()
                
                # Extract base response
                base_resp = result_data.get("base_resp", {})
                if base_resp.get("status_code") != 0:
                    # API returned an error
                    error_msg = base_resp.get("status_msg", "Unknown API error")
                    raise ValueError(f"API error: {error_msg}")
                
                # Extract status information
                api_status = result_data.get("status", "PROCESSING")
                
                # Map API status to our status
                status_map = {
                    "PROCESSING": "processing",
                    "SUCCEEDED": "completed",
                    "FAILED": "failed"
                }
                status = status_map.get(api_status, "processing")
                
                # Calculate progress based on API response
                progress = 0.0
                if status == "completed":
                    progress = 1.0
                elif status == "processing":
                    # Estimate progress based on elapsed time
                    # Assuming average job takes 3 minutes
                    elapsed = time.time() - int(cached_status.created_at or time.time())
                    progress = min(0.95, elapsed / 180)  # Cap at 95% until complete
                
                # Get video URL if available
                video_url = None
                thumbnail_url = None
                duration = None
                error = None
                
                if status == "completed":
                    # Get download URL
                    download_response = await client.get(
                        f"{self.api_base_url}/v1/video_generation_download",
                        params={"task_id": task_id}
                    )
                    download_response.raise_for_status()
                    download_data = download_response.json()
                    
                    video_url = download_data.get("url")
                    thumbnail_url = download_data.get("thumbnail_url", video_url)
                    duration = request.duration if "request" in locals() else None
                
                if status == "failed":
                    error = result_data.get("error_msg", "Video generation failed")
                
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
                
                # Store task_id for future queries
                video_status.task_id = task_id
                
                # Update cache
                self.video_status_cache[video_id] = video_status
                
                return video_status
                
            except Exception as e:
                logger.error(f"Error checking video status (attempt {attempt + 1}/{self.max_retries}): {str(e)}")
                
                # Check if we should retry
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay} seconds")
                    await asyncio.sleep(delay)
                    
                    # Create a new client if needed
                    if self.http_client and not self.http_client.is_closed:
                        await self.http_client.aclose()
                        self.http_client = None
                    
                    continue
                
                # Update cache with error
                if video_id in self.video_status_cache:
                    # Don't override status if already completed
                    if self.video_status_cache[video_id].status != "completed":
                        self.video_status_cache[video_id].error = str(e)
                        self.video_status_cache[video_id].status = "failed"
                
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
        """Close the service and clean up resources."""
        # Close HTTP client if it exists
        if self.http_client and not self.http_client.is_closed:
            await self.http_client.aclose()
            self.http_client = None
