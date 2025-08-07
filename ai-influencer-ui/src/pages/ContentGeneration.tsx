import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  CardActions,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  LinearProgress,
  Chip,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Tabs,
  Tab,
  Divider,
  IconButton,
  Tooltip,
  CircularProgress,
  Skeleton,
  Snackbar,
} from '@mui/material';
import {
  Image as ImageIcon,
  VideoLibrary as VideoIcon,
  AutoAwesome as GenerateIcon,
  Refresh as RefreshIcon,
  Download as DownloadIcon,
  Share as ShareIcon,
  Preview as PreviewIcon,
  History as HistoryIcon,
  Sync as SyncIcon,
  Info as InfoIcon,
  Launch as LaunchIcon,
  AccessTime as TimeIcon,
  Speed as SpeedIcon,
  Code as CodeIcon,
} from '@mui/icons-material';
import { characterAPI, contentAPI } from '../utils/api';

interface Character {
  id: string;
  name: string;
  description: string;
  training_status: string;
  model_url?: string;
}

interface GenerationJob {
  id: string;
  type: 'image' | 'video';
  prompt: string;
  character_id: string;
  character_name: string;
  status: string; // Allow any status string from API
  created_at: string;
  result_url?: string;
  progress?: number;
  generation_id?: string; // Add generation_id to track API job
  error?: string; // Error message from Replicate
  error_category?: string; // Error category from unified schema
  error_component?: string; // Error component from unified schema
  replicate_prediction_id?: string; // Replicate prediction ID
  replicate_status?: string; // Raw Replicate status
  // Multi-image generation statistics
  num_images_requested?: number; // Number of images requested
  num_images_generated?: number; // Number of images successfully generated
  max_attempts?: number; // Maximum attempts allowed
  current_attempt?: number; // Current attempt number
  generated_images?: string[]; // Array of generated image URLs
  success_rate?: number; // Success rate percentage
  // Full Replicate data
  replicate_input?: any; // Raw input parameters from Replicate
  replicate_output?: any; // Raw output from Replicate
  replicate_logs?: string; // Full execution logs
  replicate_metrics?: any; // Performance metrics
  replicate_urls?: any; // Replicate URLs (web, stream, etc.)
  replicate_version?: string; // Model version
  completed_at?: string; // Job completion time
  started_at?: string; // Job start time
}

