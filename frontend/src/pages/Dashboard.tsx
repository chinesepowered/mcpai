import React from 'react';
import { useNavigate } from 'react-router-dom';
import { FiSearch, FiVideo } from 'react-icons/fi';

/**
 * Dashboard component - simplified version to avoid syntax errors
 * Provides basic navigation and welcome information
 */
const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  
  // Navigation handlers
  const handleDiscoverContent = () => {
    navigate('/discover');
  };
  
  const handleGenerateVideo = () => {
    navigate('/discover');
  };
  
  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-gray-600 dark:text-gray-300 mt-2">
          Welcome to the Viral Marketing Agent. Discover trending content and generate viral videos.
        </p>
      </div>
      
      {/* Welcome card */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">Get Started</h2>
        <p className="text-gray-600 dark:text-gray-300 mb-6">
          This tool helps you discover viral content from Instagram and transform it into 
          engaging videos using AI. Start by discovering content, then generate videos based 
          on what you find.
        </p>
        
        {/* Quick action buttons */}
        <div className="flex flex-col sm:flex-row gap-4">
          <button
            onClick={handleDiscoverContent}
            className="btn btn-md btn-primary flex items-center justify-center"
          >
            <FiSearch className="mr-2" />
            Discover Content
          </button>
          
          <button
            onClick={handleGenerateVideo}
            className="btn btn-md btn-outline flex items-center justify-center"
          >
            <FiVideo className="mr-2" />
            Generate Video
          </button>
        </div>
      </div>
      
      {/* Features overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-2">Content Discovery</h3>
          <p className="text-gray-600 dark:text-gray-300">
            Find trending content from popular Instagram accounts like Austin Nasso.
            Our system uses Bright Data MCP with Apify as a backup to ensure reliable scraping.
          </p>
        </div>
        
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-2">Video Generation</h3>
          <p className="text-gray-600 dark:text-gray-300">
            Transform Instagram posts into engaging videos using MiniMax MCP.
            Customize style, duration, voice type, and more to create perfect viral content.
          </p>
        </div>
      </div>
      
      {/* How it works */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">How It Works</h2>
        <ol className="list-decimal list-inside space-y-3 text-gray-600 dark:text-gray-300">
          <li>Go to <strong>Discover Content</strong> to scrape trending Instagram posts</li>
          <li>Select a post that you'd like to transform into a viral video</li>
          <li>Customize your video generation settings</li>
          <li>Generate and preview your AI-created video</li>
          <li>Download and share your content!</li>
        </ol>
      </div>
    </div>
  );
};

export default Dashboard;
