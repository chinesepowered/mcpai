import os
import logging
import asyncio
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Import service classes
# NOTE: FastAPI runs this file from the *backend* package, so
# relative imports (`services.*`) resolve regardless of the project root.
from services.brightdata_service import BrightDataService, InstagramPost
from services.minimax_service import (
    MiniMaxService,
    VideoGenerationRequest as MCPVideoRequest,
    VideoStatus,
)
from services.apify_service import ApifyService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Validate required environment variables
required_env_vars = [
    "MINIMAX_API_KEY", 
    "BRIGHTDATA_API_TOKEN", 
    "APIFY_API_TOKEN"
]

missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Define data models
class ScrapingRequest(BaseModel):
    username: str = Field(default="austinnasso")
    limit: int = Field(default=10, ge=1, le=50)
    use_backup: bool = Field(default=False)

class VideoGenerationRequest(BaseModel):
    post_id: str
    caption: str
    image_url: str
    style: str = Field(default="comedy")
    duration: int = Field(default=30, ge=10, le=120)
    voice_type: str = Field(default="male")
    include_captions: bool = Field(default=True)
    music_style: Optional[str] = None

class VideoGenerationResponse(BaseModel):
    video_id: str
    status: str = "processing"
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration: Optional[int] = None
    message: Optional[str] = None
    created_at: Optional[str] = None

# Create FastAPI app
app = FastAPI(
    title="Viral Marketing Agent API",
    description="API for scraping Instagram content and generating viral videos",
    version="1.0.0",
)

# Configure CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service instances and initialization lock
brightdata_service: Optional[BrightDataService] = None
minimax_service: Optional[MiniMaxService] = None
apify_service: Optional[ApifyService] = None
init_lock = asyncio.Lock()
services_initialized = False
service_errors: Dict[str, str] = {}

# Error handling middleware
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": exc.body},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "message": str(exc)},
    )

# Health check endpoint
@app.get("/api/health")
async def health_check():
    health_status = {
        "status": "ok", 
        "message": "API is running",
        "services": {
            "brightdata": "initialized" if brightdata_service else "not_initialized",
            "minimax": "initialized" if minimax_service else "not_initialized",
            "apify": "initialized" if apify_service else "not_initialized"
        }
    }
    
    # Add error information if any services failed to initialize
    if service_errors:
        health_status["service_errors"] = service_errors
        health_status["status"] = "degraded"
    
    return health_status

# Service dependencies - these now just return the already initialized services
async def get_brightdata_service() -> BrightDataService:
    if not brightdata_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bright Data service not initialized. Check server logs for details."
        )
    return brightdata_service

async def get_minimax_service() -> MiniMaxService:
    if not minimax_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MiniMax service not initialized. Check server logs for details."
        )
    return minimax_service

async def get_apify_service() -> ApifyService:
    if not apify_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Apify service not initialized. Check server logs for details."
        )
    return apify_service

# Instagram content scraping endpoints
@app.post("/api/scrape", response_model=List[InstagramPost])
async def scrape_instagram_content(
    request: ScrapingRequest,
    brightdata_service: BrightDataService = Depends(get_brightdata_service),
    apify_service: ApifyService = Depends(get_apify_service)
):
    """
    Scrape content from Instagram using Bright Data MCP (primary) or Apify (backup)
    """
    try:
        if not request.use_backup:
            # Use Bright Data MCP as primary method
            logger.info(f"Scraping Instagram content for user {request.username} using Bright Data MCP")
            posts = await brightdata_service.scrape_instagram_user(
                username=request.username,
                limit=request.limit
            )
            return posts
        else:
            # Use Apify as backup method
            logger.info(f"Scraping Instagram content for user {request.username} using Apify (backup)")
            posts = await apify_service.scrape_instagram_user(
                username=request.username,
                limit=request.limit
            )
            return posts
    except Exception as e:
        logger.error(f"Error scraping Instagram content: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error scraping Instagram content: {str(e)}",
        )

# Video generation endpoint
@app.post("/api/generate-video", response_model=VideoGenerationResponse)
async def generate_video(
    request: VideoGenerationRequest,
    minimax_service: MiniMaxService = Depends(get_minimax_service)
):
    """
    Generate a viral video based on the selected Instagram post using MiniMax MCP
    """
    try:
        logger.info(f"Generating video for post {request.post_id} with style {request.style}")
        
        # Convert to MCP request format
        mcp_request = MCPVideoRequest(
            post_id=request.post_id,
            caption=request.caption,
            image_url=request.image_url,
            style=request.style,
            duration=request.duration,
            voice_type=request.voice_type,
            include_captions=request.include_captions,
            music_style=request.music_style
        )
        
        # Generate video
        response = await minimax_service.generate_video(mcp_request)
        
        return VideoGenerationResponse(
            video_id=response.video_id,
            status=response.status,
            video_url=response.video_url,
            thumbnail_url=response.thumbnail_url,
            message="Video generation started",
            created_at=response.created_at
        )
    except Exception as e:
        logger.error(f"Error generating video: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating video: {str(e)}",
        )

