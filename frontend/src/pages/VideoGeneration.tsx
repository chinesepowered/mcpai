import React, { useState, useEffect } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import { FiVideo, FiSettings, FiClock, FiMic, FiMusic, FiType, FiCheck, FiArrowLeft, FiAlertCircle } from 'react-icons/fi';
import toast from 'react-hot-toast';
import { useLoading } from '../App';
import apiService from '../services/api';
import { InstagramPost, VideoGenerationRequest, VideoGenerationResponse, VideoStyle, VoiceType, MusicStyle } from '../types';

// Video style options for the form
const videoStyleOptions = [
  { value: VideoStyle.COMEDY, label: 'Comedy' },
  { value: VideoStyle.DRAMATIC, label: 'Dramatic' },
  { value: VideoStyle.INFORMATIVE, label: 'Informative' },
  { value: VideoStyle.INSPIRATIONAL, label: 'Inspirational' },
  { value: VideoStyle.SATIRICAL, label: 'Satirical (Tech Parody)' },
];

// Voice type options for the form
const voiceTypeOptions = [
  { value: VoiceType.MALE, label: 'Male Voice' },
  { value: VoiceType.FEMALE, label: 'Female Voice' },
  { value: VoiceType.ROBOTIC, label: 'Robotic Voice' },
  { value: VoiceType.NARRATOR, label: 'Narrator Voice' },
];

// Music style options for the form
const musicStyleOptions = [
  { value: MusicStyle.UPBEAT, label: 'Upbeat' },
  { value: MusicStyle.DRAMATIC, label: 'Dramatic' },
  { value: MusicStyle.EMOTIONAL, label: 'Emotional' },
  { value: MusicStyle.FUNNY, label: 'Funny' },
  { value: MusicStyle.NONE, label: 'No Music' },
];

// Duration options for the form
const durationOptions = [
  { value: 15, label: '15 seconds' },
  { value: 30, label: '30 seconds' },
  { value: 45, label: '45 seconds' },
  { value: 60, label: '60 seconds' },
  { value: 90, label: '90 seconds' },
  { value: 120, label: '2 minutes' },
];

