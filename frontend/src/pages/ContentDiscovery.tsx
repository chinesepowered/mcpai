import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { FiSearch, FiFilter, FiRefreshCw, FiArrowUp, FiArrowDown, FiHeart, FiMessageSquare, FiVideo } from 'react-icons/fi';
import toast from 'react-hot-toast';
import { useLoading } from '../App';
import apiService from '../services/api';
import { InstagramPost, ScrapingRequest, ApiError } from '../types';

// Sort options for Instagram posts
type SortField = 'engagement_rate' | 'likes' | 'comments' | 'timestamp';
type SortDirection = 'asc' | 'desc';

interface SortOption {
  field: SortField;
  direction: SortDirection;
  label: string;
}

const sortOptions: SortOption[] = [
  { field: 'engagement_rate', direction: 'desc', label: 'Highest Engagement' },
  { field: 'engagement_rate', direction: 'asc', label: 'Lowest Engagement' },
  { field: 'likes', direction: 'desc', label: 'Most Likes' },
  { field: 'comments', direction: 'desc', label: 'Most Comments' },
  { field: 'timestamp', direction: 'desc', label: 'Newest First' },
  { field: 'timestamp', direction: 'asc', label: 'Oldest First' },
];

// Instagram Post Card Component
interface PostCardProps {
  post: InstagramPost;
  onSelect: (post: InstagramPost) => void;
}

const PostCard: React.FC<PostCardProps> = ({ post, onSelect }) => {
  // Format timestamp if available
  const formattedDate = post.timestamp 
    ? new Date(post.timestamp).toLocaleDateString(undefined, { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric' 
      })
    : 'Unknown date';

  return (
    <div className="instagram-post group" onClick={() => onSelect(post)}>
      <div className="relative">
        <img 
          src={post.image_url} 
          alt={`Instagram post by ${post.caption.substring(0, 20)}...`}
          className="instagram-post-image"
          onError={(e) => {
            (e.target as HTMLImageElement).src = 'https://via.placeholder.com/300x300?text=Image+Not+Available';
          }}
        />
        <div className="absolute inset-0 bg-black bg-opacity-50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
          <button 
            className="btn btn-md btn-primary"
            onClick={(e) => {
              e.stopPropagation();
              onSelect(post);
            }}
          >
            <FiVideo className="mr-2" />
            Generate Video
          </button>
        </div>
      </div>
      <div className="instagram-post-content">
        <p className="instagram-post-caption">{post.caption}</p>
        <div className="instagram-post-stats">
          <div className="flex items-center">
            <FiHeart className="mr-1" />
            <span>{post.likes?.toLocaleString() || 'N/A'}</span>
            <FiMessageSquare className="ml-3 mr-1" />
            <span>{post.comments?.toLocaleString() || 'N/A'}</span>
          </div>
          <div>
            {post.engagement_rate !== undefined && (
              <span className={`px-2 py-1 rounded-full text-xs ${
                post.engagement_rate > 5 ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' :
                post.engagement_rate > 2 ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' :
                'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
              }`}>
                {post.engagement_rate.toFixed(1)}% Engagement
              </span>
            )}
          </div>
        </div>
        <div className="text-xs text-gray-500 dark:text-gray-400 mt-2">
          {formattedDate}
        </div>
      </div>
    </div>
  );
};

// Empty State Component
const EmptyState: React.FC<{ onScrape: () => void }> = ({ onScrape }) => {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-8 text-center">
      <FiSearch className="mx-auto h-12 w-12 text-gray-400" />
      <h3 className="mt-2 text-lg font-medium">No Instagram posts found</h3>
      <p className="mt-1 text-gray-500 dark:text-gray-400">
        Start by scraping content from Instagram using the form above.
      </p>
      <div className="mt-6">
        <button
          onClick={onScrape}
          className="btn btn-md btn-primary"
        >
          <FiSearch className="mr-2" />
          Scrape Content
        </button>
      </div>
    </div>
  );
};

