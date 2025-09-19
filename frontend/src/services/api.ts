import axios, { AxiosError, AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import {
  ApiError,
  ApiResponse,
  CompletedVideo,
  ErrorType,
  InstagramPost,
  ScrapingRequest,
  VideoGenerationRequest,
  VideoGenerationResponse,
  VideoStatus
} from '../types';

/**
 * Configuration for the API client
 */
const API_CONFIG = {
  BASE_URL: '/api',
  // Default timeout for most API calls
  TIMEOUT: 60000, // 60 seconds
  // Video generation can take several minutes on MiniMax – use a much larger timeout
  VIDEO_GENERATION_TIMEOUT: 600000, // 10 minutes
  RETRY_COUNT: 3,
  RETRY_DELAY: 1000, // 1 second
  ENDPOINTS: {
    HEALTH: '/health',
    SCRAPE: '/scrape',
    GENERATE_VIDEO: '/generate-video',
    VIDEO_STATUS: '/video-status',
    VIDEOS: '/videos',
  }
};

/**
 * Creates and configures an Axios instance for API requests
 */
const createApiClient = (): AxiosInstance => {
  const client = axios.create({
    baseURL: API_CONFIG.BASE_URL,
    timeout: API_CONFIG.TIMEOUT,
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
  });

  // Request interceptor
  client.interceptors.request.use(
    (config) => {
      // You can add authentication headers here if needed in the future
      return config;
    },
    (error) => {
      return Promise.reject(error);
    }
  );

  // Response interceptor
  client.interceptors.response.use(
    (response) => {
      return response;
    },
    async (error: AxiosError) => {
      const originalRequest = error.config as AxiosRequestConfig & { _retry?: number };
      
      // Initialize retry count if not already set
      if (originalRequest._retry === undefined) {
        originalRequest._retry = 0;
      }

      // Handle retry logic for network errors or 5xx server errors
      if (
        (error.response?.status && error.response.status >= 500) || 
        error.message === 'Network Error'
      ) {
        // If we haven't exceeded retry count
        if (originalRequest._retry < API_CONFIG.RETRY_COUNT) {
          originalRequest._retry += 1;
          
          // Wait before retrying (with exponential backoff)
          const delay = API_CONFIG.RETRY_DELAY * Math.pow(2, originalRequest._retry - 1);
          await new Promise(resolve => setTimeout(resolve, delay));
          
          // Retry the request
          return client(originalRequest);
        }
      }

      // Transform error to our standard ApiError format
      const apiError: ApiError = {
        status: error.response?.status || 0,
        message: error.message || 'Unknown error occurred',
        detail: error.response?.data || error.message,
      };

      return Promise.reject(apiError);
    }
  );

  return client;
};

// Create a singleton instance of the API client
const apiClient = createApiClient();

/**
 * API service for interacting with the backend
 */
export const apiService = {
  /**
   * Check if the API is healthy
   */
  checkHealth: async (): Promise<boolean> => {
    try {
      const response = await apiClient.get<{ status: string }>(API_CONFIG.ENDPOINTS.HEALTH);
      return response.data.status === 'ok';
    } catch (error) {
      return false;
    }
  },

  /**
   * Scrape Instagram content
   * @param request Scraping request parameters
   */
  scrapeInstagramContent: async (request: ScrapingRequest): Promise<InstagramPost[]> => {
    try {
      const response = await apiClient.post<InstagramPost[]>(
        API_CONFIG.ENDPOINTS.SCRAPE,
        request
      );
      return response.data;
    } catch (error) {
      if ((error as ApiError).status) {
        throw error;
      }
      
      throw {
        status: 500,
        message: 'Failed to scrape Instagram content',
        detail: error,
      } as ApiError;
    }
  },

  /**
   * Generate a video from an Instagram post
   * @param request Video generation request
   */
  generateVideo: async (request: VideoGenerationRequest): Promise<VideoGenerationResponse> => {
    try {
      const response = await apiClient.post<VideoGenerationResponse>(
        API_CONFIG.ENDPOINTS.GENERATE_VIDEO,
        request,
        {
          // Override default timeout for long-running generation job
          timeout: API_CONFIG.VIDEO_GENERATION_TIMEOUT,
        }
      );
      return response.data;
    } catch (error) {
      if ((error as ApiError).status) {
        throw error;
      }
      
      throw {
        status: 500,
        message: 'Failed to generate video',
        detail: error,
      } as ApiError;
    }
  },

  /**
   * Get the status of a video generation task
   * @param videoId ID of the video
   */
  getVideoStatus: async (videoId: string): Promise<VideoStatus> => {
    try {
      const response = await apiClient.get<VideoStatus>(
        `${API_CONFIG.ENDPOINTS.VIDEO_STATUS}/${videoId}`
      );
      return response.data;
    } catch (error) {
      if ((error as ApiError).status) {
        throw error;
      }
      
      throw {
        status: 500,
        message: 'Failed to get video status',
        detail: error,
      } as ApiError;
    }
  },

  /**
   * Poll for video status until it's completed or failed
   * @param videoId ID of the video
   * @param interval Polling interval in milliseconds
   * @param maxAttempts Maximum number of polling attempts
   */
  pollVideoStatus: async (
    videoId: string, 
    interval = 2000, 
    maxAttempts = 60
  ): Promise<VideoStatus> => {
    return new Promise((resolve, reject) => {
      let attempts = 0;
      
      const checkStatus = async () => {
        try {
          const status = await apiService.getVideoStatus(videoId);
          
          if (status.status === 'completed' || status.status === 'failed') {
            resolve(status);
            return;
          }
          
          attempts++;
          
          if (attempts >= maxAttempts) {
            reject({
              status: 408,
              message: 'Timed out waiting for video processing',
              detail: `Exceeded maximum attempts (${maxAttempts})`,
            } as ApiError);
            return;
          }
          
          setTimeout(checkStatus, interval);
        } catch (error) {
          reject(error);
        }
      };
      
      checkStatus();
    });
  },

  /**
   * Get details of a completed video
   * @param videoId ID of the video
   */
  getCompletedVideo: async (videoId: string): Promise<CompletedVideo> => {
    try {
      const response = await apiClient.get<CompletedVideo>(
        `${API_CONFIG.ENDPOINTS.VIDEOS}/${videoId}`
      );
      return response.data;
    } catch (error) {
      if ((error as ApiError).status) {
        throw error;
      }
      
      throw {
        status: 500,
        message: 'Failed to get video details',
        detail: error,
      } as ApiError;
    }
  },

  /**
   * Download a video file
   * @param videoUrl URL of the video to download
   * @param filename Filename to save as
   */
  downloadVideo: async (videoUrl: string, filename: string): Promise<void> => {
    try {
      // Create a download link and trigger it
      const response = await fetch(videoUrl);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      
      link.href = url;
      link.download = filename || 'generated-video.mp4';
      document.body.appendChild(link);
      link.click();
      
      // Clean up
      setTimeout(() => {
        window.URL.revokeObjectURL(url);
        document.body.removeChild(link);
      }, 100);
    } catch (error) {
      throw {
        status: 500,
        message: 'Failed to download video',
        detail: error,
      } as ApiError;
    }
  },

  /**
   * Handle API errors consistently
   * @param error Error object from catch block
   */
  handleApiError: (error: unknown): ApiError => {
    if ((error as ApiError).status) {
      return error as ApiError;
    }
    
    if (error instanceof Error) {
      return {
        status: 500,
        message: error.message || 'An unexpected error occurred',
        detail: error,
      };
    }
    
    return {
      status: 500,
      message: 'An unexpected error occurred',
      detail: error,
    };
  }
};

export default apiService;
