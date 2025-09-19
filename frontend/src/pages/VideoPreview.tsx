import React, { useState, useEffect, useRef } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import { FiDownload, FiShare2, FiArrowLeft, FiAlertCircle, FiCheck, FiRefreshCw, FiPlay, FiPause, FiVolume2, FiVolumeX } from 'react-icons/fi';
import toast from 'react-hot-toast';
import { useLoading } from '../App';
import apiService from '../services/api';
import { VideoStatus, VideoProcessingStatus, InstagramPost, CompletedVideo } from '../types';

// Progress indicator component
interface ProgressBarProps {
  progress: number;
  status: VideoProcessingStatus;
}

const ProgressBar: React.FC<ProgressBarProps> = ({ progress, status }) => {
  const progressPercent = Math.min(Math.max(progress * 100, 0), 100);
  
  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center text-sm">
        <span className="font-medium">
          {status === 'processing' ? 'Processing video...' : 
           status === 'completed' ? 'Video ready!' : 
           'Processing failed'}
        </span>
        <span>{Math.round(progressPercent)}%</span>
      </div>
      <div className="progress-bar">
        <div 
          className={`progress-bar-fill ${
            status === 'failed' ? 'bg-red-500' : 
            status === 'completed' ? 'bg-green-500' : 
            'bg-brand'
          }`} 
          style={{ width: `${progressPercent}%` }}
        ></div>
      </div>
    </div>
  );
};

// Video player component
interface VideoPlayerProps {
  videoUrl: string;
  thumbnailUrl?: string;
}

