/**
 * Mock API service for testing the retry mechanism and progress display
 * without making real Replicate API calls
 */

export interface MockJobProgress {
  job_id: string;
  status: 'processing' | 'completed' | 'failed';
  completed_images: number;
  total_images: number;
  current_attempt: number;
  max_attempts: number;
  success_rate: number;
  image_urls: string[];
  start_time?: string;
  estimated_completion?: string;
}

class MockTrainingAPI {
  private jobs: Map<string, MockJobProgress> = new Map();
  private mockDelay = 1000; // 1 second delay to simulate network requests

  async generateTrainingImages(data: {
    character_name: string;
    character_description: string;
    num_images: number;
  }) {
    await this.delay(this.mockDelay);

    const jobId = `mock_job_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const maxAttempts = Math.min(data.num_images * 2 + 3, 25);

    // Create initial job status
    const job: MockJobProgress = {
      job_id: jobId,
      status: 'processing',
      completed_images: 0,
      total_images: data.num_images,
      current_attempt: 0,
      max_attempts: maxAttempts,
      success_rate: 0,
      image_urls: [],
      start_time: new Date().toISOString(),
    };

    this.jobs.set(jobId, job);

    // Start simulating the generation process
    this.simulateImageGeneration(jobId, data.num_images, maxAttempts);

    return {
      data: {
        job_id: jobId,
        status: 'processing',
        total_images: data.num_images,
        max_attempts: maxAttempts,
        current_attempt: 0,
        success_rate: 0,
      },
    };
  }

  async getJobStatus(jobId: string) {
    await this.delay(200); // Shorter delay for status checks

    const job = this.jobs.get(jobId);
    if (!job) {
      throw new Error(`Job ${jobId} not found`);
    }

    return {
      data: job,
    };
  }

  private async simulateImageGeneration(jobId: string, targetImages: number, maxAttempts: number) {
    const job = this.jobs.get(jobId);
    if (!job) return;

    // Simulate realistic success rate patterns with randomization
    const successRatePattern = this.getSuccessRatePattern();
    const patternName = successRatePattern === 'high' ? 'High Success (80-95%)' : 
                       successRatePattern === 'medium' ? 'Medium Success (60-80%)' : 
                       'Low Success (30-50%)';
    
    console.log(`🎲 Mock Job ${jobId}: Random pattern selected - ${patternName}`);
    
    let completedImages = 0;
    let currentAttempt = 0;

    const scheduleNextAttempt = () => {
      // Randomize timing between attempts (200-400ms for variety)
      const nextAttemptDelay = 200 + Math.random() * 200;
      
      setTimeout(() => {
        currentAttempt++;
        
        // Determine if this attempt succeeds based on the pattern
        const shouldSucceed = this.shouldAttemptSucceed(currentAttempt, successRatePattern);
        
        if (shouldSucceed && completedImages < targetImages) {
          completedImages++;
          job.image_urls.push(`https://mock-s3-bucket.amazonaws.com/training-images/${jobId}/image_${completedImages}.jpg`);
        }

        // Update job progress
        job.current_attempt = currentAttempt;
        job.completed_images = completedImages;
        job.success_rate = (completedImages / currentAttempt) * 100;

        const statusIcon = shouldSucceed && completedImages <= targetImages ? '✅' : '❌';
        console.log(`${statusIcon} Mock Job ${jobId}: Attempt ${currentAttempt}/${maxAttempts}, Images: ${completedImages}/${targetImages}, Success Rate: ${job.success_rate.toFixed(1)}%`);

        // Check completion conditions
        if (completedImages >= targetImages || currentAttempt >= maxAttempts) {
          job.status = 'completed';
          job.estimated_completion = new Date().toISOString();
          
          const completionIcon = completedImages >= targetImages ? '🎉' : '⚠️';
          const completionMsg = completedImages >= targetImages ? 'SUCCESS' : 'PARTIAL SUCCESS';
          console.log(`${completionIcon} Mock Job ${jobId} ${completionMsg}: Generated ${completedImages}/${targetImages} images in ${currentAttempt} attempts`);
        } else {
          // Schedule next attempt
          scheduleNextAttempt();
        }

        this.jobs.set(jobId, job);
      }, nextAttemptDelay);
    };
    
    // Start the first attempt
    scheduleNextAttempt();
  }

  private getSuccessRatePattern(): 'high' | 'medium' | 'low' {
    // Realistic distribution based on actual Replicate API behavior
    const rand = Math.random();
    
    // Weighted distribution to simulate real-world patterns:
    if (rand < 0.15) return 'low';    // 15% chance of low success rate (30-50%)
    if (rand < 0.70) return 'medium'; // 55% chance of medium success rate (60-80%)
    return 'high';                    // 30% chance of high success rate (80-95%)
  }

  private shouldAttemptSucceed(attemptNumber: number, pattern: 'high' | 'medium' | 'low'): boolean {
    let baseSuccessRate: number;
    
    switch (pattern) {
      case 'high':
        baseSuccessRate = 0.85; // 85% success rate
        break;
      case 'medium':
        baseSuccessRate = 0.65; // 65% success rate
        break;
      case 'low':
        baseSuccessRate = 0.35; // 35% success rate
        break;
    }

    // Add some randomness but maintain the overall success rate
    const variation = (Math.random() - 0.5) * 0.3; // ±15% variation
    const adjustedSuccessRate = Math.max(0.1, Math.min(0.95, baseSuccessRate + variation));
    
    return Math.random() < adjustedSuccessRate;
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // Method to get all jobs (for debugging)
  getAllJobs(): MockJobProgress[] {
    return Array.from(this.jobs.values());
  }

  // Method to clear all jobs (for testing)
  clearAllJobs(): void {
    this.jobs.clear();
  }
}

// Create and export singleton instance
export const mockTrainingAPI = new MockTrainingAPI();

// Export interface for the component to use
export interface MockAPI {
  generateTrainingImages: typeof mockTrainingAPI.generateTrainingImages;
  getJobStatus: typeof mockTrainingAPI.getJobStatus;
}

// Configuration to enable/disable mock mode
export const useMockAPI = process.env.NODE_ENV === 'development' && process.env.REACT_APP_USE_MOCK_API === 'true';

console.log('Mock API mode:', useMockAPI ? 'ENABLED' : 'DISABLED');
