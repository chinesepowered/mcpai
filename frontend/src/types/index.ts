/**
 * Type definitions for the Viral Marketing Agent application
 */

// Instagram Post Types
export interface InstagramPost {
  id: string;
  caption: string;
  image_url: string;
  video_url?: string;
  likes?: number;
  comments?: number;
  engagement_rate?: number;
  timestamp?: string;
}

export interface ScrapingRequest {
  username: string;
  limit: number;
  use_backup: boolean;
}

// Video Generation Types
export interface VideoGenerationRequest {
  post_id: string;
  caption: string;
  image_url: string;
  style?: string;
  duration?: number;
  voice_type?: string;
  include_captions?: boolean;
  music_style?: string;
}

export interface VideoGenerationResponse {
  video_id: string;
  status: string;
  video_url?: string;
  thumbnail_url?: string;
  duration?: number;
  message?: string;
  created_at?: string;
}

export interface VideoStatus {
  video_id: string;
  status: VideoProcessingStatus;
  progress?: number;
  video_url?: string;
  thumbnail_url?: string;
  duration?: number;
  error?: string;
}

export type VideoProcessingStatus = 'processing' | 'completed' | 'failed';

export interface CompletedVideo {
  video_id: string;
  video_url: string;
  thumbnail_url?: string;
  duration?: number;
  status: 'completed';
}

// API Response Types
export interface ApiResponse<T> {
  data: T;
  status: number;
  message?: string;
}

export interface ApiError {
  status: number;
  message: string;
  detail?: any;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// UI State Types
export interface ContentDiscoveryState {
  posts: InstagramPost[];
  isLoading: boolean;
  error: ApiError | null;
  selectedUsername: string;
  useBackup: boolean;
  limit: number;
}

export interface VideoGenerationState {
  selectedPost: InstagramPost | null;
  generationOptions: Omit<VideoGenerationRequest, 'post_id' | 'caption' | 'image_url'>;
  isGenerating: boolean;
  generationError: ApiError | null;
  generatedVideoId?: string;
}

export interface VideoPreviewState {
  videoId: string;
  videoStatus: VideoStatus | null;
  isLoading: boolean;
  error: ApiError | null;
  isDownloading: boolean;
}

export interface AppTheme {
  mode: 'light' | 'dark';
  primaryColor: string;
}

export interface UserPreferences {
  theme: AppTheme;
  defaultUsername: string;
  defaultVideoStyle: string;
  defaultVideoDuration: number;
  defaultVoiceType: string;
  showCaptions: boolean;
}

// Error Types
export interface ValidationError {
  field: string;
  message: string;
}

export interface FormErrors {
  [key: string]: string;
}

export enum ErrorType {
  API_ERROR = 'API_ERROR',
  NETWORK_ERROR = 'NETWORK_ERROR',
  VALIDATION_ERROR = 'VALIDATION_ERROR',
  AUTHENTICATION_ERROR = 'AUTHENTICATION_ERROR',
  UNKNOWN_ERROR = 'UNKNOWN_ERROR'
}

export interface AppError {
  type: ErrorType;
  message: string;
  originalError?: any;
  statusCode?: number;
  validationErrors?: ValidationError[];
}

// Video Style Options
export enum VideoStyle {
  COMEDY = 'comedy',
  DRAMATIC = 'dramatic',
  INFORMATIVE = 'informative',
  INSPIRATIONAL = 'inspirational',
  SATIRICAL = 'satirical'
}

export enum VoiceType {
  MALE = 'male',
  FEMALE = 'female',
  ROBOTIC = 'robotic',
  NARRATOR = 'narrator'
}

export enum MusicStyle {
  UPBEAT = 'upbeat',
  DRAMATIC = 'dramatic',
  EMOTIONAL = 'emotional',
  FUNNY = 'funny',
  NONE = 'none'
}

// Utility Types
export type LoadingState = 'idle' | 'loading' | 'success' | 'error';

export interface Pagination {
  page: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
}

export type SortDirection = 'asc' | 'desc';

export interface SortOptions {
  field: string;
  direction: SortDirection;
}

export interface FilterOptions {
  [key: string]: any;
}
