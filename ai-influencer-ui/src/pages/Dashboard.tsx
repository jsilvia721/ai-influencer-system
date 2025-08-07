import React, { useEffect, useState } from 'react';
import {
  Typography,
  Card,
  CardContent,
  CardActions,
  Box,
  LinearProgress,
  Chip,
  Alert,
  Button,
  Grid,
  Paper,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Avatar,
  IconButton,
  Tooltip,
  Badge,
  Skeleton,
  CircularProgress,
} from '@mui/material';
import {
  Person as PersonIcon,
  AutoAwesome as GenerateIcon,
  Schedule as ScheduleIcon,
  TrendingUp as TrendingUpIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Refresh as RefreshIcon,
  Add as AddIcon,
  PlayArrow as PlayArrowIcon,
  Notifications as NotificationsIcon,
  Timeline as TimelineIcon,
} from '@mui/icons-material';
import { analyticsAPI, characterAPI, socialAPI, loraAPI } from '../utils/api';

interface DashboardStats {
  totalCharacters: number;
  activeTrainings: number;
  completedTrainings: number;
  generationsToday: number;
  scheduledPosts: number;
  recentGenerations: any[];
  systemHealth: 'healthy' | 'warning' | 'error';
  notifications: Notification[];
  recentActivity: Activity[];
}

interface Notification {
  id: string;
  type: 'success' | 'warning' | 'error' | 'info';
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
}

interface Activity {
  id: string;
  type: 'training' | 'generation' | 'post' | 'character';
  title: string;
  description: string;
  timestamp: string;
  status: 'completed' | 'failed' | 'processing';
}

