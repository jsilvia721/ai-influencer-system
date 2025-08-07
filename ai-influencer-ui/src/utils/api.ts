import axios from 'axios';

// You'll need to replace this with your actual API Gateway URL after deployment
const API_BASE_URL = process.env.REACT_APP_API_URL || 'https://9fkbuxy8g6.execute-api.us-east-1.amazonaws.com/dev';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Character Management APIs
export const characterAPI = {
  // List all characters
  getCharacters: () => api.get('/characters'),
  
  // Create new character with training data
  createCharacter: (characterData: {
    name: string;
    description: string;
    style?: string;
    personality?: string;
    training_images: string[]; // base64 encoded images
  }) => api.post('/characters', characterData),
  
  // Get character details
  getCharacter: (characterId: string) => api.get(`/characters/${characterId}`),
  
  // Delete character
  deleteCharacter: (characterId: string) => api.delete(`/characters/${characterId}`),
  
  // Get training status
  getTrainingStatus: (characterId: string) => api.get(`/characters/${characterId}/training-status`),
};

// Content Generation APIs
export const contentAPI = {
  // Generate image using character-consistent LoRA
  generateImage: (data: {
    character_id: string;
    prompt: string;
    num_images?: number; // Number of images to generate (1-10)
  }) => api.post('/generate-content', {
    ...data,
    mode: 'image_only'
  }, {
    timeout: 300000 // 5 minutes for image generation
  }),
  
  // Generate video from image using Kling
  generateVideo: (data: {
    character_id?: string;
    image_url: string;
    prompt: string;
  }) => api.post('/generate-content', {
    ...data,
    mode: 'video_only'
  }, {
    timeout: 600000 // 10 minutes for video generation
  }),
  
  // Generate complete content (image + video pipeline)
  generateCompleteContent: (data: {
    character_id: string;
    prompt: string;
  }) => api.post('/generate-content', {
    ...data,
    mode: 'full_pipeline'
  }, {
    timeout: 900000 // 15 minutes for full pipeline
  }),
  
  // Get generation job status
  getGenerationStatus: (jobId: string) => api.get(`/content-jobs/${jobId}`),
  
  // Get content generation jobs/history
  getGenerationHistory: (characterId?: string) => api.get('/content-jobs', {
    params: characterId ? { character_id: characterId } : {}
  }),
  
  // Get all content generation jobs
  getJobs: (characterId?: string) => api.get('/content-jobs', {
    params: characterId ? { character_id: characterId } : {}
  }),
  
  // Sync all content generation jobs with Replicate
  syncWithReplicate: () => api.post('/sync-replicate'),
};

// Social Media APIs
export const socialAPI = {
  // Schedule post
  schedulePost: (data: {
    platform: string;
    content: string;
    media_url?: string;
    scheduled_time: string;
    character_id?: string;
  }) => api.post('/social/schedule', data),
  
  // Get scheduled posts
  getScheduledPosts: () => api.get('/social/scheduled'),
  
  // Post immediately
  postNow: (data: {
    platform: string;
    content: string;
    media_url?: string;
    character_id?: string;
  }) => api.post('/social/post', data),
  
  // Get posting history
  getPostHistory: () => api.get('/social/history'),
};

// Analytics APIs
export const analyticsAPI = {
  // Get usage stats
  getUsageStats: () => api.get('/analytics/usage'),
  
  // Get cost breakdown
  getCosts: () => api.get('/analytics/costs'),
  
  // Get generation metrics
  getGenerationMetrics: () => api.get('/analytics/generations'),
  
  // Get social media metrics
  getSocialMetrics: () => api.get('/analytics/social'),
};

// Settings APIs
export const settingsAPI = {
  // Get system settings
  getSettings: () => api.get('/settings'),
  
  // Update API keys (handled securely via AWS Secrets Manager)
  updateApiKeys: (keys: {
    replicate_api_key?: string;
    openai_api_key?: string;
    kling_api_key?: string;
    instagram_access_token?: string;
    twitter_api_key?: string;
  }) => api.post('/settings/api-keys', keys),
  
  // Test API connections
  testConnections: () => api.get('/settings/test-connections'),
};

// Training Image Generation APIs
export const trainingAPI = {
  // Generate training images using Flux 1.1 Pro
  generateTrainingImages: (data: {
    character_name: string;
    character_description: string;
    num_images?: number;
  }) => api.post('/generate-training-images', data),
  
  // Get job status
  getJobStatus: (jobId: string) => api.get(`/training-jobs/${jobId}`),
  
  // Get all training jobs
  getTrainingJobs: () => api.get('/training-jobs'),
  
  // Get all training images from S3
  getTrainingImages: () => api.get('/training-images'),
};

// LoRA Training APIs
export const loraAPI = {
  // Start LoRA training for a character
  startTraining: (data: {
    character_id: string;
  }) => api.post('/train-lora', data),
  
  // Get LoRA training status
  getTrainingStatus: (jobId: string) => api.get(`/lora-training-status/${jobId}`),
  
  // List all LoRA training jobs
  listTrainingJobs: (characterId?: string) => api.get('/lora-training-jobs', {
    params: characterId ? { character_id: characterId } : {}
  }),
};

export default api;
