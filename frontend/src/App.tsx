import React, { createContext, useContext, useState, useEffect } from 'react';
import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { ErrorBoundary } from 'react-error-boundary';
import { FiVideo, FiSearch, FiHome, FiMoon, FiSun, FiGithub, FiZap } from 'react-icons/fi';
import toast from 'react-hot-toast';
import { apiService } from './services/api';

// Theme context
type Theme = 'light' | 'dark';
interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType>({
  theme: 'light',
  toggleTheme: () => {},
});

// Loading context
interface LoadingContextType {
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  loadingMessage: string;
  setLoadingMessage: (message: string) => void;
}

const LoadingContext = createContext<LoadingContextType>({
  isLoading: false,
  setIsLoading: () => {},
  loadingMessage: '',
  setLoadingMessage: () => {},
});

// Custom hooks
export const useTheme = () => useContext(ThemeContext);
export const useLoading = () => useContext(LoadingContext);

// Error fallback component
const ErrorFallback = ({ error, resetErrorBoundary }: { error: Error; resetErrorBoundary: () => void }) => {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen p-6 bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200">
      <div className="max-w-md w-full bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 text-center">
        <h2 className="text-2xl font-bold mb-4">Something went wrong</h2>
        <div className="mb-4 p-4 bg-red-100 dark:bg-red-900/30 rounded text-sm font-mono text-left overflow-auto max-h-48">
          {error.message}
        </div>
        <button
          className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
          onClick={resetErrorBoundary}
        >
          Try again
        </button>
      </div>
    </div>
  );
};

// Loading overlay component
const LoadingOverlay = ({ message }: { message: string }) => {
  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 max-w-sm w-full">
        <div className="flex flex-col items-center justify-center space-y-4">
          <div className="spinner spinner-lg border-brand"></div>
          <p className="text-center font-medium">{message || 'Loading...'}</p>
        </div>
      </div>
    </div>
  );
};

// Navigation item component
interface NavItemProps {
  to: string;
  icon: React.ReactNode;
  label: string;
}

const NavItem = ({ to, icon, label }: NavItemProps) => {
  const location = useLocation();
  const isActive = location.pathname === to || 
    (to !== '/' && location.pathname.startsWith(to));
  
  return (
    <NavLink
      to={to}
      className={({ isActive }) => 
        `flex items-center px-4 py-2 rounded-md transition-colors ${
          isActive 
            ? 'bg-brand/10 text-brand font-medium' 
            : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'
        }`
      }
    >
      <span className="mr-3">{icon}</span>
      <span>{label}</span>
    </NavLink>
  );
};