# Video status endpoint
@app.get("/api/video-status/{video_id}", response_model=VideoStatus)
async def get_video_status(
    video_id: str,
    minimax_service: MiniMaxService = Depends(get_minimax_service)
):
    """
    Get the status of a video generation task
    """
    try:
        status = await minimax_service.get_video_status(video_id)
        return status
    except Exception as e:
        logger.error(f"Error getting video status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting video status: {str(e)}",
        )

# Completed video endpoint
@app.get("/api/videos/{video_id}")
async def get_video(
    video_id: str,
    minimax_service: MiniMaxService = Depends(get_minimax_service)
):
    """
    Get details of a completed video
    """
    try:
        video = await minimax_service.get_completed_video(video_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video {video_id} not found or not completed",
            )
        return video
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting video: {str(e)}",
        )

# MCP status endpoint
@app.get("/api/mcp-status")
async def get_mcp_status():
    """
    Get status of MCP servers
    """
    status_info = {
        "brightdata": {
            "initialized": brightdata_service is not None,
            "error": service_errors.get("brightdata")
        },
        "minimax": {
            "initialized": minimax_service is not None,
            "error": service_errors.get("minimax")
        }
    }
    
    # Check if MCPs are running
    if brightdata_service:
        try:
            is_running = await brightdata_service.ensure_mcp_running()
            status_info["brightdata"]["running"] = is_running
        except Exception as e:
            status_info["brightdata"]["running"] = False
            status_info["brightdata"]["error"] = str(e)
    
    if minimax_service:
        try:
            is_running = await minimax_service.ensure_mcp_running()
            status_info["minimax"]["running"] = is_running
        except Exception as e:
            status_info["minimax"]["running"] = False
            status_info["minimax"]["error"] = str(e)
    
    return status_info

# Initialize services function
async def initialize_services():
    """
    Initialize all services with proper error handling.
    This is called only once during startup.
    """
    global brightdata_service, minimax_service, apify_service, services_initialized, service_errors
    
    # Use a lock to prevent concurrent initialization
    async with init_lock:
        if services_initialized:
            return
        
        # Initialize Bright Data service
        try:
            logger.info("Initializing Bright Data service")
            brightdata_service = BrightDataService()
            # Don't wait for MCP to start here, just create the service
        except Exception as e:
            logger.error(f"Failed to initialize Bright Data service: {str(e)}", exc_info=True)
            service_errors["brightdata"] = str(e)
        
        # Initialize MiniMax service
        try:
            logger.info("Initializing MiniMax service")
            minimax_service = MiniMaxService()
            # Don't wait for MCP to start here, just create the service
        except Exception as e:
            logger.error(f"Failed to initialize MiniMax service: {str(e)}", exc_info=True)
            service_errors["minimax"] = str(e)
        
        # Initialize Apify service
        try:
            logger.info("Initializing Apify service")
            apify_service = ApifyService()
        except Exception as e:
            logger.error(f"Failed to initialize Apify service: {str(e)}", exc_info=True)
            service_errors["apify"] = str(e)
        
        services_initialized = True
    
    # Start MCP processes in background tasks to avoid blocking startup
    if brightdata_service:
        asyncio.create_task(start_brightdata_mcp())
    
    if minimax_service:
        asyncio.create_task(start_minimax_mcp())

async def start_brightdata_mcp():
    """Start Bright Data MCP in a background task"""
    global service_errors
    try:
        logger.info("Starting Bright Data MCP")
        success = await brightdata_service.ensure_mcp_running()
        if not success:
            service_errors["brightdata"] = "Failed to start Bright Data MCP"
            logger.error("Failed to start Bright Data MCP")
    except Exception as e:
        service_errors["brightdata"] = str(e)
        logger.error(f"Error starting Bright Data MCP: {str(e)}", exc_info=True)

async def start_minimax_mcp():
    """Start MiniMax MCP in a background task"""
    global service_errors
    try:
        logger.info("Starting MiniMax MCP")
        success = await minimax_service.ensure_mcp_running()
        if not success:
            service_errors["minimax"] = "Failed to start MiniMax MCP"
            logger.error("Failed to start MiniMax MCP")
    except Exception as e:
        service_errors["minimax"] = str(e)
        logger.error(f"Error starting MiniMax MCP: {str(e)}", exc_info=True)

# Application startup event
@app.on_event("startup")
async def startup_event():
    logger.info("Starting services")
    try:
        # Initialize all services once during startup
        await initialize_services()
        logger.info("Service initialization process started")
    except Exception as e:
        logger.error(f"Error during service initialization: {str(e)}", exc_info=True)

# Shutdown hook to clean up services
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down services")
    
    # Close Bright Data service
    if brightdata_service:
        try:
            await brightdata_service.close()
            logger.info("Bright Data service closed")
        except Exception as e:
            logger.error(f"Error closing Bright Data service: {str(e)}")
    
    # Close MiniMax service
    if minimax_service:
        try:
            await minimax_service.close()
            logger.info("MiniMax service closed")
        except Exception as e:
            logger.error(f"Error closing MiniMax service: {str(e)}")

# Run the application
if __name__ == "__main__":
    import uvicorn
    
    # Run FastAPI with Uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
