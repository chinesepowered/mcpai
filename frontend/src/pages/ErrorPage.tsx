import React from 'react';
import { useRouteError, isRouteErrorResponse, useNavigate } from 'react-router-dom';
import { FiAlertTriangle, FiHome } from 'react-icons/fi';

/**
 * Error page component that displays when routing fails
 * Shows different messages based on error type and provides navigation back to home
 */
const ErrorPage: React.FC = () => {
  const error = useRouteError();
  const navigate = useNavigate();
  
  // Determine if this is a known route error or an unexpected error
  const isRouteError = isRouteErrorResponse(error);
  
  // Get error details
  const errorStatus = isRouteError ? error.status : 500;
  const errorMessage = isRouteError 
    ? error.statusText || 'Page not found'
    : error instanceof Error 
      ? error.message 
      : 'An unexpected error occurred';
  
  // Navigate back to home
  const handleGoHome = () => {
    navigate('/', { replace: true });
  };
  
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex flex-col items-center justify-center p-4">
      <div className="max-w-md w-full bg-white dark:bg-gray-800 rounded-lg shadow-lg p-8 text-center">
        {/* Error icon */}
        <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-red-100 dark:bg-red-900/30 mb-6">
          <FiAlertTriangle className="h-10 w-10 text-red-600 dark:text-red-400" />
        </div>
        
        {/* Error status */}
        <h1 className="text-4xl font-bold text-red-600 dark:text-red-400 mb-2">
          {errorStatus === 404 ? '404' : errorStatus}
        </h1>
        
        {/* Error heading */}
        <h2 className="text-2xl font-semibold mb-4">
          {errorStatus === 404 ? 'Page Not Found' : 'Something Went Wrong'}
        </h2>
        
        {/* Error message */}
        <p className="text-gray-600 dark:text-gray-300 mb-8">
          {errorMessage}
        </p>
        
        {/* Error details (only in development) */}
        {process.env.NODE_ENV !== 'production' && error instanceof Error && (
          <div className="mb-6 p-4 bg-gray-100 dark:bg-gray-700 rounded text-left overflow-auto max-h-48 text-sm font-mono">
            <p className="text-red-600 dark:text-red-400">{error.stack}</p>
          </div>
        )}
        
        {/* Navigation button */}
        <button
          onClick={handleGoHome}
          className="btn btn-lg btn-primary flex items-center justify-center mx-auto"
        >
          <FiHome className="mr-2" />
          Go back home
        </button>
      </div>
    </div>
  );
};

export default ErrorPage;