// Main App component
const App: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  
  // Theme state
  const [theme, setTheme] = useState<Theme>(() => {
    // Check for saved theme preference or system preference
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark' || savedTheme === 'light') {
      return savedTheme;
    }
    
    // Check system preference
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    
    return 'light';
  });
  
  // Loading state
  const [isLoading, setIsLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('');
  
  // API health check
  const [apiHealthy, setApiHealthy] = useState(true);
  
  // Toggle theme function
  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
    localStorage.setItem('theme', newTheme);
  };
  
  // Apply theme to document
  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);
  
  // Check API health on mount
  useEffect(() => {
    const checkApiHealth = async () => {
      try {
        const isHealthy = await apiService.checkHealth();
        setApiHealthy(isHealthy);
        
        if (!isHealthy) {
          toast.error('API is not responding. Some features may not work.');
        }
      } catch (error) {
        setApiHealthy(false);
        toast.error('Could not connect to API. Please check your connection.');
      }
    };
    
    checkApiHealth();
    
    // Set up periodic health check
    const interval = setInterval(checkApiHealth, 60000); // Check every minute
    
    return () => {
      clearInterval(interval);
    };
  }, []);
  
  // Handle error boundary reset
  const handleErrorReset = () => {
    navigate(location.pathname, { replace: true });
  };
  
  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      <LoadingContext.Provider value={{ isLoading, setIsLoading, loadingMessage, setLoadingMessage }}>
        <ErrorBoundary FallbackComponent={ErrorFallback} onReset={handleErrorReset}>
          <div className="min-h-screen bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 flex flex-col">
            {/* Header */}
            <header className="bg-white dark:bg-gray-800 shadow-sm">
              <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex justify-between h-16">
                  {/* Logo and title */}
                  <div className="flex items-center">
                    <NavLink to="/" className="flex items-center">
                      <FiVideo className="h-8 w-8 text-brand" />
                      <span className="ml-2 text-xl font-bold">Viral Marketing Agent</span>
                    </NavLink>
                  </div>
                  
                  {/* Right side actions */}
                  <div className="flex items-center space-x-4">
                    {/* API health indicator */}
                    <div className="hidden sm:flex items-center">
                      <div className={`w-2 h-2 rounded-full ${apiHealthy ? 'bg-green-500' : 'bg-red-500'}`}></div>
                      <span className="ml-2 text-sm text-gray-500 dark:text-gray-400">
                        API {apiHealthy ? 'Online' : 'Offline'}
                      </span>
                    </div>
                    
                    {/* Theme toggle */}
                    <button
                      onClick={toggleTheme}
                      className="p-2 rounded-md text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand"
                      aria-label="Toggle theme"
                    >
                      {theme === 'light' ? <FiMoon size={20} /> : <FiSun size={20} />}
                    </button>
                    
                    {/* GitHub link */}
                    <a
                      href="https://github.com/your-org/viral-marketing-agent"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-2 rounded-md text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand"
                      aria-label="GitHub repository"
                    >
                      <FiGithub size={20} />
                    </a>
                  </div>
                </div>
              </div>
            </header>
            
            {/* Main content area with navigation sidebar */}
            <div className="flex-1 flex">
              {/* Navigation sidebar */}
              <nav className="w-64 bg-white dark:bg-gray-800 shadow-sm hidden md:block p-4">
                <div className="space-y-2">
                  <NavItem to="/" icon={<FiHome size={18} />} label="Dashboard" />
                  <NavItem to="/discover" icon={<FiSearch size={18} />} label="Discover Content" />
                  <NavItem to="/demo" icon={<FiZap size={18} />} label="Demo Videos" />
                </div>
              </nav>
              
              {/* Mobile navigation (bottom bar) */}
              <div className="fixed bottom-0 left-0 right-0 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 md:hidden z-10">
                <div className="flex justify-around">
                  <NavLink
                    to="/"
                    className={({ isActive }) => 
                      `flex flex-col items-center py-3 px-6 ${isActive ? 'text-brand' : 'text-gray-600 dark:text-gray-400'}`
                    }
                  >
                    <FiHome size={20} />
                    <span className="text-xs mt-1">Home</span>
                  </NavLink>
                  
                  <NavLink
                    to="/discover"
                    className={({ isActive }) => 
                      `flex flex-col items-center py-3 px-6 ${isActive ? 'text-brand' : 'text-gray-600 dark:text-gray-400'}`
                    }
                  >
                    <FiSearch size={20} />
                    <span className="text-xs mt-1">Discover</span>
                  </NavLink>
                  
                  <NavLink
                    to="/demo"
                    className={({ isActive }) => 
                      `flex flex-col items-center py-3 px-6 ${isActive ? 'text-brand' : 'text-gray-600 dark:text-gray-400'}`
                    }
                  >
                    <FiZap size={20} />
                    <span className="text-xs mt-1">Demo</span>
                  </NavLink>
                </div>
              </div>
              
              {/* Main content */}
              <main className="flex-1 overflow-auto p-4 sm:p-6 pb-20 md:pb-6">
                <div className="max-w-7xl mx-auto">
                  <Outlet />
                </div>
              </main>
            </div>
            
            {/* Loading overlay */}
            {isLoading && <LoadingOverlay message={loadingMessage} />}
          </div>
        </ErrorBoundary>
      </LoadingContext.Provider>
    </ThemeContext.Provider>
  );
};

export default App;