// VideoGeneration component
const VideoGeneration: React.FC = () => {
  // Hooks for routing and navigation
  const { postId } = useParams<{ postId: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const { setIsLoading, setLoadingMessage } = useLoading();
  
  // State for post and form
  const [post, setPost] = useState<InstagramPost | null>(
    location.state?.post || null
  );
  const [error, setError] = useState<string | null>(null);
  
  // Form state
  const [style, setStyle] = useState<VideoStyle>(VideoStyle.SATIRICAL);
  const [duration, setDuration] = useState<number>(30);
  const [voiceType, setVoiceType] = useState<VoiceType>(VoiceType.MALE);
  const [includeCaptions, setIncludeCaptions] = useState<boolean>(true);
  const [musicStyle, setMusicStyle] = useState<MusicStyle>(MusicStyle.UPBEAT);
  
  // Fetch post if not provided in location state
  useEffect(() => {
    const fetchPost = async () => {
      if (!postId) {
        setError('No post ID provided');
        return;
      }
      
      if (post) {
        return; // Already have post data
      }
      
      try {
        setIsLoading(true);
        setLoadingMessage('Loading post details...');
        
        // In a real implementation, we would fetch the post details from the API
        // const fetchedPost = await apiService.getPostById(postId);
        // setPost(fetchedPost);
        
        // For now, create a placeholder post
        const placeholderPost: InstagramPost = {
          id: postId,
          caption: 'This is a placeholder post caption. In a real implementation, this would be fetched from the API.',
          image_url: 'https://picsum.photos/seed/' + postId + '/600/600',
          likes: 1000,
          comments: 50,
          engagement_rate: 4.5,
          timestamp: new Date().toISOString(),
        };
        
        setPost(placeholderPost);
      } catch (error) {
        const apiError = apiService.handleApiError(error);
        setError(`Failed to load post: ${apiError.message}`);
        toast.error(`Failed to load post: ${apiError.message}`);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchPost();
  }, [postId, post, setIsLoading, setLoadingMessage]);
  
  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!post) {
      toast.error('No post data available');
      return;
    }
    
    try {
      setError(null);
      setIsLoading(true);
      setLoadingMessage('Generating video...');
      
      const request: VideoGenerationRequest = {
        post_id: post.id,
        caption: post.caption,
        image_url: post.image_url,
        style,
        duration,
        voice_type: voiceType,
        include_captions: includeCaptions,
        music_style: musicStyle,
      };
      
      const response = await apiService.generateVideo(request);
      
      toast.success('Video generation started!');
      
      // Navigate to the video preview page
      navigate(`/preview/${response.video_id}`, {
        state: { 
          videoResponse: response,
          sourcePost: post,
          generationOptions: {
            style,
            duration,
            voice_type: voiceType,
            include_captions: includeCaptions,
            music_style: musicStyle,
          }
        }
      });
    } catch (error) {
      const apiError = apiService.handleApiError(error);
      setError(`Failed to generate video: ${apiError.message}`);
      toast.error(`Failed to generate video: ${apiError.message}`);
    } finally {
      setIsLoading(false);
    }
  };
  
  // Handle navigation back
  const handleGoBack = () => {
    navigate(location.state?.returnPath || '/discover');
  };
  
  // If there's an error and no post, show error state
  if (error && !post) {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="text-3xl font-bold">Video Generation</h1>
          <p className="text-gray-600 dark:text-gray-300 mt-2">
            Configure and generate a viral video from Instagram content.
          </p>
        </div>
        
        <div className="bg-red-50 dark:bg-red-900/20 border-l-4 border-red-500 p-4 rounded-r-lg">
          <div className="flex">
            <div className="flex-shrink-0">
              <FiAlertCircle className="h-5 w-5 text-red-500" />
            </div>
            <div className="ml-3">
              <p className="text-red-700 dark:text-red-300">{error}</p>
              <div className="mt-2">
                <button
                  type="button"
                  className="btn btn-sm bg-red-500 hover:bg-red-600 text-white"
                  onClick={handleGoBack}
                >
                  Go Back
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }
  
  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <button
          onClick={handleGoBack}
          className="flex items-center text-brand hover:text-brand-dark mb-4"
        >
          <FiArrowLeft className="mr-2" />
          Back to discovery
        </button>
        
        <h1 className="text-3xl font-bold">Generate Viral Video</h1>
        <p className="text-gray-600 dark:text-gray-300 mt-2">
          Configure options to transform this Instagram post into a viral video.
        </p>
      </div>
      
      {/* Post preview and generation form */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Post preview */}
        <div className="lg:col-span-1">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden sticky top-4">
            <div className="aspect-square">
              {post && (
                <img 
                  src={post.image_url} 
                  alt="Instagram post"
                  className="w-full h-full object-cover"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src = 'https://via.placeholder.com/600x600?text=Image+Not+Available';
                  }}
                />
              )}
            </div>
            <div className="p-4">
              <p className="text-sm line-clamp-4">{post?.caption}</p>
              
              {post && (
                <div className="mt-2 text-xs text-gray-500 dark:text-gray-400 flex items-center justify-between">
                  <div className="flex items-center">
                    <span className="mr-2">❤️ {post.likes?.toLocaleString() || 'N/A'}</span>
                    <span>💬 {post.comments?.toLocaleString() || 'N/A'}</span>
                  </div>
                  
                  {post.engagement_rate !== undefined && (
                    <span className={`px-2 py-1 rounded-full ${
                      post.engagement_rate > 5 ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' :
                      post.engagement_rate > 2 ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' :
                      'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                    }`}>
                      {post.engagement_rate.toFixed(1)}% Engagement
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
        
        {/* Generation form */}
        <div className="lg:col-span-2">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4 flex items-center">
              <FiSettings className="mr-2" />
              Video Generation Options
            </h2>
            
            <form onSubmit={handleSubmit} className="generation-form">
              {/* Video style */}
              <div className="form-group">
                <label htmlFor="style" className="form-label flex items-center">
                  <FiVideo className="mr-2" />
                  Video Style
                </label>
                <select
                  id="style"
                  className="input"
                  value={style}
                  onChange={(e) => setStyle(e.target.value as VideoStyle)}
                >
                  {videoStyleOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  Choose the overall tone and style for your video.
                </p>
              </div>
              
              {/* Video duration */}
              <div className="form-group">
                <label htmlFor="duration" className="form-label flex items-center">
                  <FiClock className="mr-2" />
                  Video Duration
                </label>
                <select
                  id="duration"
                  className="input"
                  value={duration}
                  onChange={(e) => setDuration(parseInt(e.target.value))}
                >
                  {durationOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  Shorter videos typically perform better on social media.
                </p>
              </div>
              
              {/* Voice type */}
              <div className="form-group">
                <label htmlFor="voiceType" className="form-label flex items-center">
                  <FiMic className="mr-2" />
                  Voice Type
                </label>
                <select
                  id="voiceType"
                  className="input"
                  value={voiceType}
                  onChange={(e) => setVoiceType(e.target.value as VoiceType)}
                >
                  {voiceTypeOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  Select the voice that will narrate your video.
                </p>
              </div>
              
              {/* Music style */}
              <div className="form-group">
                <label htmlFor="musicStyle" className="form-label flex items-center">
                  <FiMusic className="mr-2" />
                  Background Music
                </label>
                <select
                  id="musicStyle"
                  className="input"
                  value={musicStyle}
                  onChange={(e) => setMusicStyle(e.target.value as MusicStyle)}
                >
                  {musicStyleOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  Choose background music that matches your video's mood.
                </p>
              </div>
              
              {/* Include captions toggle */}
              <div className="form-group">
                <label className="form-label flex items-center mb-2">
                  <FiType className="mr-2" />
                  Captions
                </label>
                <label className="inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    className="sr-only peer"
                    checked={includeCaptions}
                    onChange={(e) => setIncludeCaptions(e.target.checked)}
                  />
                  <div className="relative w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-brand/30 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-brand"></div>
                  <span className="ms-3 text-sm font-medium text-gray-900 dark:text-gray-300">
                    Include on-screen captions
                  </span>
                </label>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  Captions improve engagement and accessibility.
                </p>
              </div>
              
              {/* Submit button */}
              <div className="mt-8">
                <button
                  type="submit"
                  className="btn btn-lg btn-primary w-full flex items-center justify-center"
                  disabled={!post}
                >
                  <FiVideo className="mr-2" />
                  Generate Viral Video
                </button>
                
                {error && (
                  <p className="mt-2 text-sm text-red-600 dark:text-red-400">
                    {error}
                  </p>
                )}
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};

export default VideoGeneration;
