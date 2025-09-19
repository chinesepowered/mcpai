import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

// https://vitejs.dev/config/
export default defineConfig(({ command, mode }) => {
  const isProduction = mode === 'production';
  
  return {
    plugins: [
      react({
        // Enable React Fast Refresh
        fastRefresh: true,
        // Include JSX runtime
        jsxRuntime: 'automatic',
        // Babel options for React
        babel: {
          plugins: [
            // Any additional Babel plugins can be added here
          ],
        },
      }),
    ],
    
    // Resolve path aliases
    resolve: {
      alias: {
        '@': resolve(__dirname, './src'),
        '@components': resolve(__dirname, './src/components'),
        '@hooks': resolve(__dirname, './src/hooks'),
        '@pages': resolve(__dirname, './src/pages'),
        '@services': resolve(__dirname, './src/services'),
        '@utils': resolve(__dirname, './src/utils'),
        '@assets': resolve(__dirname, './src/assets'),
        '@types': resolve(__dirname, './src/types'),
      },
    },
    
    // Server configuration with API proxy
    server: {
      port: 5173,
      strictPort: false,
      open: true,
      proxy: {
        // Proxy API requests to backend
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          secure: false,
          rewrite: (path) => path,
        },
      },
    },
    
    // Build optimization
    build: {
      target: 'es2015',
      outDir: 'dist',
      assetsDir: 'assets',
      minify: isProduction ? 'esbuild' : false,
      sourcemap: !isProduction,
      rollupOptions: {
        output: {
          manualChunks: {
            react: ['react', 'react-dom'],
            router: ['react-router-dom'],
            utils: ['axios', 'react-query'],
          },
        },
      },
      // Reduce chunk size warnings threshold
      chunkSizeWarningLimit: 1000,
    },
    
    // TypeScript configuration
    esbuild: {
      logOverride: { 'this-is-undefined-in-esm': 'silent' },
    },
    
    // Testing configuration with Vitest
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: ['./src/setupTests.ts'],
      css: true,
      coverage: {
        reporter: ['text', 'json', 'html'],
        exclude: [
          'node_modules/',
          'src/setupTests.ts',
        ],
      },
    },
    
    // Optimize dependencies
    optimizeDeps: {
      include: ['react', 'react-dom', 'react-router-dom'],
      exclude: [],
    },
  };
});