const StatCard: React.FC<{
  title: string;
  value: string | number;
  icon: React.ReactNode;
  color?: string;
}> = ({ title, value, icon, color = 'primary' }) => (
  <Card sx={{ height: '100%' }}>
    <CardContent>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
        <Box sx={{ color: `${color}.main`, mr: 1 }}>{icon}</Box>
        <Typography variant="h6" component="div">
          {title}
        </Typography>
      </Box>
      <Typography variant="h4" component="div" sx={{ fontWeight: 'bold' }}>
        {value}
      </Typography>
    </CardContent>
  </Card>
);

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats>({
    totalCharacters: 0,
    activeTrainings: 0,
    completedTrainings: 0,
    generationsToday: 0,
    scheduledPosts: 0,
    recentGenerations: [],
    systemHealth: 'healthy',
    notifications: [],
    recentActivity: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchDashboardData = async () => {
    try {
      setRefreshing(true);
      
      // Fetch data from multiple endpoints
      const [charactersRes, loraJobsRes] = await Promise.allSettled([
        characterAPI.getCharacters(),
        loraAPI.listTrainingJobs(),
      ]);

      let characters = [];
      let loraJobs = [];

      if (charactersRes.status === 'fulfilled') {
        characters = charactersRes.value.data.data || [];
      }

      if (loraJobsRes.status === 'fulfilled') {
        loraJobs = loraJobsRes.value.data.jobs || [];
      }

      // Generate mock notifications
      const mockNotifications: Notification[] = [
        {
          id: '1',
          type: 'success',
          title: 'Training Complete',
          message: 'Character LoRA training completed successfully',
          timestamp: new Date().toISOString(),
          read: false,
        },
        {
          id: '2',
          type: 'info',
          title: 'Content Generated',
          message: 'New image content ready for posting',
          timestamp: new Date(Date.now() - 3600000).toISOString(),
          read: false,
        },
      ];

      // Generate mock activity
      const mockActivity: Activity[] = [
        {
          id: '1',
          type: 'training',
          title: 'LoRA Training Started',
          description: 'Character training initiated with 15 images',
          timestamp: new Date().toISOString(),
          status: 'processing',
        },
        {
          id: '2',
          type: 'generation',
          title: 'Image Generated',
          description: 'Portrait shot with professional lighting',
          timestamp: new Date(Date.now() - 1800000).toISOString(),
          status: 'completed',
        },
        {
          id: '3',
          type: 'character',
          title: 'New Character Created',
          description: 'Isabella Rose character profile setup',
          timestamp: new Date(Date.now() - 7200000).toISOString(),
          status: 'completed',
        },
      ];

      // Get generation jobs from localStorage
      const savedGenerationJobs = localStorage.getItem('generationJobs');
      let generationJobs = [];
      if (savedGenerationJobs) {
        try {
          generationJobs = JSON.parse(savedGenerationJobs);
        } catch (e) {}
      }

      const todayGenerations = generationJobs.filter((job: any) => {
        const jobDate = new Date(job.created_at);
        const today = new Date();
        return jobDate.toDateString() === today.toDateString();
      }).length;

      // Process the results
      const newStats: DashboardStats = {
        totalCharacters: characters.length,
        activeTrainings: loraJobs.filter((job: any) => job.status === 'training' || job.status === 'preparing').length,
        completedTrainings: loraJobs.filter((job: any) => job.status === 'completed').length,
        generationsToday: todayGenerations,
        scheduledPosts: 0, // Implement when social features are ready
        recentGenerations: generationJobs.slice(0, 5),
        systemHealth: 'healthy',
        notifications: mockNotifications,
        recentActivity: mockActivity,
      };

      setStats(newStats);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err);
      setError('Failed to load dashboard data. Please check your API connection.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchDashboardData, 30000);
    return () => clearInterval(interval);
  }, []);

  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'training': return <TrendingUpIcon />;
      case 'generation': return <GenerateIcon />;
      case 'post': return <ScheduleIcon />;
      case 'character': return <PersonIcon />;
      default: return <TimelineIcon />;
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircleIcon color="success" />;
      case 'failed': return <ErrorIcon color="error" />;
      case 'processing': return <TrendingUpIcon color="warning" />;
      default: return <TimelineIcon />;
    }
  };

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'success': return <CheckCircleIcon />;
      case 'warning': return <WarningIcon />;
      case 'error': return <ErrorIcon />;
      default: return <NotificationsIcon />;
    }
  };

  if (loading) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>
          Dashboard
        </Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' }, gap: 3, mb: 3 }}>
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} variant="rectangular" height={120} />
          ))}
        </Box>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '2fr 1fr' }, gap: 3 }}>
          <Skeleton variant="rectangular" height={300} />
          <Skeleton variant="rectangular" height={300} />
        </Box>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Dashboard</Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title="Auto-refresh every 30s">
            <Chip
              icon={<TimelineIcon />}
              label="Live"
              color="success"
              size="small"
              variant="outlined"
            />
          </Tooltip>
          <Button
            startIcon={refreshing ? <CircularProgress size={16} /> : <RefreshIcon />}
            onClick={fetchDashboardData}
            disabled={refreshing}
            size="small"
            variant="outlined"
          >
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </Button>
        </Box>
      </Box>
      
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* System Health & Notifications */}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '2fr 1fr' }, gap: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <Chip
            icon={stats.systemHealth === 'healthy' ? <CheckCircleIcon /> : <ErrorIcon />}
            label={`System ${stats.systemHealth.toUpperCase()}`}
            color={stats.systemHealth === 'healthy' ? 'success' : 'error'}
          />
          <Typography variant="body2" color="text.secondary">
            All services operational • Last updated: {new Date().toLocaleTimeString()}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Badge badgeContent={stats.notifications.filter(n => !n.read).length} color="error">
            <IconButton>
              <NotificationsIcon />
            </IconButton>
          </Badge>
        </Box>
      </Box>

      {/* Stats Cards */}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' }, gap: 3, mb: 4 }}>
        <StatCard
          title="Total Characters"
          value={stats.totalCharacters}
          icon={<PersonIcon />}
          color="primary"
        />
        <StatCard
          title="Active Trainings"
          value={stats.activeTrainings}
          icon={<TrendingUpIcon />}
          color="warning"
        />
        <StatCard
          title="Generations Today"
          value={stats.generationsToday}
          icon={<GenerateIcon />}
          color="success"
        />
        <StatCard
          title="Completed Trainings"
          value={stats.completedTrainings}
          icon={<CheckCircleIcon />}
          color="info"
        />
      </Box>

      {/* Main Content */}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '2fr 1fr' }, gap: 3 }}>
        {/* Recent Activity */}
        <Card sx={{ height: '100%' }}>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">
                Recent Activity
              </Typography>
              <IconButton size="small" onClick={fetchDashboardData}>
                <RefreshIcon />
              </IconButton>
            </Box>
            
            <List>
              {stats.recentActivity.length > 0 ? (
                stats.recentActivity.map((activity, index) => (
                  <React.Fragment key={activity.id}>
                    <ListItem sx={{ px: 0 }}>
                      <ListItemIcon>
                        <Avatar sx={{ width: 32, height: 32 }}>
                          {getActivityIcon(activity.type)}
                        </Avatar>
                      </ListItemIcon>
                      <ListItemText
                        primary={
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Typography variant="body2" fontWeight="medium">
                              {activity.title}
                            </Typography>
                            {getStatusIcon(activity.status)}
                          </Box>
                        }
                        secondary={
                          <>
                            <Typography variant="caption" display="block">
                              {activity.description}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {new Date(activity.timestamp).toLocaleString()}
                            </Typography>
                          </>
                        }
                      />
                    </ListItem>
                    {index < stats.recentActivity.length - 1 && <Divider />}
                  </React.Fragment>
                ))
              ) : (
                <ListItem>
                  <ListItemText primary="No recent activity" secondary="Activity will appear here as you use the system" />
                </ListItem>
              )}
            </List>
          </CardContent>
        </Card>

        {/* Quick Actions & Notifications */}
        <Box sx={{ display: 'grid', gridTemplateRows: 'auto auto', gap: 2 }}>
          {/* Quick Actions */}
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Quick Actions
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <Button
                  variant="contained"
                  startIcon={<AddIcon />}
                  fullWidth
                  onClick={() => window.location.href = '/characters'}
                >
                  Create Character
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<GenerateIcon />}
                  fullWidth
                  onClick={() => window.location.href = '/generate'}
                >
                  Generate Content
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<ScheduleIcon />}
                  fullWidth
                  onClick={() => window.location.href = '/schedule'}
                >
                  Schedule Post
                </Button>
              </Box>
            </CardContent>
          </Card>

          {/* Notifications */}
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Notifications
              </Typography>
              
              {stats.notifications.length > 0 ? (
                <List dense>
                  {stats.notifications.slice(0, 3).map((notification) => (
                    <ListItem key={notification.id} sx={{ px: 0 }}>
                      <ListItemIcon>
                        {getNotificationIcon(notification.type)}
                      </ListItemIcon>
                      <ListItemText
                        primary={notification.title}
                        secondary={
                          <>
                            <Typography variant="caption" display="block">
                              {notification.message}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {new Date(notification.timestamp).toLocaleString()}
                            </Typography>
                          </>
                        }
                      />
                    </ListItem>
                  ))}
                </List>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No new notifications
                </Typography>
              )}
            </CardContent>
          </Card>
        </Box>
      </Box>
    </Box>
  );
};

export default Dashboard;
