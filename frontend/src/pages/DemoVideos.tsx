import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
// Correct API client import
import { apiService } from '../services/api';

interface DemoPrompt {
  id: string;
  title: string;
  text: string;
  imageUrl?: string;
}

interface VideoStatus {
  loading: boolean;
  videoId?: string;
  videoUrl?: string;
  thumbnailUrl?: string;
  error?: string;
}

const DemoVideos: React.FC = () => {
  const navigate = useNavigate();
  
  // Demo prompts for quick video generation
  const demoPrompts: DemoPrompt[] = [
    {
      id: "olympic-dive",
      title: "Olympic Cat Diving Champion",
      text: "Televised footage of a cat doing an acrobatic dive into a swimming pool at the Olympics, from a 10m high diving board, flips and spins",
      imageUrl: "https://images.unsplash.com/photo-1583524505974-6facd53f4597?q=80&w=600&auto=format&fit=crop"
    },
    {
      id: "diving-board",
      title: "Cat at Olympic Diving Board",
      text: "An orange cat standing straight at the 5meter high diving board at the Olympic Games, there were several people sitting around watching the event",
      imageUrl: "https://images.unsplash.com/photo-1573865526739-10659fec78a5?q=80&w=600&auto=format&fit=crop"
    },
    // Tech / AI themed prompt
    {
      id: "ai-future",
      title: "AI Future Lab Collaboration",
      text: "A futuristic scene of humanoid robots collaborating with human engineers in a neon-lit lab, cinematic lighting, ultra-realistic",
      imageUrl: "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?q=80&w=600&auto=format&fit=crop"
    },
    // Sports / action prompt
    {
      id: "mountain-bike",
      title: "Epic Mountain Bike Jump",
      text: "Slow-motion shot of a mountain biker launching off a cliff at sunset, dust and debris flying, GoPro perspective, epic soundtrack",
      imageUrl: "https://images.unsplash.com/photo-1504439904031-93ded9ce4156?q=80&w=600&auto=format&fit=crop"
    }
  ];

  // Track status for each demo prompt
  const [videoStatus, setVideoStatus] = useState<Record<string, VideoStatus>>({
    "olympic-dive": { loading: false },
    "diving-board": { loading: false },
    "ai-future": { loading: false },
    "mountain-bike": { loading: false }
  });

  // Generate video for a demo prompt
  const generateVideo = async (prompt: DemoPrompt) => {
    // Update loading state
    setVideoStatus(prev => ({
      ...prev,
      [prompt.id]: { loading: true }
    }));

    try {
      // Call API to start video generation
      const response = await apiService.post('/api/generate-video', {
        post_id: `demo-${prompt.id}`,
        caption: prompt.text,
        image_url: prompt.imageUrl || '',
        style: 'cinematic',
        duration: 30,
        voice_type: 'male',
        include_captions: true,
        music_style: 'dramatic'
      });

      const { video_id } = response.data;

      // Update status with video ID
      setVideoStatus(prev => ({
        ...prev,
        [prompt.id]: { 
          loading: true,
          videoId: video_id
        }
      }));

      // Poll for video status
      pollVideoStatus(prompt.id, video_id);
    } catch (error) {
      console.error('Error generating video:', error);
      setVideoStatus(prev => ({
        ...prev,
        [prompt.id]: { 
          loading: false,
          error: 'Failed to start video generation'
        }
      }));
    }
  };

  // Poll for video status until complete or error
  const pollVideoStatus = async (promptId: string, videoId: string) => {
    try {
      const response = await apiService.get(`/api/video-status/${videoId}`);
      const { status, video_url, thumbnail_url, error } = response.data;

      if (status === 'completed' && video_url) {
        // Video is ready
        setVideoStatus(prev => ({
          ...prev,
          [promptId]: {
            loading: false,
            videoId,
            videoUrl: video_url,
            thumbnailUrl: thumbnail_url
          }
        }));
      } else if (status === 'failed' || error) {
        // Video generation failed
        setVideoStatus(prev => ({
          ...prev,
          [promptId]: {
            loading: false,
            videoId,
            error: error || 'Video generation failed'
          }
        }));
      } else {
        // Still processing, poll again after delay
        setTimeout(() => pollVideoStatus(promptId, videoId), 3000);
      }
    } catch (error) {
      console.error('Error polling video status:', error);
      setVideoStatus(prev => ({
        ...prev,
        [promptId]: {
          loading: false,
          videoId,
          error: 'Error checking video status'
        }
      }));
    }
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="bg-gradient-to-r from-purple-600 to-indigo-700 rounded-lg p-6 mb-8 shadow-lg">
        <h1 className="text-3xl font-bold text-white mb-2">🎬 Video Templates</h1>
        <p className="text-white text-lg opacity-90">
          Explore a selection of professionally-crafted prompts designed to
          highlight the full capabilities of our AI video engine. Simply choose a
          template and generate a high-impact video in one click—no additional
          content required.
        </p>
        <div className="mt-4 bg-white bg-opacity-20 p-3 rounded-md">
          <p className="text-white text-sm">
            These templates run through the same production-grade MiniMax
            pipeline used for your custom videos, delivering studio-quality
            results in seconds.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {demoPrompts.map(prompt => (
          <div key={prompt.id} className="bg-white rounded-lg shadow-md overflow-hidden border border-gray-200">
            <div className="p-6">
              <h2 className="text-xl font-bold text-gray-800 mb-3">{prompt.title}</h2>
              <div className="bg-gray-100 p-4 rounded-md mb-4">
                <p className="text-gray-800 font-medium">{prompt.text}</p>
              </div>

              {!videoStatus[prompt.id].videoUrl && !videoStatus[prompt.id].loading && (
                <button
                  onClick={() => generateVideo(prompt)}
                  disabled={videoStatus[prompt.id].loading}
                  className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 px-4 rounded-md transition duration-200"
                >
                  {videoStatus[prompt.id].loading ? (
                    <span className="flex items-center justify-center">
                      <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Generating Video...
                    </span>
                  ) : (
                    'Generate Video'
                  )}
                </button>
              )}

              {/* Loading state */}
              {videoStatus[prompt.id].loading && (
                <div className="mt-4">
                  <div className="w-full bg-gray-200 rounded-full h-2.5">
                    <div className="bg-indigo-600 h-2.5 rounded-full animate-pulse w-full"></div>
                  </div>
                  <p className="text-sm text-gray-600 mt-2 text-center">
                    Generating your video... This may take 1-2 minutes.
                  </p>
                </div>
              )}

              {/* Error state */}
              {videoStatus[prompt.id].error && (
                <div className="mt-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
                  <p className="font-medium">Generation failed</p>
                  <p className="text-sm">{videoStatus[prompt.id].error}</p>
                  <button
                    onClick={() => generateVideo(prompt)}
                    className="mt-2 text-sm bg-red-100 hover:bg-red-200 text-red-700 font-medium py-1 px-2 rounded"
                  >
                    Try Again
                  </button>
                </div>
              )}

              {/* Video result */}
              {videoStatus[prompt.id].videoUrl && (
                <div className="mt-4">
                  <div className="relative pt-[56.25%] bg-black rounded-md overflow-hidden">
                    <video
                      src={videoStatus[prompt.id].videoUrl}
                      poster={videoStatus[prompt.id].thumbnailUrl}
                      controls
                      className="absolute top-0 left-0 w-full h-full object-contain"
                    />
                  </div>
                  <div className="mt-3 flex justify-between">
                    <button
                      onClick={() => window.open(videoStatus[prompt.id].videoUrl, '_blank')}
                      className="text-sm bg-gray-100 hover:bg-gray-200 text-gray-800 font-medium py-1 px-3 rounded"
                    >
                      Open in New Tab
                    </button>
                    <button
                      onClick={() => generateVideo(prompt)}
                      className="text-sm bg-indigo-100 hover:bg-indigo-200 text-indigo-700 font-medium py-1 px-3 rounded"
                    >
                      Generate Again
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-8 flex justify-center">
        <button
          onClick={() => navigate('/content')}
          className="bg-gray-200 hover:bg-gray-300 text-gray-800 font-medium py-2 px-4 rounded-md transition duration-200"
        >
          Back to Content Discovery
        </button>
      </div>
    </div>
  );
};

export default DemoVideos;
