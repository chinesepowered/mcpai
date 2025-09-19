import os
import logging
import asyncio
import time
from datetime import datetime
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

class ApifyService:
    """Service for interacting with Apify API to scrape Instagram content as a backup method."""
    
    def __init__(self, api_token: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize the Apify service.
        
        Args:
            api_token: Apify API token. If not provided, will be loaded from environment.
            base_url: Apify API base URL. If not provided, will use the default.
        """
        self.api_token = api_token or os.getenv("APIFY_API_TOKEN")
        if not self.api_token:
            raise ValueError("Apify API token not provided and not found in environment")
        
        self.base_url = base_url or os.getenv("APIFY_BASE_URL", "https://api.apify.com/v2")
        
        # Rate limiting settings
        self.requests_per_minute = 10
        self.last_request_time = 0
        self.min_request_interval = 60 / self.requests_per_minute  # seconds
        
        # Retry settings
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        
        # Timeout settings
        self.request_timeout = 120  # seconds
    
    async def _enforce_rate_limit(self):
        """
        Enforce rate limiting by waiting if necessary.
        """
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < self.min_request_interval:
            wait_time = self.min_request_interval - elapsed
            logger.debug(f"Rate limiting: waiting {wait_time:.2f} seconds")
            await asyncio.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None, 
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make a rate-limited request to the Apify API with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            params: Query parameters
            json_data: JSON request body
            
        Returns:
            Dict[str, Any]: API response
        """
        url = f"{self.base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self.api_token}"}
        
        # Add common parameters
        if params is None:
            params = {}
        
        for attempt in range(self.max_retries):
            try:
                # Enforce rate limiting
                await self._enforce_rate_limit()
                
                async with httpx.AsyncClient() as client:
                    if method.upper() == "GET":
                        response = await client.get(
                            url,
                            headers=headers,
                            params=params,
                            timeout=self.request_timeout
                        )
                    elif method.upper() == "POST":
                        response = await client.post(
                            url,
                            headers=headers,
                            params=params,
                            json=json_data,
                            timeout=self.request_timeout
                        )
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")
                
                # Check for HTTP errors
                response.raise_for_status()
                
                # Parse and return JSON response
                return response.json()
            
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error on attempt {attempt + 1}/{self.max_retries}: {str(e)}")
                
                # Handle rate limiting (429) or server errors (5xx)
                if e.response.status_code == 429 or e.response.status_code >= 500:
                    if attempt < self.max_retries - 1:
                        # Exponential backoff
                        wait_time = self.retry_delay * (2 ** attempt)
                        logger.info(f"Retrying in {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                        continue
                
                # For other HTTP errors, raise immediately
                raise RuntimeError(f"Apify API returned error: {e.response.status_code} - {e.response.text}")
            
            except (httpx.RequestError, asyncio.TimeoutError) as e:
                logger.warning(f"Request error on attempt {attempt + 1}/{self.max_retries}: {str(e)}")
                
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                    continue
                
                raise RuntimeError(f"Error communicating with Apify API: {str(e)}")
        
        # This should not be reached due to the raises above
        raise RuntimeError("Maximum retry attempts exceeded")
    
    async def start_actor_run(
        self, 
        actor_id: str = "apify/instagram-scraper", 
        run_input: Dict[str, Any] = None
    ) -> str:
        """
        Start an Apify actor run.
        
        Args:
            actor_id: ID of the Apify actor
            run_input: Input for the actor run
            
        Returns:
            str: Run ID
        """
        endpoint = f"/acts/{actor_id}/runs"
        
        try:
            response = await self._make_request("POST", endpoint, json_data=run_input)
            run_id = response.get("data", {}).get("id")
            
            if not run_id:
                raise ValueError("Run ID not found in response")
            
            logger.info(f"Started Apify actor run: {run_id}")
            return run_id
        except Exception as e:
            logger.error(f"Error starting Apify actor run: {str(e)}", exc_info=True)
            raise RuntimeError(f"Error starting Apify actor run: {str(e)}")
    
    async def wait_for_run(self, run_id: str, max_wait_time: int = 300) -> Dict[str, Any]:
        """
        Wait for an Apify actor run to complete.
        
        Args:
            run_id: ID of the run to wait for
            max_wait_time: Maximum time to wait in seconds
            
        Returns:
            Dict[str, Any]: Run status
        """
        endpoint = f"/actor-runs/{run_id}"
        
        start_time = time.time()
        check_interval = 5  # seconds
        
        while time.time() - start_time < max_wait_time:
            try:
                response = await self._make_request("GET", endpoint)
                status = response.get("data", {}).get("status")
                
                if status == "SUCCEEDED":
                    logger.info(f"Apify actor run {run_id} completed successfully")
                    return response.get("data", {})
                elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                    error_message = response.get("data", {}).get("errorMessage", f"Run failed with status: {status}")
                    logger.error(f"Apify actor run {run_id} failed: {error_message}")
                    raise RuntimeError(f"Apify actor run failed: {error_message}")
                
                logger.debug(f"Apify actor run {run_id} status: {status}, waiting...")
                await asyncio.sleep(check_interval)
            
            except Exception as e:
                if not isinstance(e, RuntimeError) or "failed" not in str(e):
                    logger.error(f"Error checking Apify actor run status: {str(e)}", exc_info=True)
                raise
        
        logger.error(f"Timed out waiting for Apify actor run {run_id}")
        raise TimeoutError(f"Timed out waiting for Apify actor run {run_id}")
    
    async def get_dataset_items(self, dataset_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get items from an Apify dataset.
        
        Args:
            dataset_id: ID of the dataset
            limit: Maximum number of items to return
            
        Returns:
            List[Dict[str, Any]]: Dataset items
        """
        endpoint = f"/datasets/{dataset_id}/items"
        params = {"limit": limit, "format": "json"}
        
        try:
            response = await self._make_request("GET", endpoint, params=params)
            return response
        except Exception as e:
            logger.error(f"Error getting Apify dataset items: {str(e)}", exc_info=True)
            raise RuntimeError(f"Error getting Apify dataset items: {str(e)}")
    
    async def scrape_instagram_user(
        self, 
        username: str = "austinnasso", 
        limit: int = 10
    ) -> List[InstagramPost]:
        """
        Scrape Instagram posts from a specific user using Apify.
        
        Args:
            username: Instagram username to scrape
            limit: Maximum number of posts to return
            
        Returns:
            List[InstagramPost]: List of Instagram posts
        """
        logger.info(f"Scraping Instagram posts for user: {username} using Apify (backup)")
        
        # Prepare actor input
        run_input = {
            "usernames": [username],
            "resultsType": "posts",
            "resultsLimit": max(limit * 2, 20),  # Request more to account for filtering
            "addUserInfo": True,
            "proxy": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"]
            }
        }
        
        try:
            # Start actor run
            run_id = await self.start_actor_run("apify/instagram-scraper", run_input)
            
            # Wait for run to complete
            run_data = await self.wait_for_run(run_id)
            
            # Get dataset ID from run
            default_dataset_id = run_data.get("defaultDatasetId")
            if not default_dataset_id:
                raise ValueError("Default dataset ID not found in run data")
            
            # Get dataset items
            items = await self.get_dataset_items(default_dataset_id, limit * 2)
            
            # Transform to InstagramPost model
            return self._transform_instagram_data(items, username, limit)
        except Exception as e:
            logger.error(f"Error scraping Instagram with Apify: {str(e)}", exc_info=True)
            raise RuntimeError(f"Error scraping Instagram with Apify: {str(e)}")
    
    def _transform_instagram_data(
        self, 
        data: List[Dict[str, Any]], 
        username: str, 
        limit: int
    ) -> List[InstagramPost]:
        """
        Transform raw Instagram data from Apify to InstagramPost models.
        
        Args:
            data: Raw data from Apify
            username: Instagram username
            limit: Maximum number of posts to return
            
        Returns:
            List[InstagramPost]: List of Instagram posts
        """
        posts = []
        
        try:
            # Extract user data for engagement calculation
            user_data = next((item for item in data if item.get("type") == "user"), {})
            follower_count = user_data.get("followersCount", 0) or user_data.get("followers", 0)
            
            # Extract posts
            post_items = [item for item in data if item.get("type") == "post"]
            
            for post in post_items[:limit]:
                try:
                    # Extract post data
                    post_id = post.get("id") or post.get("shortCode", f"unknown_{len(posts)}")
                    caption = post.get("caption", "")
                    
                    # Get image URL
                    image_url = ""
                    if "imageUrl" in post:
                        image_url = post["imageUrl"]
                    elif "displayUrl" in post:
                        image_url = post["displayUrl"]
                    elif "images" in post and post["images"]:
                        image_url = post["images"][0]
                    
                    # Get video URL if available
                    video_url = None
                    if "videoUrl" in post:
                        video_url = post["videoUrl"]
                    elif "video" in post and post["video"]:
                        video_url = post["video"]
                    
                    # Extract engagement metrics
                    likes = post.get("likesCount", 0) or post.get("likes", 0)
                    comments = post.get("commentsCount", 0) or post.get("comments", 0)
                    
                    # Calculate engagement rate if follower count is available
                    engagement_rate = None
                    if follower_count > 0:
                        engagement_rate = round((likes + comments) / follower_count * 100, 2)
                    
                    # Extract timestamp
                    timestamp = None
                    if "timestamp" in post:
                        timestamp = post["timestamp"]
                    elif "createdAt" in post:
                        timestamp = post["createdAt"]
                    elif "taken_at_timestamp" in post:
                        timestamp_value = post["taken_at_timestamp"]
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
                    logger.warning(f"Error processing Instagram post from Apify: {str(e)}")
            
            logger.info(f"Successfully processed {len(posts)} Instagram posts from Apify for {username}")
            return posts
        except Exception as e:
            logger.error(f"Error transforming Instagram data from Apify: {str(e)}", exc_info=True)
            # Return whatever posts were successfully processed
            return posts