// Main Content Discovery Component
const ContentDiscovery: React.FC = () => {
  const navigate = useNavigate();
  const { setIsLoading, setLoadingMessage } = useLoading();
  
  // Form state
  const [username, setUsername] = useState<string>('austinnasso');
  const [limit, setLimit] = useState<number>(10);
  const [useBackup, setUseBackup] = useState<boolean>(false);
  
  // Content state
  const [posts, setPosts] = useState<InstagramPost[]>([]);
  const [filteredPosts, setFilteredPosts] = useState<InstagramPost[]>([]);
  const [isFirstLoad, setIsFirstLoad] = useState<boolean>(true);
  
  // Filter and sort state
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [currentSort, setCurrentSort] = useState<SortOption>(sortOptions[0]);
  const [minEngagement, setMinEngagement] = useState<number>(0);
  
  // Error state
  const [error, setError] = useState<string | null>(null);
  
  // Apply filters and sorting
  useEffect(() => {
    if (posts.length === 0) {
      setFilteredPosts([]);
      return;
    }
    
    // Filter by search term and minimum engagement
    let filtered = [...posts];
    
    if (searchTerm) {
      filtered = filtered.filter(post => 
        post.caption.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }
    
    if (minEngagement > 0) {
      filtered = filtered.filter(post => 
        (post.engagement_rate || 0) >= minEngagement
      );
    }
    
    // Sort posts
    filtered.sort((a, b) => {
      const fieldA = a[currentSort.field] || 0;
      const fieldB = b[currentSort.field] || 0;
      
      if (currentSort.direction === 'asc') {
        return fieldA > fieldB ? 1 : -1;
      } else {
        return fieldA < fieldB ? 1 : -1;
      }
    });
    
    setFilteredPosts(filtered);
  }, [posts, searchTerm, currentSort, minEngagement]);
  
  // Handle form submission
  const handleScrape = async (e?: React.FormEvent) => {
    if (e) {
      e.preventDefault();
    }
    
    if (!username) {
      toast.error('Please enter an Instagram username');
      return;
    }
    
    try {
      setError(null);
      setIsLoading(true);
      setLoadingMessage(`Scraping Instagram posts from @${username}...`);
      
      const request: ScrapingRequest = {
        username,
        limit,
        use_backup: useBackup
      };
      
      const scrapedPosts = await apiService.scrapeInstagramContent(request);
      
      setPosts(scrapedPosts);
      setIsFirstLoad(false);
      
      if (scrapedPosts.length === 0) {
        toast.info(`No posts found for @${username}`);
      } else {
        toast.success(`Successfully scraped ${scrapedPosts.length} posts from @${username}`);
      }
    } catch (error) {
      const apiError = apiService.handleApiError(error);
      setError(`Failed to scrape content: ${apiError.message}`);
      toast.error(`Failed to scrape content: ${apiError.message}`);
    } finally {
      setIsLoading(false);
    }
  };
  
  // Handle post selection for video generation
  const handleSelectPost = (post: InstagramPost) => {
    navigate(`/generate/${post.id}`, { 
      state: { 
        post,
        returnPath: '/discover'
      } 
    });
  };
  
  // Reset filters
  const handleResetFilters = () => {
    setSearchTerm('');
    setMinEngagement(0);
    setCurrentSort(sortOptions[0]);
  };
  
  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-3xl font-bold">Discover Content</h1>
        <p className="text-gray-600 dark:text-gray-300 mt-2">
          Scrape trending posts from Instagram to find viral content ideas.
        </p>
      </div>
      
      {/* Scraping form */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">Scrape Instagram Content</h2>
        <form onSubmit={handleScrape} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Username input */}
            <div className="form-group">
              <label htmlFor="username" className="form-label">Instagram Username</label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-gray-500">@</span>
                <input
                  type="text"
                  id="username"
                  className="input pl-8"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="austinnasso"
                  required
                />
              </div>
            </div>
            
            {/* Post limit selector */}
            <div className="form-group">
              <label htmlFor="limit" className="form-label">Number of Posts</label>
              <select
                id="limit"
                className="input"
                value={limit}
                onChange={(e) => setLimit(parseInt(e.target.value))}
              >
                <option value="5">5 posts</option>
                <option value="10">10 posts</option>
                <option value="20">20 posts</option>
                <option value="30">30 posts</option>
                <option value="50">50 posts</option>
              </select>
            </div>
            
            {/* Backup toggle */}
            <div className="form-group flex items-end">
              <label className="inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  className="sr-only peer"
                  checked={useBackup}
                  onChange={(e) => setUseBackup(e.target.checked)}
                />
                <div className="relative w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-brand/30 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-brand"></div>
                <span className="ms-3 text-sm font-medium text-gray-900 dark:text-gray-300">
                  Use backup method (Apify)
                </span>
              </label>
            </div>
          </div>
          
          {/* Submit button */}
          <div>
            <button
              type="submit"
              className="btn btn-md btn-primary"
            >
              <FiSearch className="mr-2" />
              Scrape Content
            </button>
          </div>
        </form>
      </div>
      
      {/* Error display */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border-l-4 border-red-500 p-4 rounded-r-lg">
          <div className="flex">
            <div className="flex-shrink-0">
              <FiRefreshCw className="h-5 w-5 text-red-500" />
            </div>
            <div className="ml-3">
              <p className="text-red-700 dark:text-red-300">{error}</p>
              <div className="mt-2">
                <button
                  type="button"
                  className="btn btn-sm bg-red-500 hover:bg-red-600 text-white"
                  onClick={() => handleScrape()}
                >
                  Try Again
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      
      {/* Content display */}
      {!isFirstLoad && (
        <div>
          {/* Filters and sorting */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 mb-6">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between space-y-4 md:space-y-0">
              {/* Search filter */}
              <div className="relative w-full md:w-64">
                <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                  <FiSearch className="w-5 h-5 text-gray-500 dark:text-gray-400" />
                </div>
                <input
                  type="text"
                  className="input pl-10"
                  placeholder="Search in captions..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
              
              <div className="flex flex-col sm:flex-row space-y-4 sm:space-y-0 sm:space-x-4">
                {/* Engagement filter */}
                <div className="w-full sm:w-48">
                  <select
                    className="input"
                    value={minEngagement}
                    onChange={(e) => setMinEngagement(parseFloat(e.target.value))}
                  >
                    <option value="0">Any engagement</option>
                    <option value="1">At least 1% engagement</option>
                    <option value="2">At least 2% engagement</option>
                    <option value="3">At least 3% engagement</option>
                    <option value="5">At least 5% engagement</option>
                  </select>
                </div>
                
                {/* Sort selector */}
                <div className="w-full sm:w-48">
                  <select
                    className="input"
                    value={`${currentSort.field}_${currentSort.direction}`}
                    onChange={(e) => {
                      const [field, direction] = e.target.value.split('_') as [SortField, SortDirection];
                      const option = sortOptions.find(opt => opt.field === field && opt.direction === direction);
                      if (option) setCurrentSort(option);
                    }}
                  >
                    {sortOptions.map((option) => (
                      <option 
                        key={`${option.field}_${option.direction}`}
                        value={`${option.field}_${option.direction}`}
                      >
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                
                {/* Reset filters button */}
                <button
                  className="btn btn-md btn-outline"
                  onClick={handleResetFilters}
                >
                  <FiFilter className="mr-2" />
                  Reset Filters
                </button>
              </div>
            </div>
            
            {/* Results count */}
            <div className="mt-4 text-sm text-gray-500 dark:text-gray-400">
              Showing {filteredPosts.length} of {posts.length} posts
              {searchTerm && ` matching "${searchTerm}"`}
              {minEngagement > 0 && ` with at least ${minEngagement}% engagement`}
            </div>
          </div>
          
          {/* Posts grid */}
          {filteredPosts.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
              {filteredPosts.map((post) => (
                <PostCard
                  key={post.id}
                  post={post}
                  onSelect={handleSelectPost}
                />
              ))}
            </div>
          ) : (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 text-center">
              <FiFilter className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-lg font-medium">No posts match your filters</h3>
              <p className="mt-1 text-gray-500 dark:text-gray-400">
                Try adjusting your search terms or filters.
              </p>
              <div className="mt-6">
                <button
                  onClick={handleResetFilters}
                  className="btn btn-md btn-primary"
                >
                  <FiFilter className="mr-2" />
                  Reset Filters
                </button>
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Empty state */}
      {isFirstLoad && (
        <EmptyState onScrape={handleScrape} />
      )}
    </div>
  );
};

export default ContentDiscovery;
