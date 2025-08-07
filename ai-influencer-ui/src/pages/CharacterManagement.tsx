import React, { useState, useEffect, useCallback } from 'react';
import {
  Typography,
  Card,
  CardContent,
  CardActions,
  Button,
  TextField,
  Box,
  Chip,
  Avatar,
  LinearProgress,
  Alert,
  IconButton,
  Paper,
  ImageList,
  ImageListItem,
  Tabs,
  Tab,
  Tooltip,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  CloudUpload as UploadIcon,
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useDropzone } from 'react-dropzone';
import { characterAPI, trainingAPI, loraAPI } from '../utils/api';
import { mockTrainingAPI, useMockAPI } from '../utils/mockApi';

interface Character {
  id: string;
  name: string;
  description: string;
  style?: string;
  personality?: string;
  training_status: 'pending' | 'training' | 'completed' | 'failed';
  created_at: string;
  model_url?: string;
}

interface TrainingJob {
  jobId: string;
  characterName: string;
  status: 'processing' | 'completed' | 'failed';
  totalImages: number;
  completedImages: number;
  startTime: Date;
  estimatedCompletion: Date;
  imageUrls?: string[];
  currentAttempt?: number;
  maxAttempts?: number;
  successRate?: number;
}

interface TrainingImage {
  url: string;
  filename: string;
}

interface S3TrainingJob {
  job_id: string;
  character_name: string;
  total_images: number;
  created_date: string;
  last_modified: string;
  images: TrainingImage[];
}