const VideoPlayer: React.FC<VideoPlayerProps> = ({ videoUrl, thumbnailUrl }) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  
  // Handle play/pause
  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };
  
  // Handle mute/unmute
  const toggleMute = () => {
    if (videoRef.current) {
      videoRef.current.muted = !isMuted;
      setIsMuted(!isMuted);
    }
  };
  
  // Update time display
  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };
  
  // Set duration when metadata is loaded
  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  };
  
  // Format time display (mm:ss)
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };
  
  // Handle seeking
  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const seekTime = parseFloat(e.target.value);
    if (videoRef.current) {
      videoRef.current.currentTime = seekTime;
      setCurrentTime(seekTime);
    }
  };
  
  return (
    <div className="video-player rounded-lg overflow-hidden bg-black">
      <div className="relative">
        <video
          ref={videoRef}
          src={videoUrl}
          poster={thumbnailUrl}
          className="w-full max-h-[70vh] mx-auto"
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={handleLoadedMetadata}
          onEnded={() => setIsPlaying(false)}
          onClick={togglePlay}
        />
        
        {/* Video controls */}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-4 text-white">
          {/* Progress bar */}
          <input
            type="range"
            min={0}
            max={duration || 100}
            value={currentTime}
            onChange={handleSeek}
            className="w-full h-1 bg-gray-400 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white"
          />
          
          {/* Controls */}
          <div className="flex items-center justify-between mt-2">
            <div className="flex items-center space-x-4">
              <button 
                onClick={togglePlay}
                className="p-1 rounded-full hover:bg-white/20"
                aria-label={isPlaying ? "Pause" : "Play"}
              >
                {isPlaying ? <FiPause size={18} /> : <FiPlay size={18} />}
              </button>
              
              <button
                onClick={toggleMute}
                className="p-1 rounded-full hover:bg-white/20"
                aria-label={isMuted ? "Unmute" : "Mute"}
              >
                {isMuted ? <FiVolumeX size={18} /> : <FiVolume2 size={18} />}
              </button>
              
              <span className="text-sm">
                {formatTime(currentTime)} / {formatTime(duration || 0)}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// Main VideoPreview component
const VideoPreview: React.FC = () => {
  // Hooks for routing and navigation
  const { videoId } = useParams<{ videoId: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const { setIsLoading, setLoadingMessage } = useLoading();
  
  // State for video status and data
  const [videoStatus, setVideoStatus] = useState<VideoStatus | null>(null);
  const [completedVideo, setCompletedVideo] = useState<CompletedVideo | null>(null);
  const [sourcePost, setSourcePost] = useState<InstagramPost | null>(
    location.state?.sourcePost || null
  );
  const [error, setError] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  
  // Polling interval reference
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  
  // Initial video response from generation (if available)
  const initialVideoResponse = location.state?.videoResponse;
  
  // Set up polling for video status
  useEffect(() => {
    if (!videoId) {
      setError('No video ID provided');
      return;
    }
    
    // Initialize with data from navigation state if available
    if (initialVideoResponse) {
      setVideoStatus({
        video_id: initialVideoResponse.video_id,
        status: initialVideoResponse.status as VideoProcessingStatus,
        progress: 0,
        video_url: initialVideoResponse.video_url,
        thumbnail_url: initialVideoResponse.thumbnail_url,
        duration: initialVideoResponse.duration,
      });
    }
    
    // Function to fetch video status
    const fetchVideoStatus = async () => {
      try {
        const status = await apiService.getVideoStatus(videoId);
        setVideoStatus(status);
        
        // If completed, fetch the full video details
        if (status.status === 'completed') {
          try {
            const video = await apiService.getCompletedVideo(videoId);
            setCompletedVideo(video);
            
            // Clear polling interval
            if (pollingIntervalRef.current) {
              clearInterval(pollingIntervalRef.current);
              pollingIntervalRef.current = null;
            }
          } catch (error) {
            console.error('Error fetching completed video:', error);
          }
        }
        
        // If failed, stop polling
        if (status.status === 'failed') {
          if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
            pollingIntervalRef.current = null;
          }
          setError(status.error || 'Video generation failed');
          toast.error('Video generation failed');
        }
      } catch (error) {
        const apiError = apiService.handleApiError(error);
        setError(`Failed to get video status: ${apiError.message}`);
        
        // Don't show toast on every poll failure
        console.error('Error polling video status:', apiError);
      }
    };
    
    // Initial fetch
    fetchVideoStatus();
    
    // Set up polling interval (every 3 seconds)
    pollingIntervalRef.current = setInterval(fetchVideoStatus, 3000);
    
    // Cleanup on unmount
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, [videoId, initialVideoResponse]);
  
  // Handle download
  const handleDownload = async () => {
    if (!completedVideo?.video_url) {
      toast.error('Video URL not available');
      return;
    }
    
    try {
      setIsDownloading(true);
      await apiService.downloadVideo(
        completedVideo.video_url,
        `viral-video-${videoId}.mp4`
      );
      toast.success('Video downloaded successfully');
    } catch (error) {
      const apiError = apiService.handleApiError(error);
      toast.error(`Failed to download video: ${apiError.message}`);
    } finally {
      setIsDownloading(false);
    }
  };
  
  // Handle retry
  const handleRetry = () => {
    if (!sourcePost) {
      navigate('/discover');
      return;
    }
    
    navigate(`/generate/${sourcePost.id}`, {
      state: { post: sourcePost }
    });
  };
  
  // Handle navigation back
  const handleGoBack = () => {
    navigate(location.state?.returnPath || '/');
  };
  
  // Handle share (placeholder - would integrate with Web Share API)
  const handleShare = () => {
    if (!completedVideo?.video_url) {
      toast.error('Video URL not available');
      return;
    }
    
    // Check if Web Share API is available
    if (navigator.share) {
      navigator.share({
        title: 'Check out my viral video!',
        text: sourcePost?.caption || 'Generated with Viral Marketing Agent',
        url: completedVideo.video_url,
      })
      .then(() => toast.success('Shared successfully'))
      .catch((error) => {
        console.error('Error sharing:', error);
        toast.error('Failed to share video');
      });
    } else {
      // Fallback - copy URL to clipboard
      navigator.clipboard.writeText(completedVideo.video_url)
        .then(() => toast.success('Video URL copied to clipboard'))
        .catch(() => toast.error('Failed to copy URL'));
    }
  };
  
  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <button
          onClick={handleGoBack}
          className="flex items-center text-brand hover:text-brand-dark mb-4"
        >
          <FiArrowLeft className="mr-2" />
          Back
        </button>
        
        <h1 className="text-3xl font-bold">Video Preview</h1>
        <p className="text-gray-600 dark:text-gray-300 mt-2">
          {videoStatus?.status === 'completed' 
            ? 'Your viral video is ready to download and share!' 
            : videoStatus?.status === 'failed'
            ? 'There was a problem generating your video.'
            : 'Your viral video is being generated. This may take a minute...'}
        </p>
      </div>
      
      {/* Video preview and status */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Video preview */}
        <div className="lg:col-span-2">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
            {/* Show video player if completed */}
            {videoStatus?.status === 'completed' && videoStatus.video_url ? (
              <VideoPlayer 
                videoUrl={videoStatus.video_url}
                thumbnailUrl={videoStatus.thumbnail_url}
              />
            ) : (
              /* Show placeholder with source image while processing */
              <div className="aspect-video bg-gray-900 flex items-center justify-center relative">
                {sourcePost?.image_url && (
                  <img 
                    src={sourcePost.image_url} 
                    alt="Source content"
                    className="absolute inset-0 w-full h-full object-contain opacity-30"
                  />
                )}
                
                <div className="z-10 text-center p-8">
                  {videoStatus?.status === 'failed' ? (
                    <div className="flex flex-col items-center">
                      <div className="rounded-full bg-red-100 p-4 mb-4">
                        <FiAlertCircle size={32} className="text-red-500" />
                      </div>
                      <h3 className="text-xl font-semibold text-white mb-2">Video Generation Failed</h3>
                      <p className="text-gray-300 mb-4">{videoStatus.error || 'An error occurred during video generation'}</p>
                      <button 
                        onClick={handleRetry}
                        className="btn btn-md btn-primary"
                      >
                        <FiRefreshCw className="mr-2" />
                        Try Again
                      </button>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center">
                      <div className="spinner spinner-xl border-brand mb-4"></div>
                      <h3 className="text-xl font-semibold text-white mb-2">Generating Your Video</h3>
                      <p className="text-gray-300 mb-4">This usually takes 30-60 seconds</p>
                    </div>
                  )}
                </div>
              </div>
            )}
            
            {/* Progress bar */}
            {videoStatus && videoStatus.status !== 'completed' && (
              <div className="p-4">
                <ProgressBar 
                  progress={videoStatus.progress || 0}
                  status={videoStatus.status}
                />
              </div>
            )}
            
            {/* Video actions (download, share) */}
            {videoStatus?.status === 'completed' && (
              <div className="p-4 flex flex-wrap gap-4">
                <button
                  onClick={handleDownload}
                  disabled={isDownloading}
                  className="btn btn-md btn-primary flex-1"
                >
                  {isDownloading ? (
                    <span className="spinner spinner-sm mr-2"></span>
                  ) : (
                    <FiDownload className="mr-2" />
                  )}
                  Download Video
                </button>
                
                <button
                  onClick={handleShare}
                  className="btn btn-md btn-outline flex-1"
                >
                  <FiShare2 className="mr-2" />
                  Share
                </button>
              </div>
            )}
          </div>
        </div>
        
        {/* Video details and source */}
        <div className="lg:col-span-1">
          {/* Video details */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6">
            <h2 className="text-xl font-semibold mb-4">Video Details</h2>
            
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Status</h3>
                <div className="mt-1 flex items-center">
                  {videoStatus?.status === 'completed' ? (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                      <FiCheck className="mr-1" />
                      Completed
                    </span>
                  ) : videoStatus?.status === 'failed' ? (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
                      <FiAlertCircle className="mr-1" />
                      Failed
                    </span>
                  ) : (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                      <svg className="animate-spin -ml-1 mr-2 h-3 w-3 text-blue-800 dark:text-blue-200" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Processing
                    </span>
                  )}
                </div>
              </div>
              
              {videoStatus?.status === 'completed' && (
                <>
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Duration</h3>
                    <p className="mt-1">
                      {videoStatus.duration 
                        ? `${Math.floor(videoStatus.duration / 60)}:${(videoStatus.duration % 60).toString().padStart(2, '0')}`
                        : 'Unknown'}
                    </p>
                  </div>
                  
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Created</h3>
                    <p className="mt-1">
                      {new Date().toLocaleDateString()} {/* In a real app, use actual creation date */}
                    </p>
                  </div>
                </>
              )}
              
              {/* Generation options from state if available */}
              {location.state?.generationOptions && (
                <div>
                  <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Generation Style</h3>
                  <p className="mt-1 capitalize">
                    {location.state.generationOptions.style}
                  </p>
                </div>
              )}
            </div>
          </div>
          
          {/* Source post */}
          {sourcePost && (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
              <h2 className="text-xl font-semibold p-4 border-b border-gray-200 dark:border-gray-700">Source Content</h2>
              <div className="aspect-square w-full">
                <img 
                  src={sourcePost.image_url} 
                  alt="Source Instagram post"
                  className="w-full h-full object-cover"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src = 'https://via.placeholder.com/300x300?text=Image+Not+Available';
                  }}
                />
              </div>
              <div className="p-4">
                <p className="text-sm line-clamp-3">{sourcePost.caption}</p>
                
                <div className="mt-2 text-xs text-gray-500 dark:text-gray-400 flex items-center justify-between">
                  <div className="flex items-center">
                    <span className="mr-2">❤️ {sourcePost.likes?.toLocaleString() || 'N/A'}</span>
                    <span>💬 {sourcePost.comments?.toLocaleString() || 'N/A'}</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default VideoPreview;