const ContentGeneration: React.FC = () => {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [selectedCharacter, setSelectedCharacter] = useState<string>('');
  const [contentType, setContentType] = useState<'image' | 'video'>('image');
  const [prompt, setPrompt] = useState('');
  const [generating, setGenerating] = useState(false);
  const [generationJobs, setGenerationJobs] = useState<GenerationJob[]>([]);
  const [previewDialog, setPreviewDialog] = useState(false);
  const [previewContent, setPreviewContent] = useState<{ url: string; type: 'image' | 'video' } | null>(null);
  const [currentTab, setCurrentTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedImageUrl, setSelectedImageUrl] = useState<string>('');
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string>('');
  const [showSyncSnackbar, setShowSyncSnackbar] = useState(false);
  const [nextPollIn, setNextPollIn] = useState(10);
  
  // Job details dialog
  const [jobDetailsDialog, setJobDetailsDialog] = useState(false);
  const [selectedJobDetails, setSelectedJobDetails] = useState<GenerationJob | null>(null);

  // Advanced options (currently not used in API calls but kept for UI)
  const [aspectRatio, setAspectRatio] = useState('1:1');
  const [duration, setDuration] = useState(5);
  const [numImages, setNumImages] = useState(1);  // Number of images to generate

  const fetchCharacters = useCallback(async () => {
    try {
      const response = await characterAPI.getCharacters();
      const charactersData = response.data.data || response.data || [];
      // Only show completed characters
      const completedCharacters = charactersData.filter(
        (char: Character) => char.training_status === 'completed'
      );
      setCharacters(completedCharacters);
      if (completedCharacters.length > 0 && !selectedCharacter) {
        setSelectedCharacter(completedCharacters[0].id);
      }
    } catch (err) {
      console.error('Failed to fetch characters:', err);
      setError('Failed to load characters. Please ensure you have trained characters available.');
    } finally {
      setLoading(false);
    }
  }, [selectedCharacter]);

  const loadGenerationJobs = useCallback(async () => {
    try {
      const response = await contentAPI.getJobs();
      const jobs = response.data.jobs || [];
      // Transform backend jobs to frontend format
      const transformedJobs = jobs.map((job: any) => {
        // Handle different job types and their corresponding URLs
        let resultUrl = job.output_url || job.image_url || job.video_url;
        let jobType = job.type;
        
        // For complete jobs, we prefer the video if available, otherwise the image
        if (job.type === 'complete') {
          resultUrl = job.video_url || job.image_url || job.output_url;
          jobType = job.video_url ? 'video' : 'image'; // Convert complete type to video or image for UI
        }
        
        return {
          id: job.job_id,
          type: jobType === 'complete' ? (job.video_url ? 'video' : 'image') : jobType,
          prompt: job.prompt,
          character_id: job.character_id,
          character_name: job.character_name || 'Unknown',
          status: job.status,
          created_at: job.created_at,
          result_url: resultUrl,
          generation_id: job.job_id,
          error: job.error || job.error_message, // Include error message from backend
          error_category: job.error_category,
          error_component: job.error_component,
          replicate_prediction_id: job.replicate_prediction_id,
          replicate_status: job.replicate_status,
          // Multi-image generation statistics
          num_images_requested: job.num_images_requested,
          num_images_generated: job.num_images_generated,
          max_attempts: job.max_attempts,
          current_attempt: job.current_attempt,
          generated_images: job.generated_images,
          success_rate: job.success_rate
        };
      });
      setGenerationJobs(transformedJobs);
    } catch (err) {
      console.error('Error loading generation jobs:', err);
      // Fallback to localStorage for backward compatibility
      const savedJobs = localStorage.getItem('generationJobs');
      if (savedJobs) {
        try {
          setGenerationJobs(JSON.parse(savedJobs));
        } catch (parseErr) {
          console.error('Error parsing localStorage jobs:', parseErr);
        }
      }
    }
  }, []);

  const updateJobStatuses = useCallback(async () => {
    // Instead of checking individual jobs, reload all jobs from backend
    // This ensures we always have the latest status from webhooks
    try {
      const response = await contentAPI.getJobs();
      const jobs = response.data.jobs || [];
      // Transform backend jobs to frontend format
      const transformedJobs = jobs.map((job: any) => {
        // Handle different job types and their corresponding URLs
        let resultUrl = job.output_url || job.image_url || job.video_url;
        let jobType = job.type;
        
        // For complete jobs, we prefer the video if available, otherwise the image
        if (job.type === 'complete') {
          resultUrl = job.video_url || job.image_url || job.output_url;
          jobType = job.video_url ? 'video' : 'image'; // Convert complete type to video or image for UI
        }
        
        return {
          id: job.job_id,
          type: jobType === 'complete' ? (job.video_url ? 'video' : 'image') : jobType,
          prompt: job.prompt,
          character_id: job.character_id,
          character_name: job.character_name || 'Unknown',
          status: job.status,
          created_at: job.created_at,
          result_url: resultUrl,
          generation_id: job.job_id,
          error: job.error || job.error_message, // Include error message from backend
          error_category: job.error_category,
          error_component: job.error_component,
          replicate_prediction_id: job.replicate_prediction_id, // Include replicate prediction ID
          replicate_status: job.replicate_status
        };
      });
      setGenerationJobs(transformedJobs);
      
      // Still save to localStorage as backup
      localStorage.setItem('generationJobs', JSON.stringify(transformedJobs));
    } catch (error) {
      console.error('Failed to reload job statuses:', error);
    }
  }, []);

  useEffect(() => {
    fetchCharacters();
    loadGenerationJobs();
  }, [fetchCharacters, loadGenerationJobs]);

  // Poll for job updates every 10 seconds with countdown - only when there are processing jobs
  useEffect(() => {
    // Consider jobs stale if they've been processing for more than 10 minutes
    const STALE_JOB_THRESHOLD = 10 * 60 * 1000; // 10 minutes in milliseconds
    const now = new Date().getTime();
    
    const hasActiveProcessingJobs = generationJobs.some(job => {
      if (job.status !== 'processing') return false;
      
      // Check if job is stale (been processing too long)
      const jobStartTime = new Date(job.created_at).getTime();
      const isStale = (now - jobStartTime) > STALE_JOB_THRESHOLD;
      
      return !isStale; // Only count as active if not stale
    });
    
    // Don't poll if there are no active processing jobs
    if (!hasActiveProcessingJobs) {
      setNextPollIn(0); // Reset countdown when not polling
      return;
    }
    
    // Immediately set countdown to 10 when polling starts
    setNextPollIn(10);
    
    const interval = setInterval(() => {
      updateJobStatuses();
      setNextPollIn(10); // Reset countdown after each poll
    }, 10000);
    
    const countdownInterval = setInterval(() => {
      setNextPollIn((prev) => Math.max(0, prev - 1));
    }, 1000);
    
    return () => {
      clearInterval(interval);
      clearInterval(countdownInterval);
    };
  }, [generationJobs, updateJobStatuses]);

  const handleGenerate = async () => {
    if (!selectedCharacter || !prompt.trim()) {
      setError('Please select a character and enter a prompt.');
      return;
    }

    if (contentType === 'video' && !selectedImageUrl) {
      setError('Please select an input image for video generation.');
      return;
    }

    const selectedChar = characters.find(char => char.id === selectedCharacter);
    if (!selectedChar) {
      setError('Selected character not found.');
      return;
    }

    try {
      setGenerating(true);
      setError(null);

      // Make actual API call
      let apiResponse;
      if (contentType === 'image') {
        apiResponse = await contentAPI.generateImage({
          character_id: selectedCharacter,
          prompt: prompt.trim(),
          num_images: numImages  // Pass the number of images to generate
        });
      } else {
        // For video generation, use the selected image URL
        apiResponse = await contentAPI.generateVideo({
          character_id: selectedCharacter,
          prompt: prompt.trim(),
          image_url: selectedImageUrl
        });
      }
      
      // Success - job is now in the backend and kicked off in Replicate
      if (apiResponse.data && apiResponse.data.job_id) {
        console.log(`${contentType} generation started successfully with job ID: ${apiResponse.data.job_id}`);
        
        // Don't clear the form immediately - let user generate more content with same prompt if desired
        // Only clear video-specific fields
        if (contentType === 'video') {
          setSelectedImageUrl(''); // Reset selected image
        }
        
        // Switch to history tab immediately to show the new processing job
        setCurrentTab(1);
        
        // Refresh jobs list to show the new job
        await loadGenerationJobs();
      }
      
    } catch (err: any) {
      console.error('Generation failed:', err);
      
      // Handle different types of errors
      let errorMessage = 'Content generation failed. Please try again.';
      
      if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
        // This is a timeout error - the job might still be running
        errorMessage = `${contentType === 'video' ? 'Video' : 'Image'} generation is taking longer than expected. The job might still be processing in the background. Check the history tab in a few minutes to see if it completed.`;
      } else if (err.response?.data?.error) {
        errorMessage = err.response.data.error;
      }
      
      setError(errorMessage);
    } finally {
      setGenerating(false);
    }
  };

  const handleSync = async () => {
    try {
      setSyncing(true);
      setError(null);
      
      // Call the sync API
      const response = await contentAPI.syncWithReplicate();
      
      // Wait a moment for sync to process
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Refresh the jobs list to show updated data
      await loadGenerationJobs();
      
      // Show success message based on sync results
      const syncData = response.data;
      let message = 'Sync completed successfully!';
      if (syncData && syncData.synced_count !== undefined) {
        if (syncData.synced_count > 0) {
          message = `Successfully updated ${syncData.synced_count} job${syncData.synced_count !== 1 ? 's' : ''} from Replicate`;
        } else {
          message = 'All jobs are already up to date';
        }
      }
      
      setSyncMessage(message);
      setShowSyncSnackbar(true);
      console.log(message);
      
    } catch (err: any) {
      console.error('Sync failed:', err);
      let errorMessage = 'Failed to sync with Replicate. Please try again.';
      if (err.response?.data?.error) {
        errorMessage = err.response.data.error;
      }
      setSyncMessage(errorMessage);
      setShowSyncSnackbar(true);
    } finally {
      setSyncing(false);
    }
  };

  const handlePreview = (job: GenerationJob) => {
    if (job.result_url) {
      setPreviewContent({ url: job.result_url, type: job.type });
      setPreviewDialog(true);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'success';
      case 'processing': return 'warning';
      case 'failed': return 'error';
      default: return 'default';
    }
  };

  if (loading) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>
          Content Generation
        </Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 3 }}>
          <Skeleton variant="rectangular" height={300} />
          <Skeleton variant="rectangular" height={300} />
        </Box>
      </Box>
    );
  }

  if (characters.length === 0) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>
          Content Generation
        </Typography>
        <Alert severity="warning" sx={{ mb: 3 }}>
          No trained characters available. Please complete character training first.
        </Alert>
        <Button 
          variant="contained" 
          onClick={() => window.location.href = '/characters'}
        >
          Go to Character Management
        </Button>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Content Generation</Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title="Sync job statuses with Replicate">
            <Button
              startIcon={syncing ? <CircularProgress size={16} /> : <SyncIcon />}
              onClick={handleSync}
              variant="outlined"
              size="small"
              disabled={syncing}
            >
              {syncing ? 'Syncing...' : 'Sync'}
            </Button>
          </Tooltip>
          <Button
            startIcon={<RefreshIcon />}
            onClick={() => {
              fetchCharacters();
              loadGenerationJobs();
            }}
            variant="outlined"
            size="small"
          >
            Refresh
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <Paper sx={{ mb: 3 }}>
        <Tabs value={currentTab} onChange={(e, v) => setCurrentTab(v)}>
          <Tab icon={<GenerateIcon />} label="Generate Content" />
          <Tab icon={<HistoryIcon />} label={`Generation History (${generationJobs?.length || 0})`} />
        </Tabs>
      </Paper>

      {/* Generate Content Tab */}
      {currentTab === 0 && (
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '2fr 1fr' }, gap: 3 }}>
          <Box>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Create AI Content
                </Typography>
                
                <FormControl fullWidth sx={{ mb: 3 }}>
                  <InputLabel error={!selectedCharacter}>Select Character *</InputLabel>
                  <Select
                    value={selectedCharacter}
                    onChange={(e) => setSelectedCharacter(e.target.value)}
                    label="Select Character *"
                    error={!selectedCharacter}
                  >
                    {characters.map((character) => (
                      <MenuItem key={character.id} value={character.id}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          {character.name}
                          <Chip size="small" label="Trained" color="success" />
                        </Box>
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
                  <Button
                    variant={contentType === 'image' ? 'contained' : 'outlined'}
                    startIcon={<ImageIcon />}
                    onClick={() => setContentType('image')}
                  >
                    Image
                  </Button>
                  <Button
                    variant={contentType === 'video' ? 'contained' : 'outlined'}
                    startIcon={<VideoIcon />}
                    onClick={() => setContentType('video')}
                  >
                    Video
                  </Button>
                </Box>

                {contentType === 'video' && (
                  <>
                    <FormControl fullWidth sx={{ mb: 3 }}>
                      <InputLabel error={contentType === 'video' && !selectedImageUrl}>Select Input Image *</InputLabel>
                      <Select
                        value={selectedImageUrl}
                        onChange={(e) => setSelectedImageUrl(e.target.value)}
                        label="Select Input Image *"
                        error={contentType === 'video' && !selectedImageUrl}
                      >
                        {generationJobs
                          .filter(job => job.type === 'image' && job.status === 'completed' && job.result_url)
                          .map((imageJob) => (
                            <MenuItem key={imageJob.id} value={imageJob.result_url}>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
                                <img 
                                  src={imageJob.result_url} 
                                  alt={`${imageJob.character_name} - ${imageJob.prompt.substring(0, 30)}...`}
                                  style={{ 
                                    width: 40, 
                                    height: 40, 
                                    objectFit: 'cover', 
                                    borderRadius: 4 
                                  }}
                                />
                                <Box sx={{ flex: 1, minWidth: 0 }}>
                                  <Typography variant="body2" noWrap>
                                    {imageJob.character_name}
                                  </Typography>
                                  <Typography variant="caption" color="text.secondary" noWrap>
                                    {imageJob.prompt && imageJob.prompt.length > 40 ? `${imageJob.prompt.substring(0, 40)}...` : (imageJob.prompt || 'No prompt')}
                                  </Typography>
                                </Box>
                              </Box>
                            </MenuItem>
                          ))}
                      </Select>
                      {generationJobs.filter(job => job.type === 'image' && job.status === 'completed' && job.result_url).length === 0 && (
                        <Alert severity="info" sx={{ mt: 1 }}>
                          No completed images available. Generate some images first to use for video creation.
                        </Alert>
                      )}
                    </FormControl>
                  </>
                )}

                <TextField
                  fullWidth
                  multiline
                  rows={4}
                  label="Content Description *"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder={`Enter a detailed prompt for ${contentType} generation...`}
                  required
                  error={!prompt.trim()}
                  helperText={!prompt.trim() ? 'Please enter a description for your content' : 'Be specific about what you want to create'}
                  sx={{ mb: 3 }}
                />

                <Divider sx={{ my: 2 }} />
                
                <Typography variant="subtitle2" gutterBottom>
                  Advanced Options
                </Typography>
                
                <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2 }}>
                  <FormControl fullWidth>
                    <InputLabel>Aspect Ratio</InputLabel>
                    <Select
                      value={aspectRatio}
                      onChange={(e) => setAspectRatio(e.target.value)}
                      label="Aspect Ratio"
                    >
                      <MenuItem value="1:1">Square (1:1)</MenuItem>
                      <MenuItem value="16:9">Landscape (16:9)</MenuItem>
                      <MenuItem value="9:16">Portrait (9:16)</MenuItem>
                      <MenuItem value="4:3">Classic (4:3)</MenuItem>
                    </Select>
                  </FormControl>
                  
                  {contentType === 'video' ? (
                    <TextField
                      fullWidth
                      type="number"
                      label="Duration (seconds)"
                      value={duration}
                      onChange={(e) => setDuration(Number(e.target.value))}
                      inputProps={{ min: 1, max: 30 }}
                    />
                  ) : (
                    <TextField
                      fullWidth
                      type="number"
                      label="Number of Images"
                      value={numImages}
                      onChange={(e) => setNumImages(Number(e.target.value))}
                      inputProps={{ min: 1, max: 10 }}
                      helperText="Generate up to 10 images with smart retry logic"
                    />
                  )}
                </Box>
              </CardContent>
              
              <CardActions>
                <Button
                  variant="contained"
                  size="large"
                  startIcon={generating ? <CircularProgress size={20} /> : <GenerateIcon />}
                  onClick={handleGenerate}
                  disabled={generating || !selectedCharacter || !prompt.trim()}
                  fullWidth
                >
                  {generating ? `Generating ${contentType}...` : `Generate ${contentType === 'image' ? 'Image' : 'Video'}`}
                </Button>
              </CardActions>
            </Card>
          </Box>
          
          <Box>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Tips for Better Results
                </Typography>
                <Typography variant="body2" paragraph>
                  • Be specific about pose, expression, and setting
                </Typography>
                <Typography variant="body2" paragraph>
                  • Include lighting and mood descriptions
                </Typography>
                <Typography variant="body2" paragraph>
                  • Mention style keywords (photorealistic, cinematic, etc.)
                </Typography>
                <Typography variant="body2" paragraph>
                  • For videos, describe the action or movement
                </Typography>
                
                <Divider sx={{ my: 2 }} />
                
                <Typography variant="subtitle2" gutterBottom>
                  Example Prompts:
                </Typography>
                <Typography variant="caption" display="block" sx={{ mb: 1 }}>
                  "Portrait shot, confident smile, natural lighting, modern office background"
                </Typography>
                <Typography variant="caption" display="block">
                  "Walking in a park, casual outfit, golden hour lighting, cinematic style"
                </Typography>
              </CardContent>
            </Card>
          </Box>
        </Box>
      )}

      {/* History Tab */}
      {currentTab === 1 && (
        <Box>
          {/* Polling Status Indicator */}
          {(() => {
            const hasProcessingJobs = generationJobs.some(job => {
              if (job.status !== 'processing') return false;
              
              // Check if job is stale (same logic as polling)
              const STALE_JOB_THRESHOLD = 10 * 60 * 1000; // 10 minutes
              const now = new Date().getTime();
              const jobStartTime = new Date(job.created_at).getTime();
              const isStale = (now - jobStartTime) > STALE_JOB_THRESHOLD;
              
              return !isStale; // Only count as active if not stale
            });
            
            if (generationJobs.length === 0) {
              // No jobs at all
              return null; // Don't show banner when no jobs exist
            } else if (hasProcessingJobs) {
              // Active polling mode
              return (
                <Alert 
                  severity="info" 
                  sx={{ mb: 2, display: 'flex', alignItems: 'center' }}
                  icon={<TimeIcon />}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="body2">
                      Auto-refresh in {nextPollIn}s
                    </Typography>
                    <Chip 
                      size="small" 
                      label="Live Updates" 
                      color="primary" 
                      variant="outlined"
                    />
                  </Box>
                </Alert>
              );
            } else {
              // Paused mode (no active processing jobs)
              return (
                <Alert 
                  severity="success" 
                  sx={{ mb: 2, display: 'flex', alignItems: 'center' }}
                  icon={<SpeedIcon />}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="body2">
                      Auto-refresh paused - no active jobs
                    </Typography>
                    <Chip 
                      size="small" 
                      label="Optimized" 
                      color="success" 
                      variant="outlined"
                    />
                  </Box>
                </Alert>
              );
            }
          })()} 
          
          {generationJobs.length === 0 ? (
            <Card>
              <CardContent sx={{ textAlign: 'center', py: 6 }}>
                <GenerateIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
                <Typography variant="h6" color="text.secondary" gutterBottom>
                  No content generated yet
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Switch to the Generate tab to create your first AI content
                </Typography>
              </CardContent>
            </Card>
          ) : (
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' }, gap: 3 }}>
              {generationJobs.map((job) => (
                <Card key={job.id}>
                    <CardContent>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                        <Chip
                          icon={job.type === 'image' ? <ImageIcon /> : <VideoIcon />}
                          label={job.type}
                          size="small"
                          variant="outlined"
                        />
                        <Chip
                          label={job.status}
                          color={getStatusColor(job.status) as any}
                          size="small"
                        />
                      </Box>
                      
                      <Typography variant="subtitle2" gutterBottom>
                        {job.character_name}
                      </Typography>
                      
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        {job.prompt && job.prompt.length > 80 ? `${job.prompt.substring(0, 80)}...` : (job.prompt || 'No prompt')}
                      </Typography>
                      
                      {job.status === 'processing' && (
                        <Box sx={{ mb: 2 }}>
                          <LinearProgress 
                            variant="determinate" 
                            value={job.progress || 0}
                            sx={{ mb: 1 }}
                          />
                          <Typography variant="caption" color="text.secondary">
                            {Math.round(job.progress || 0)}% complete
                          </Typography>
                          {/* Check if job is stale */}
                          {(() => {
                            const STALE_JOB_THRESHOLD = 10 * 60 * 1000; // 10 minutes
                            const now = new Date().getTime();
                            const jobStartTime = new Date(job.created_at).getTime();
                            const isStale = (now - jobStartTime) > STALE_JOB_THRESHOLD;
                            
                            if (isStale) {
                              return (
                                <Alert severity="warning" sx={{ mt: 1 }}>
                                  <Typography variant="caption">
                                    <strong>Stale Job:</strong> This job has been processing for over 10 minutes. 
                                    Consider using the Sync button to check for updates.
                                  </Typography>
                                </Alert>
                              );
                            }
                            return null;
                          })()} 
                        </Box>
                      )}
                      
                      {job.status === 'failed' && job.error && (
                        <Alert severity="error" sx={{ mb: 2 }}>
                          <Typography variant="caption">
                            <strong>Error:</strong> {job.error}
                          </Typography>
                          {job.error_category && (
                            <Typography variant="caption" display="block" sx={{ mt: 0.5, opacity: 0.8 }}>
                              Category: {job.error_category}
                              {job.error_component && ` (${job.error_component})`}
                            </Typography>
                          )}
                          {job.replicate_prediction_id && (
                            <Typography variant="caption" display="block" sx={{ mt: 0.5, opacity: 0.7 }}>
                              Replicate ID: {job.replicate_prediction_id.substring(0, 8)}...
                            </Typography>
                          )}
                        </Alert>
                      )}
                      
                      <Typography variant="caption" color="text.secondary" display="block">
                        {new Date(job.created_at).toLocaleString()}
                      </Typography>
                    </CardContent>
                    
                    <CardActions>
                      {job.status === 'completed' && job.result_url && (
                        <>
                          <Tooltip title="Preview">
                            <IconButton size="small" onClick={() => handlePreview(job)}>
                              <PreviewIcon />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="Download">
                            <IconButton size="small" onClick={() => window.open(job.result_url, '_blank')}>
                              <DownloadIcon />
                            </IconButton>
                          </Tooltip>
                          {job.type === 'image' && (
                            <Tooltip title="Use for Video">
                              <IconButton 
                                size="small" 
                                onClick={() => {
                                  setSelectedImageUrl(job.result_url!);
                                  setContentType('video');
                                  setCurrentTab(0); // Switch to generate tab
                                }}
                              >
                                <VideoIcon />
                              </IconButton>
                            </Tooltip>
                          )}
                          <Tooltip title="Share">
                            <IconButton size="small">
                              <ShareIcon />
                            </IconButton>
                          </Tooltip>
                        </>
                      )}
                    </CardActions>
                  </Card>
              ))}
            </Box>
          )}
        </Box>
      )}

      {/* Preview Dialog */}
      <Dialog 
        open={previewDialog} 
        onClose={() => setPreviewDialog(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Content Preview</DialogTitle>
        <DialogContent>
          {previewContent && (
            <Box sx={{ textAlign: 'center' }}>
              {previewContent.type === 'image' ? (
                <img 
                  src={previewContent.url} 
                  alt="Generated content" 
                  style={{ maxWidth: '100%', height: 'auto' }}
                />
              ) : (
                <video 
                  src={previewContent.url} 
                  controls 
                  autoPlay
                  loop
                  muted
                  style={{ maxWidth: '100%', height: 'auto' }}
                />
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPreviewDialog(false)}>Close</Button>
          {previewContent && (
            <Button 
              variant="contained" 
              onClick={() => window.open(previewContent.url, '_blank')}
            >
              Download
            </Button>
          )}
        </DialogActions>
      </Dialog>

      {/* Sync Notification Snackbar */}
      <Snackbar
        open={showSyncSnackbar}
        autoHideDuration={4000}
        onClose={() => setShowSyncSnackbar(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert 
          onClose={() => setShowSyncSnackbar(false)} 
          severity={syncMessage.includes('Failed') || syncMessage.includes('Error') ? 'error' : 'success'}
          variant="filled"
          sx={{ width: '100%' }}
        >
          {syncMessage}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default ContentGeneration;