const CharacterManagement: React.FC = () => {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [loading, setLoading] = useState(true);
  // Main workflow tab state
  const [activeTab, setActiveTab] = useState(0); // 0: Generate Images, 1: Create Characters, 2: Manage Characters
  
  // Generate Images tab state
  const [generatingImages, setGeneratingImages] = useState(false);
  const [trainingJobs, setTrainingJobs] = useState<TrainingJob[]>(() => {
    // Load jobs from localStorage on component mount
    const savedJobs = localStorage.getItem('trainingJobs');
    if (savedJobs) {
      try {
        const parsed = JSON.parse(savedJobs);
        // Convert date strings back to Date objects
        return parsed.map((job: any) => ({
          ...job,
          startTime: new Date(job.startTime),
          estimatedCompletion: new Date(job.estimatedCompletion)
        }));
      } catch (error) {
        console.error('Error parsing saved training jobs:', error);
        return [];
      }
    }
    return [];
  });
  const [imageGenForm, setImageGenForm] = useState({
    character_name: '',
    character_description: '',
    character_style: '',
    num_images: 20, // Default to 20 training images
  });
  
  // Create Characters tab state
  const [availableGeneratedImages, setAvailableGeneratedImages] = useState<string[]>([]);
  const [availableTrainingJobs, setAvailableTrainingJobs] = useState<S3TrainingJob[]>([]);
  const [selectedImages, setSelectedImages] = useState<File[]>([]);
  const [selectedGeneratedImages, setSelectedGeneratedImages] = useState<string[]>([]);
  const [imagePreviewUrls, setImagePreviewUrls] = useState<string[]>([]);
  const [imageSelectionTab, setImageSelectionTab] = useState(0); // 0 for upload, 1 for generated
  const [newCharacter, setNewCharacter] = useState({
    name: '',
    description: '',
    style: '',
    personality: '',
  });
  const [creating, setCreating] = useState(false);
  
  // Manage Characters tab state
  const [loraJobs, setLoraJobs] = useState<any[]>([]);
  
  // Global state
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchCharacters();
    fetchTrainingImages();
    fetchLoraJobs();
  }, []);

  // Poll LoRA training status every 30 seconds
  useEffect(() => {
    const pollLoraStatus = async () => {
      try {
        // Fetch all LoRA training jobs
        const response = await loraAPI.listTrainingJobs();
        const jobs = response.data.jobs || [];
        setLoraJobs(jobs);
        
        // Update character training status based on jobs
        const jobsByCharacter: Record<string, any> = {};
        jobs.forEach((job: any) => {
          if (job.character_id) {
            jobsByCharacter[job.character_id] = job;
          }
        });
        
        // Update characters with real-time status
        setCharacters(prev => prev.map(char => {
          const job = jobsByCharacter[char.id];
          if (job) {
            let status = 'pending';
            switch (job.status) {
              case 'training':
              case 'preparing':
                status = 'training';
                break;
              case 'completed':
                status = 'completed';
                break;
              case 'failed':
                status = 'failed';
                break;
              default:
                status = 'pending';
            }
            return { ...char, training_status: status as any };
          }
          // If no job found, keep the existing status from the character record
          return char;
        }));
        
        // Also refresh characters from the database occasionally to ensure consistency
        // This helps in case the backend updated the status via webhooks
        const shouldRefreshCharacters = jobs.some((job: any) => 
          job.status === 'completed' || job.status === 'failed'
        );
        if (shouldRefreshCharacters) {
          // Refresh characters after a short delay to ensure backend updates are processed
          setTimeout(() => {
            fetchCharacters();
          }, 2000);
        }
        
        console.log(`Polled LoRA jobs: ${jobs.length} jobs found`, jobs);
      } catch (error) {
        console.error('Error polling LoRA status:', error);
      }
    };

    // Poll immediately, then every 30 seconds
    pollLoraStatus();
    const interval = setInterval(pollLoraStatus, 30000);
    
    return () => clearInterval(interval);
  }, []); // Remove dependency to prevent recreating interval

  // Save training jobs to localStorage whenever they change
  useEffect(() => {
    localStorage.setItem('trainingJobs', JSON.stringify(trainingJobs));
  }, [trainingJobs]);

  // Poll job statuses - Fixed polling mechanism
  useEffect(() => {
    const activeJobs = trainingJobs.filter(job => job.status === 'processing');

    if (activeJobs.length === 0) {
      console.log('⏸️ No active jobs - polling paused to save resources');
      return; // No active jobs, so no polling needed
    }

    const pollJobStatus = async () => {
      try {
        // We refilter here to get the most current list of active jobs
        const jobsToPoll = trainingJobs.filter(job => job.status === 'processing');
        if (jobsToPoll.length === 0) return;

        console.log(`Polling status for ${jobsToPoll.length} active jobs...`);
        const apiToUse = useMockAPI ? mockTrainingAPI : trainingAPI;

        const statusPromises = jobsToPoll.map(async (job) => {
          try {
            const response = await apiToUse.getJobStatus(job.jobId);
            return { jobId: job.jobId, ...response.data };
          } catch (error) {
            console.error(`Error polling status for job ${job.jobId}:`, error);
            return { jobId: job.jobId, error: true };
          }
        });

        const statusUpdates = await Promise.all(statusPromises);

        setTrainingJobs(prevJobs => prevJobs.map(job => {
          const update = statusUpdates.find(u => u && u.jobId === job.jobId);
          if (update && !update.error) {
            return {
              ...job,
              status: update.status || job.status,
              completedImages: typeof update.completed_images === 'number' ? update.completed_images : job.completedImages,
              totalImages: typeof update.total_images === 'number' ? update.total_images : job.totalImages,
              currentAttempt: typeof update.current_attempt === 'number' ? update.current_attempt : job.currentAttempt,
              maxAttempts: typeof update.max_attempts === 'number' ? update.max_attempts : job.maxAttempts,
              successRate: typeof update.success_rate === 'number' ? update.success_rate : job.successRate,
              imageUrls: Array.isArray(update.image_urls) ? update.image_urls : job.imageUrls,
            };
          }
          return job;
        }));
      } catch (error) {
        console.error('Error in pollJobStatus:', error);
      }
    };

    console.log('▶️ Starting polling every 2 seconds for active training jobs');
    pollJobStatus(); // Initial poll
    const intervalId = setInterval(pollJobStatus, 2000);

    // Cleanup function to stop polling when the component unmounts or dependencies change
    return () => {
      clearInterval(intervalId);
      console.log('🛑 Training job polling stopped (cleanup)');
    };
  }, [trainingJobs.filter(j => j.status === 'processing').length]); // Depend on the number of active jobs

  // Update available generated images when training jobs change
  // BUT prioritize S3 images over placeholder images
  useEffect(() => {
    const completedImages: string[] = [];
    trainingJobs.forEach(job => {
      if (job.status === 'completed' && job.imageUrls) {
        completedImages.push(...job.imageUrls);
      }
    });
    
    // Only update from training jobs if we don't have S3 images already
    // S3 images should take priority over placeholder images
    if (completedImages.length > 0 && availableGeneratedImages.length === 0) {
      setAvailableGeneratedImages(completedImages);
    }
  }, [trainingJobs, availableGeneratedImages]);

  const fetchCharacters = async () => {
    try {
      const response = await characterAPI.getCharacters();
      // The API returns {data: []} so we access response.data.data
      setCharacters(response.data.data || []);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch characters:', err);
      setError('Failed to load characters. Please check your API connection.');
    } finally {
      setLoading(false);
    }
  };

  const fetchTrainingImages = async () => {
    try {
      console.log('Fetching training images from S3...');
      const response = await trainingAPI.getTrainingImages();
      const data = response.data.data;
      
      console.log('Training images data:', data);
      
      // Handle new structured response with training jobs
      if (data.training_jobs && data.training_jobs.length > 0) {
        setAvailableTrainingJobs(data.training_jobs);
        console.log(`Found ${data.training_jobs.length} training jobs with images`);
      }
      
      // Keep the flat array for compatibility
      if (data.all_image_urls && data.all_image_urls.length > 0) {
        setAvailableGeneratedImages(data.all_image_urls);
        console.log(`Found ${data.all_image_urls.length} training images in S3`);
      }
    } catch (err) {
      console.error('Failed to fetch training images:', err);
      // Don't set error state for this as it's not critical to the main functionality
    }
  };

  const fetchLoraJobs = async () => {
    try {
      const response = await loraAPI.listTrainingJobs();
      const jobs = response.data.jobs || [];
      setLoraJobs(jobs);
      console.log(`Found ${jobs.length} LoRA training jobs`);
    } catch (err) {
      console.error('Failed to fetch LoRA jobs:', err);
    }
  };

  const handleStartLoraTraining = async (characterId: string) => {
    try {
      setError(null);
      const response = await loraAPI.startTraining({ character_id: characterId });
      
      if (response.data.job_id) {
        setSuccessMessage(`LoRA training started successfully! Job ID: ${response.data.job_id}`);
        
        // Clear success message after 4 seconds
        setTimeout(() => {
          setSuccessMessage(null);
        }, 4000);
        
        // Refresh the jobs list to show the new training job
        setTimeout(fetchLoraJobs, 1000);
      } else {
        setError('Training started but no job ID returned');
      }
    } catch (err: any) {
      console.error('Failed to start LoRA training:', err);
      const errorMessage = err.response?.data?.error || 'Failed to start LoRA training. Please try again.';
      setError(errorMessage);
    }
  };

  // Drag and drop handlers
  const onDrop = useCallback((acceptedFiles: File[]) => {
    setError(null);
    
    // Filter only image files
    const imageFiles = acceptedFiles.filter(file => file.type.startsWith('image/'));
    
    if (imageFiles.length !== acceptedFiles.length) {
      setError(`${acceptedFiles.length - imageFiles.length} non-image files were ignored.`);
    }
    
    setSelectedImages(prev => [...prev, ...imageFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']
    },
    multiple: true
  });

  // Update image preview URLs when selected images change
  useEffect(() => {
    const urls: string[] = [];
    selectedImages.forEach(file => {
      const url = URL.createObjectURL(file);
      urls.push(url);
    });
    
    setImagePreviewUrls(urls);
    
    // Cleanup URLs when component unmounts or images change
    return () => {
      urls.forEach(url => URL.revokeObjectURL(url));
    };
  }, [selectedImages]);

  const removeUploadedImage = (index: number) => {
    setSelectedImages(prev => prev.filter((_, i) => i !== index));
  };

  const toggleGeneratedImage = (imageUrl: string) => {
    setSelectedGeneratedImages(prev => {
      if (prev.includes(imageUrl)) {
        return prev.filter(url => url !== imageUrl);
      } else {
        return [...prev, imageUrl];
      }
    });
  };

  const clearAllImages = () => {
    setSelectedImages([]);
    setSelectedGeneratedImages([]);
    setImagePreviewUrls([]);
  };

  const convertImagesToBase64 = async (files: File[]): Promise<string[]> => {
    const promises = files.map((file) => {
      return new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
          if (typeof reader.result === 'string') {
            resolve(reader.result.split(',')[1]); // Remove data:image/jpeg;base64, prefix
          } else {
            reject(new Error('Failed to read file'));
          }
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
    });
    return Promise.all(promises);
  };

  const handleCreateCharacter = async () => {
    const hasUploadedImages = selectedImages.length > 0;
    const hasGeneratedImages = selectedGeneratedImages.length > 0;
    
    if (!newCharacter.name || !newCharacter.description || (!hasUploadedImages && !hasGeneratedImages)) {
      setError('Please fill in all required fields and select at least one training image (uploaded or generated).');
      return;
    }

    try {
      setCreating(true);
      let trainingImages: string[] = [];
      
      // Combine both uploaded and generated images
      if (hasUploadedImages) {
        // Convert uploaded files to base64
        const uploadedBase64 = await convertImagesToBase64(selectedImages);
        trainingImages.push(...uploadedBase64);
      }
      
      if (hasGeneratedImages) {
        // Use generated image URLs directly
        trainingImages.push(...selectedGeneratedImages);
      }
      
      await characterAPI.createCharacter({
        ...newCharacter,
        training_images: trainingImages,
      });

      // Reset form and switch to manage characters tab
      setNewCharacter({ name: '', description: '', style: '', personality: '' });
      setSelectedImages([]);
      setSelectedGeneratedImages([]);
      // Don't clear availableGeneratedImages so S3 images persist
      fetchCharacters();
      setError(null);
      setSuccessMessage(`Character "${newCharacter.name}" created successfully! Switched to "Manage Characters" tab.`);
      setActiveTab(2); // Switch to manage characters tab
      
      // Clear success message after 4 seconds
      setTimeout(() => {
        setSuccessMessage(null);
      }, 4000);
    } catch (err) {
      console.error('Failed to create character:', err);
      setError('Failed to create character. Please try again.');
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteCharacter = async (characterId: string) => {
    if (window.confirm('Are you sure you want to delete this character? This action cannot be undone.')) {
      try {
        await characterAPI.deleteCharacter(characterId);
        fetchCharacters();
      } catch (err) {
        console.error('Failed to delete character:', err);
        setError('Failed to delete character. Please try again.');
      }
    }
  };

  const handleGenerateTrainingImages = async () => {
    if (!imageGenForm.character_name || !imageGenForm.character_description) {
      setError('Please fill in character name and description before generating training images.');
      return;
    }

    try {
      setGeneratingImages(true);
      setError(null);
      
      // Generate character description for training
      const fullDescription = `${imageGenForm.character_description}${imageGenForm.character_style ? `, ${imageGenForm.character_style} style` : ''}`;
      
      // Use mock API if enabled, otherwise use real API
      const apiToUse = useMockAPI ? mockTrainingAPI : trainingAPI;
      const response = await apiToUse.generateTrainingImages({
        character_name: imageGenForm.character_name,
        character_description: fullDescription,
        num_images: imageGenForm.num_images,
      });
      
      // Add job to tracking list
      const now = new Date();
      const estimatedCompletion = new Date(now.getTime() + 5 * 1000); // 5 seconds from now for testing
      
      const newJob: TrainingJob = {
        jobId: response.data.job_id,
        characterName: imageGenForm.character_name,
        status: 'processing',
        totalImages: response.data.total_images || imageGenForm.num_images,
        completedImages: 0,
        startTime: now,
        estimatedCompletion,
        currentAttempt: response.data.current_attempt || 1,
        maxAttempts: response.data.max_attempts || Math.min(imageGenForm.num_images * 2 + 3, 25),
        successRate: response.data.success_rate || 0,
      };
      
      setTrainingJobs(prev => [newJob, ...prev]); // Add new job at the beginning
      
      setSuccessMessage(`Training image generation started! Job ID: ${response.data.job_id}. Images will be available in the "Create Characters" tab once generation is complete.`);
      
      // Clear success message after 5 seconds
      setTimeout(() => {
        setSuccessMessage(null);
      }, 5000);
      
    } catch (err: any) {
      console.error('Failed to generate training images:', err);
      setError(err.response?.data?.error || 'Failed to start training image generation. Please try again.');
    } finally {
      setGeneratingImages(false);
    }
  };

  const handleUseGeneratedImages = (job: TrainingJob) => {
    if (job.status === 'completed' && job.imageUrls) {
      setSelectedGeneratedImages(job.imageUrls);
      setAvailableGeneratedImages(job.imageUrls);
      // Clear manually uploaded images when using generated ones
      setSelectedImages([]);
      // Switch to Create Characters tab
      setActiveTab(1);
      // Set the image selection to generated images
      setImageSelectionTab(1);
      setSuccessMessage(`Selected ${job.imageUrls.length} generated training images! Switched to "Create Characters" tab.`);
      
      // Clear success message after 4 seconds
      setTimeout(() => {
        setSuccessMessage(null);
      }, 4000);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'training':
        return 'warning';
      case 'failed':
        return 'error';
      default:
        return 'default';
    }
  };

  if (loading) {
    return (
      <Box sx={{ width: '100%' }}>
        <Typography variant="h4" gutterBottom>
          Character Management
        </Typography>
        <LinearProgress />
      </Box>
    );
  }

  const renderGenerateImagesTab = () => (
    <Box>
      <Typography variant="h5" gutterBottom>
        Generate Training Images
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        First, generate high-quality training images for your AI character. These images will be used to train a LoRA model.
      </Typography>

      {/* Image Generation Form */}
      <Card sx={{ mb: 4 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Character Details
          </Typography>
          <Box sx={{ display: 'grid', gap: 2 }}>
            <TextField
              fullWidth
              label="Character Name"
              value={imageGenForm.character_name}
              onChange={(e) => setImageGenForm({ ...imageGenForm, character_name: e.target.value })}
              placeholder="e.g., Emma Johnson"
              required
            />
            <TextField
              fullWidth
              label="Character Description"
              multiline
              rows={3}
              value={imageGenForm.character_description}
              onChange={(e) => setImageGenForm({ ...imageGenForm, character_description: e.target.value })}
              placeholder="e.g., A 25-year-old professional photographer with long brown hair and green eyes"
              required
            />
            <TextField
              fullWidth
              label="Visual Style (optional)"
              value={imageGenForm.character_style}
              onChange={(e) => setImageGenForm({ ...imageGenForm, character_style: e.target.value })}
              placeholder="e.g., photorealistic, professional headshots, natural lighting"
            />
            <TextField
              fullWidth
              label="Number of Training Images"
              type="number"
              value={imageGenForm.num_images}
              onChange={(e) => {
                const value = parseInt(e.target.value, 10);
                if (value >= 1 && value <= 50) {
                  setImageGenForm({ ...imageGenForm, num_images: value });
                }
              }}
              inputProps={{
                min: 1,
                max: 50,
                step: 1
              }}
              helperText="Number of training images to generate (1-50). More images provide better training but cost more. The system will retry failed generations up to a maximum number of attempts."
              required
            />
            <Box sx={{ mt: 1, p: 2, backgroundColor: 'background.default', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
              <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 'medium' }}>
                Retry Configuration:
              </Typography>
              <Typography variant="body2" color="text.primary" sx={{ mt: 0.5 }}>
                Maximum Attempts: <strong>{Math.min(imageGenForm.num_images * 2 + 3, 25)}</strong>
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                The system will attempt up to {Math.min(imageGenForm.num_images * 2 + 3, 25)} total generations to achieve {imageGenForm.num_images} successful images.
                {imageGenForm.num_images * 2 + 3 > 25 && ' (Capped at 25 attempts for efficiency)'}
              </Typography>
            </Box>
          </Box>
          <Box sx={{ mt: 3 }}>
            <Button
              variant="contained"
              onClick={handleGenerateTrainingImages}
              disabled={generatingImages || !imageGenForm.character_name || !imageGenForm.character_description}
              startIcon={generatingImages ? <RefreshIcon /> : <AddIcon />}
              size="large"
            >
              {generatingImages ? 'Generating Images...' : 'Generate Training Images'}
            </Button>
          </Box>
        </CardContent>
      </Card>

      {/* Training Jobs */}
      {trainingJobs.length > 0 && (
        <Box>
          <Typography variant="h6" gutterBottom>
            Image Generation Jobs
          </Typography>
          <Box sx={{ display: 'grid', gap: 2 }}>
            {trainingJobs
              .sort((a, b) => b.startTime.getTime() - a.startTime.getTime()) // Sort by start time, newest first
              .map((job) => (
              <Card key={job.jobId}>
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Box>
                      <Typography variant="h6">{job.characterName}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        Job ID: {job.jobId}
                      </Typography>
                    </Box>
                    <Chip
                      label={job.status}
                      color={job.status === 'completed' ? 'success' : job.status === 'failed' ? 'error' : 'warning'}
                      size="small"
                    />
                  </Box>
                  
                  <Box sx={{ mb: 2 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant="body2">Progress</Typography>
                      <Typography variant="body2">
                        {job.completedImages}/{job.totalImages} images
                      </Typography>
                    </Box>
                    <LinearProgress 
                      variant="determinate" 
                      value={(job.completedImages / job.totalImages) * 100}
                      sx={{ height: 8, borderRadius: 4 }}
                    />
                  </Box>
                  
                  {/* Attempts and Success Rate Indicators */}
                  {(job.currentAttempt || job.maxAttempts || job.successRate !== undefined) && (
                    <Box sx={{ mb: 2, p: 2, backgroundColor: 'background.default', borderRadius: 1 }}>
                      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
                        {job.currentAttempt !== undefined && job.maxAttempts !== undefined && (
                          <Box>
                            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 'medium' }}>
                              Generation Attempts
                            </Typography>
                            <Typography variant="body2" color="text.primary">
                              <strong>{job.currentAttempt}</strong> of <strong>{job.maxAttempts}</strong>
                            </Typography>
                          </Box>
                        )}
                        {job.successRate !== undefined && (
                          <Box>
                            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 'medium' }}>
                              Success Rate
                            </Typography>
                            <Typography variant="body2" color={job.successRate >= 70 ? 'success.main' : job.successRate >= 40 ? 'warning.main' : 'error.main'}>
                              <strong>{Math.round(job.successRate)}%</strong>
                            </Typography>
                          </Box>
                        )}
                      </Box>
                      {job.currentAttempt !== undefined && job.maxAttempts !== undefined && (
                        <Box sx={{ mt: 1 }}>
                          <LinearProgress 
                            variant="determinate" 
                            value={(job.currentAttempt / job.maxAttempts) * 100}
                            sx={{ 
                              height: 4, 
                              borderRadius: 2,
                              backgroundColor: 'action.hover',
                              '& .MuiLinearProgress-bar': {
                                backgroundColor: job.status === 'completed' ? 'success.main' : 'info.main'
                              }
                            }}
                          />
                        </Box>
                      )}
                    </Box>
                  )}
                  
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography variant="body2" color="text.secondary">
                      Started: {job.startTime.toLocaleTimeString()}
                    </Typography>
                    {job.status === 'completed' && (
                      <Button
                        variant="contained"
                        color="success"
                        size="small"
                        onClick={() => handleUseGeneratedImages(job)}
                        startIcon={<CheckCircleIcon />}
                      >
                        Use These Images
                      </Button>
                    )}
                  </Box>
                </CardContent>
              </Card>
            ))}
          </Box>
        </Box>
      )}
    </Box>
  );

  const renderCreateCharactersTab = () => (
    <Box>
      <Typography variant="h5" gutterBottom>
        Create AI Character
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Use your generated training images or upload your own to create an AI character model.
      </Typography>

      <Card>
        <CardContent>
          <Box sx={{ display: 'grid', gap: 2, mb: 3 }}>
            <TextField
              fullWidth
              label="Character Name"
              value={newCharacter.name}
              onChange={(e) => setNewCharacter({ ...newCharacter, name: e.target.value })}
              required
            />
            <TextField
              fullWidth
              label="Description"
              multiline
              rows={3}
              value={newCharacter.description}
              onChange={(e) => setNewCharacter({ ...newCharacter, description: e.target.value })}
              required
            />
            <TextField
              fullWidth
              label="Style (optional)"
              value={newCharacter.style}
              onChange={(e) => setNewCharacter({ ...newCharacter, style: e.target.value })}
              placeholder="e.g., photorealistic, anime, artistic"
            />
            <TextField
              fullWidth
              label="Personality (optional)"
              multiline
              rows={2}
              value={newCharacter.personality}
              onChange={(e) => setNewCharacter({ ...newCharacter, personality: e.target.value })}
              placeholder="e.g., cheerful, professional, edgy"
            />
          </Box>

          {/* Image Selection */}
          <Paper sx={{ p: 2, mb: 2, border: '1px dashed #ccc' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">
                Training Images
              </Typography>
              {(selectedImages.length > 0 || selectedGeneratedImages.length > 0) && (
                <Button
                  size="small"
                  startIcon={<CancelIcon />}
                  onClick={clearAllImages}
                  color="secondary"
                >
                  Clear All
                </Button>
              )}
            </Box>
            
            <Tabs 
              value={imageSelectionTab} 
              onChange={(e, newValue) => setImageSelectionTab(newValue)} 
              sx={{ mb: 2 }}
            >
              <Tab label={`Upload Images ${selectedImages.length > 0 ? `(${selectedImages.length})` : ''}`} />
              <Tab label={`Generated Images ${availableGeneratedImages.length > 0 ? `(${availableGeneratedImages.length})` : ''}`} />
            </Tabs>

            {/* Upload Tab */}
            {imageSelectionTab === 0 && (
              <Box>
                <Box
                  {...getRootProps()}
                  sx={{
                    border: '2px dashed',
                    borderColor: isDragActive ? 'primary.main' : 'grey.300',
                    borderRadius: 2,
                    p: 3,
                    textAlign: 'center',
                    cursor: 'pointer',
                    backgroundColor: isDragActive ? 'action.hover' : 'background.paper',
                    transition: 'all 0.2s ease',
                    mb: 2,
                    '&:hover': {
                      borderColor: 'primary.main',
                      backgroundColor: 'action.hover'
                    }
                  }}
                >
                  <input {...getInputProps()} />
                  <UploadIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 1 }} />
                  <Typography variant="h6" gutterBottom>
                    {isDragActive ? 'Drop images here...' : 'Drag & drop images here'}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    or click to browse files
                  </Typography>
                </Box>

                {selectedImages.length > 0 && (
                  <ImageList sx={{ width: '100%' }} cols={7} gap={8}>
                    {imagePreviewUrls.map((url, index) => (
                      <ImageListItem key={index} sx={{ position: 'relative' }}>
                        <Box
                          sx={{
                            position: 'relative',
                            borderRadius: 1,
                            overflow: 'hidden',
                            border: '1px solid #e0e0e0',
                            backgroundColor: '#ffffff',
                            cursor: 'pointer',
                            transition: 'all 0.2s ease',
                            '&:hover': {
                              transform: 'scale(1.03)',
                              boxShadow: '0 3px 12px rgba(0,0,0,0.2)',
                              borderColor: 'primary.main'
                            }
                          }}
                        >
                          <img
                            src={url}
                            alt={`Preview ${index + 1}`}
                            loading="lazy"
                            style={{
                              width: '100%',
                              height: 140,
                              objectFit: 'contain',
                              display: 'block'
                            }}
                          />
                          
                          {/* Remove button */}
                          <Box
                            sx={{
                              position: 'absolute',
                              top: 4,
                              right: 4,
                              opacity: 0,
                              transition: 'opacity 0.2s ease',
                              '.MuiImageListItem-root:hover &': {
                                opacity: 1
                              }
                            }}
                          >
                            <Tooltip title="Remove">
                              <IconButton
                                onClick={(e) => {
                                  e.stopPropagation();
                                  removeUploadedImage(index);
                                }}
                                size="small"
                                sx={{
                                  backgroundColor: 'rgba(244, 67, 54, 0.9)',
                                  color: 'white',
                                  width: 20,
                                  height: 20,
                                  '&:hover': {
                                    backgroundColor: 'rgba(244, 67, 54, 1)'
                                  }
                                }}
                              >
                                <CancelIcon sx={{ fontSize: 14 }} />
                              </IconButton>
                            </Tooltip>
                          </Box>

                          {/* Subtle clickable indicator */}
                          <Box
                            sx={{
                              position: 'absolute',
                              bottom: 0,
                              left: 0,
                              right: 0,
                              height: 3,
                              backgroundColor: 'primary.main',
                              opacity: 0.8
                            }}
                          />
                        </Box>
                      </ImageListItem>
                    ))}
                  </ImageList>
                )}
              </Box>
            )}

            {/* Generated Images Tab */}
            {imageSelectionTab === 1 && (
              <Box>
                <Button
                  variant="outlined"
                  onClick={fetchTrainingImages}
                  startIcon={<RefreshIcon />}
                  sx={{ mb: 2 }}
                >
                  Refresh Available Images
                </Button>

                {availableTrainingJobs && availableTrainingJobs.length > 0 ? (
                  availableTrainingJobs.map((job) => (
                    <Box key={job.job_id} sx={{ mb: 4 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                        <Typography variant="h6" color="primary">
                          {job.character_name} ({job.total_images} images)
                        </Typography>
                        <Button
                          size="small"
                          variant="outlined"
                          onClick={() => {
                            const jobImageUrls = job.images.map(img => img.url);
                            setSelectedGeneratedImages(prev => {
                              const allSelected = jobImageUrls.every(url => prev.includes(url));
                              if (allSelected) {
                                return prev.filter(url => !jobImageUrls.includes(url));
                              } else {
                                const newSelected = [...prev];
                                jobImageUrls.forEach(url => {
                                  if (!newSelected.includes(url)) {
                                    newSelected.push(url);
                                  }
                                });
                                return newSelected;
                              }
                            });
                          }}
                        >
                          {job.images.every(img => selectedGeneratedImages.includes(img.url)) ? 'Unselect All' : 'Select All'}
                        </Button>
                      </Box>
                      
                      <ImageList sx={{ width: '100%' }} cols={7} gap={8}>
                        {job.images.map((image, index) => {
                          const isSelected = selectedGeneratedImages.includes(image.url);
                          return (
                            <ImageListItem 
                              key={`${job.job_id}-${index}`}
                              sx={{ 
                                position: 'relative',
                                cursor: 'pointer',
                                transition: 'all 0.2s ease',
                                '&:hover': {
                                  transform: 'scale(1.03)',
                                  '& .hover-border': {
                                    borderColor: 'primary.main',
                                    boxShadow: '0 3px 12px rgba(0,0,0,0.2)'
                                  }
                                }
                              }}
                              onClick={() => toggleGeneratedImage(image.url)}
                            >
                              <Box
                                className="hover-border"
                                sx={{
                                  position: 'relative',
                                  overflow: 'hidden',
                                  borderRadius: 1,
                                  border: isSelected ? '2px solid' : '1px solid',
                                  borderColor: isSelected ? 'success.main' : 'grey.300',
                                  backgroundColor: '#ffffff',
                                  transition: 'all 0.2s ease'
                                }}
                              >
                                <img
                                  src={image.url}
                                  alt={`${job.character_name} ${index + 1}`}
                                  loading="lazy"
                                  style={{
                                    width: '100%',
                                    height: '140px',
                                    objectFit: 'contain',
                                    display: 'block'
                                  }}
                                />
                                
                                {/* Selection indicator */}
                                {isSelected && (
                                  <Box
                                    sx={{
                                      position: 'absolute',
                                      top: 4,
                                      right: 4,
                                      backgroundColor: 'success.main',
                                      borderRadius: '50%',
                                      width: 18,
                                      height: 18,
                                      display: 'flex',
                                      alignItems: 'center',
                                      justifyContent: 'center',
                                      boxShadow: '0 1px 3px rgba(0,0,0,0.3)'
                                    }}
                                  >
                                    <CheckCircleIcon sx={{ color: 'white', fontSize: 14 }} />
                                  </Box>
                                )}

                                {/* Clickable indicator bar */}
                                <Box
                                  sx={{
                                    position: 'absolute',
                                    bottom: 0,
                                    left: 0,
                                    right: 0,
                                    height: 3,
                                    backgroundColor: isSelected ? 'success.main' : 'primary.main',
                                    opacity: isSelected ? 1 : 0.8,
                                    transition: 'opacity 0.2s ease'
                                  }}
                                />
                              </Box>
                            </ImageListItem>
                          );
                        })}
                      </ImageList>
                    </Box>
                  ))
                ) : (
                  <Box sx={{ textAlign: 'center', py: 4 }}>
                    <Typography variant="body2" color="text.secondary">
                      No generated images available. Go to "Generate Images" tab first.
                    </Typography>
                    <Button 
                      variant="outlined" 
                      onClick={() => setActiveTab(0)}
                      sx={{ mt: 2 }}
                    >
                      Generate Images
                    </Button>
                  </Box>
                )}
              </Box>
            )}

            {/* Summary */}
            <Box sx={{ mt: 2, p: 1, backgroundColor: 'background.default', borderRadius: 1 }}>
              <Typography variant="caption" color="text.secondary">
                Total selected: {selectedImages.length + selectedGeneratedImages.length} images
                {selectedImages.length > 0 && ` (${selectedImages.length} uploaded)`}
                {selectedGeneratedImages.length > 0 && ` (${selectedGeneratedImages.length} generated)`}
              </Typography>
            </Box>
          </Paper>

          <Button 
            onClick={handleCreateCharacter} 
            variant="contained"
            disabled={creating || !newCharacter.name || !newCharacter.description || (selectedImages.length === 0 && selectedGeneratedImages.length === 0)}
            size="large"
            startIcon={creating ? <RefreshIcon /> : <AddIcon />}
          >
            {creating ? 'Creating Character...' : 'Create Character'}
          </Button>
        </CardContent>
      </Card>
    </Box>
  );

  const renderManageCharactersTab = () => (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h5" gutterBottom>
            Manage Characters
          </Typography>
          <Typography variant="body2" color="text.secondary">
            View and manage your AI character models. Start LoRA training for newly created characters.
          </Typography>
        </Box>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={() => {
            fetchCharacters();
            fetchLoraJobs();
          }}
          size="small"
        >
          Refresh Status
        </Button>
      </Box>

      {characters.length === 0 && !loading ? (
        <Box sx={{ textAlign: 'center', mt: 5 }}>
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No characters created yet
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Create your first AI influencer character to get started
          </Typography>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setActiveTab(1)}
          >
            Create Your First Character
          </Button>
        </Box>
      ) : (
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', md: '1fr 1fr 1fr' }, gap: 3 }}>
          {characters.map((character) => (
            <Card key={character.id} sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
              <CardContent sx={{ flexGrow: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <Avatar sx={{ mr: 2, bgcolor: 'primary.main' }}>
                    {character.name.charAt(0).toUpperCase()}
                  </Avatar>
                  <Box>
                    <Typography variant="h6" component="div">
                      {character.name}
                    </Typography>
                    <Chip
                      label={character.training_status}
                      color={getStatusColor(character.training_status) as any}
                      size="small"
                    />
                  </Box>
                </Box>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  {character.description}
                </Typography>
                {character.style && (
                  <Typography variant="caption" display="block" sx={{ mb: 1 }}>
                    <strong>Style:</strong> {character.style}
                  </Typography>
                )}
                {character.personality && (
                  <Typography variant="caption" display="block">
                    <strong>Personality:</strong> {character.personality}
                  </Typography>
                )}
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
                  Created: {new Date(character.created_at).toLocaleDateString()}
                </Typography>
              </CardContent>
              <CardActions sx={{ justifyContent: 'space-between' }}>
                <Box>
                  <IconButton size="small" color="primary">
                    <EditIcon />
                  </IconButton>
                  <IconButton 
                    size="small" 
                    color="error"
                    onClick={() => handleDeleteCharacter(character.id)}
                  >
                    <DeleteIcon />
                  </IconButton>
                </Box>
                {character.training_status === 'pending' && (
                  <Button
                    size="small"
                    variant="contained"
                    color="primary"
                    onClick={() => handleStartLoraTraining(character.id)}
                    sx={{ fontSize: '0.75rem' }}
                  >
                    Start Training
                  </Button>
                )}
              </CardActions>
            </Card>
          ))}
        </Box>
      )}
    </Box>
  );

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">AI Character Workflow</Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}
      
      {successMessage && (
        <Alert severity="success" sx={{ mb: 3 }}>
          {successMessage}
        </Alert>
      )}

      {/* Main Workflow Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs 
          value={activeTab} 
          onChange={(e, newValue) => setActiveTab(newValue)}
          variant="fullWidth"
        >
          <Tab 
            label="1. Generate Images" 
            icon={<RefreshIcon />} 
            iconPosition="start"
            sx={{ 
              fontSize: '1rem',
              fontWeight: activeTab === 0 ? 'bold' : 'normal'
            }}
          />
          <Tab 
            label="2. Create Characters" 
            icon={<AddIcon />} 
            iconPosition="start"
            sx={{ 
              fontSize: '1rem',
              fontWeight: activeTab === 1 ? 'bold' : 'normal'
            }}
          />
          <Tab 
            label="3. Manage Characters" 
            icon={<EditIcon />} 
            iconPosition="start"
            sx={{ 
              fontSize: '1rem',
              fontWeight: activeTab === 2 ? 'bold' : 'normal'
            }}
          />
        </Tabs>
      </Box>

      {/* Tab Content */}
      {activeTab === 0 && renderGenerateImagesTab()}
      {activeTab === 1 && renderCreateCharactersTab()}
      {activeTab === 2 && renderManageCharactersTab()}
    </Box>
  );
};

export default CharacterManagement;
