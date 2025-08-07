import React, { useState, useEffect } from 'react';
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
  Grid,
  Chip,
  Avatar,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Paper,
  Tabs,
  Tab,
  Switch,
  FormControlLabel,
  Skeleton,
} from '@mui/material';
import {
  Instagram as InstagramIcon,
  Twitter as TwitterIcon,
  Facebook as FacebookIcon,
  Schedule as ScheduleIcon,
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Send as SendIcon,
  AccessTime as ClockIcon,
  Image as ImageIcon,
  VideoLibrary as VideoIcon,
  TrendingUp as TrendingIcon,
  MusicNote as MusicIcon,
} from '@mui/icons-material';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { characterAPI } from '../utils/api';
import dayjs from 'dayjs';

interface ScheduledPost {
  id: string;
  platform: 'instagram' | 'twitter' | 'facebook';
  character_id: string;
  character_name: string;
  content: string;
  media_url?: string;
  media_type?: 'image' | 'video';
  scheduled_time: string;
  status: 'scheduled' | 'posted' | 'failed';
  hashtags: string[];
  music_track?: string;
  created_at: string;
}

interface Character {
  id: string;
  name: string;
  training_status: string;
}

const SocialScheduler: React.FC = () => {
  const [scheduledPosts, setScheduledPosts] = useState<ScheduledPost[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [loading, setLoading] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [currentTab, setCurrentTab] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // New post form state
  const [newPost, setNewPost] = useState({
    platform: 'instagram' as 'instagram' | 'twitter' | 'facebook',
    character_id: '',
    content: '',
    media_url: '',
    media_type: 'image' as 'image' | 'video',
    scheduled_time: dayjs().add(1, 'hour'),
    hashtags: [] as string[],
    music_track: '',
    auto_hashtags: true,
    trending_music: false,
  });

  useEffect(() => {
    fetchData();
    loadScheduledPosts();
  }, []);

  const fetchData = async () => {
    try {
      const charactersRes = await characterAPI.getCharacters();
      const charactersData = charactersRes.data.data || [];
      setCharacters(charactersData.filter((char: Character) => char.training_status === 'completed'));
    } catch (err) {
      console.error('Failed to fetch data:', err);
      setError('Failed to load data.');
    } finally {
      setLoading(false);
    }
  };

  const loadScheduledPosts = () => {
    const saved = localStorage.getItem('scheduledPosts');
    if (saved) {
      try {
        setScheduledPosts(JSON.parse(saved));
      } catch (e) {}
    }
  };

  const saveScheduledPosts = (posts: ScheduledPost[]) => {
    localStorage.setItem('scheduledPosts', JSON.stringify(posts));
    setScheduledPosts(posts);
  };

  const handleCreatePost = async () => {
    if (!newPost.platform || !newPost.character_id || !newPost.content) {
      setError('Please fill in all required fields.');
      return;
    }

    try {
      const selectedChar = characters.find(char => char.id === newPost.character_id);
      if (!selectedChar) return;

      const post: ScheduledPost = {
        id: `post_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        platform: newPost.platform,
        character_id: newPost.character_id,
        character_name: selectedChar.name,
        content: newPost.content,
        media_url: newPost.media_url || undefined,
        media_type: newPost.media_type,
        scheduled_time: newPost.scheduled_time.toISOString(),
        status: 'scheduled',
        hashtags: newPost.hashtags,
        music_track: newPost.music_track || undefined,
        created_at: new Date().toISOString(),
      };

      const updatedPosts = [post, ...scheduledPosts];
      saveScheduledPosts(updatedPosts);

      setCreateDialogOpen(false);
      setNewPost({
        platform: 'instagram',
        character_id: '',
        content: '',
        media_url: '',
        media_type: 'image',
        scheduled_time: dayjs().add(1, 'hour'),
        hashtags: [],
        music_track: '',
        auto_hashtags: true,
        trending_music: false,
      });
      setError(null);
    } catch (err) {
      console.error('Failed to create post:', err);
      setError('Failed to schedule post.');
    }
  };

  const handleDeletePost = (postId: string) => {
    const updatedPosts = scheduledPosts.filter(post => post.id !== postId);
    saveScheduledPosts(updatedPosts);
  };

  const getPlatformIcon = (platform: string) => {
    switch (platform) {
      case 'instagram': return <InstagramIcon />;
      case 'twitter': return <TwitterIcon />;
      case 'facebook': return <FacebookIcon />;
      default: return <ScheduleIcon />;
    }
  };

  const getPlatformColor = (platform: string) => {
    switch (platform) {
      case 'instagram': return '#E4405F';
      case 'twitter': return '#1DA1F2';
      case 'facebook': return '#4267B2';
      default: return '#666';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'posted': return 'success';
      case 'failed': return 'error';
      default: return 'default';
    }
  };

  const addHashtag = (hashtag: string) => {
    if (hashtag && !newPost.hashtags.includes(hashtag)) {
      setNewPost(prev => ({
        ...prev,
        hashtags: [...prev.hashtags, hashtag]
      }));
    }
  };

  const removeHashtag = (hashtag: string) => {
    setNewPost(prev => ({
      ...prev,
      hashtags: prev.hashtags.filter(tag => tag !== hashtag)
    }));
  };

  if (loading) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>
          Social Scheduler
        </Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' }, gap: 3 }}>
          {[1, 2, 3].map(i => (
            <Skeleton key={i} variant="rectangular" height={200} />
          ))}
        </Box>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Social Scheduler</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setCreateDialogOpen(true)}
          disabled={characters.length === 0}
        >
          Schedule Post
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {characters.length === 0 && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          No trained characters available. Complete character training first to schedule posts.
        </Alert>
      )}

      <Paper sx={{ mb: 3 }}>
        <Tabs value={currentTab} onChange={(e, v) => setCurrentTab(v)}>
          <Tab icon={<ScheduleIcon />} label={`Scheduled (${scheduledPosts.filter(p => p.status === 'scheduled').length})`} />
          <Tab icon={<SendIcon />} label={`Posted (${scheduledPosts.filter(p => p.status === 'posted').length})`} />
          <Tab icon={<TrendingIcon />} label="Analytics" />
        </Tabs>
      </Paper>

      {/* Scheduled Posts Tab */}
      {currentTab === 0 && (
        <Box>
          {scheduledPosts.filter(post => post.status === 'scheduled').length === 0 ? (
            <Card>
              <CardContent sx={{ textAlign: 'center', py: 6 }}>
                <ScheduleIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
                <Typography variant="h6" color="text.secondary" gutterBottom>
                  No scheduled posts
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                  Create your first scheduled post to automate your social media presence
                </Typography>
                <Button 
                  variant="contained" 
                  startIcon={<AddIcon />}
                  onClick={() => setCreateDialogOpen(true)}
                  disabled={characters.length === 0}
                >
                  Schedule First Post
                </Button>
              </CardContent>
            </Card>
          ) : (
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(2, 1fr)', lg: 'repeat(3, 1fr)' }, gap: 3 }}>
              {scheduledPosts
                .filter(post => post.status === 'scheduled')
                .map((post) => (
                  <Card key={post.id}>
                    <CardContent>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Avatar sx={{ bgcolor: getPlatformColor(post.platform), width: 32, height: 32 }}>
                            {getPlatformIcon(post.platform)}
                          </Avatar>
                          <Typography variant="subtitle2">
                            {post.platform.charAt(0).toUpperCase() + post.platform.slice(1)}
                          </Typography>
                        </Box>
                        <Chip 
                          label={post.status} 
                          color={getStatusColor(post.status) as any}
                          size="small"
                        />
                      </Box>

                      <Typography variant="body2" gutterBottom>
                        <strong>{post.character_name}</strong>
                      </Typography>

                      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        {post.content.length > 100 ? `${post.content.substring(0, 100)}...` : post.content}
                      </Typography>

                      {post.hashtags.length > 0 && (
                        <Box sx={{ mb: 2 }}>
                          {post.hashtags.slice(0, 3).map((tag) => (
                            <Chip key={tag} label={`#${tag}`} size="small" sx={{ mr: 0.5, mb: 0.5 }} />
                          ))}
                          {post.hashtags.length > 3 && (
                            <Chip label={`+${post.hashtags.length - 3} more`} size="small" variant="outlined" />
                          )}
                        </Box>
                      )}

                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <ClockIcon fontSize="small" color="action" />
                        <Typography variant="caption" color="text.secondary">
                          {dayjs(post.scheduled_time).format('MMM D, YYYY h:mm A')}
                        </Typography>
                      </Box>

                      {post.media_url && (
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          {post.media_type === 'image' ? <ImageIcon fontSize="small" /> : <VideoIcon fontSize="small" />}
                          <Typography variant="caption" color="text.secondary">
                            {post.media_type} attached
                          </Typography>
                        </Box>
                      )}

                      {post.music_track && (
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
                          <MusicIcon fontSize="small" />
                          <Typography variant="caption" color="text.secondary">
                            {post.music_track}
                          </Typography>
                        </Box>
                      )}
                    </CardContent>
                    
                    <CardActions>
                      <IconButton size="small" color="primary">
                        <EditIcon />
                      </IconButton>
                      <IconButton size="small" color="error" onClick={() => handleDeletePost(post.id)}>
                        <DeleteIcon />
                      </IconButton>
                    </CardActions>
                  </Card>
                ))}
            </Box>
          )}
        </Box>
      )}

      {/* Posted Tab */}
      {currentTab === 1 && (
        <Box>
          <Typography variant="h6" gutterBottom>
            Posted Content
          </Typography>
          <Typography variant="body2" color="text.secondary">
            View your successfully posted content and engagement metrics.
          </Typography>
        </Box>
      )}

      {/* Analytics Tab */}
      {currentTab === 2 && (
        <Box>
          <Typography variant="h6" gutterBottom>
            Social Media Analytics
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Track performance metrics, engagement rates, and optimal posting times.
          </Typography>
        </Box>
      )}

      {/* Create Post Dialog */}
      <Dialog open={createDialogOpen} onClose={() => setCreateDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Schedule New Post</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'grid', gap: 3, mt: 1 }}>
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 3 }}>
              <FormControl fullWidth>
                <InputLabel>Platform</InputLabel>
                <Select
                  value={newPost.platform}
                  onChange={(e) => setNewPost(prev => ({ ...prev, platform: e.target.value as any }))}
                  label="Platform"
                >
                  <MenuItem value="instagram">
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <InstagramIcon /> Instagram
                    </Box>
                  </MenuItem>
                  <MenuItem value="twitter">
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <TwitterIcon /> Twitter
                    </Box>
                  </MenuItem>
                  <MenuItem value="facebook">
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <FacebookIcon /> Facebook
                    </Box>
                  </MenuItem>
                </Select>
              </FormControl>

              <FormControl fullWidth>
                <InputLabel>Character</InputLabel>
                <Select
                  value={newPost.character_id}
                  onChange={(e) => setNewPost(prev => ({ ...prev, character_id: e.target.value }))}
                  label="Character"
                >
                  {characters.map((character) => (
                    <MenuItem key={character.id} value={character.id}>
                      {character.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>

            <TextField
              fullWidth
              multiline
              rows={4}
              label="Post Content"
              value={newPost.content}
              onChange={(e) => setNewPost(prev => ({ ...prev, content: e.target.value }))}
              placeholder="Write your post content here..."
            />

            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 3 }}>
              <TextField
                fullWidth
                label="Media URL (optional)"
                value={newPost.media_url}
                onChange={(e) => setNewPost(prev => ({ ...prev, media_url: e.target.value }))}
                placeholder="https://..."
              />

              <LocalizationProvider dateAdapter={AdapterDayjs}>
                <DateTimePicker
                  label="Schedule Time"
                  value={newPost.scheduled_time}
                  onChange={(newValue) => setNewPost(prev => ({ ...prev, scheduled_time: newValue ? dayjs(newValue) : dayjs() }))}
                  minDateTime={dayjs()}
                  slotProps={{ textField: { fullWidth: true } }}
                />
              </LocalizationProvider>
            </Box>

            <TextField
              fullWidth
              label="Music Track (for Instagram Reels/Stories)"
              value={newPost.music_track}
              onChange={(e) => setNewPost(prev => ({ ...prev, music_track: e.target.value }))}
              placeholder="Enter music track name"
            />

            <Box>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                {newPost.hashtags.map((hashtag) => (
                  <Chip
                    key={hashtag}
                    label={`#${hashtag}`}
                    onDelete={() => removeHashtag(hashtag)}
                    size="small"
                  />
                ))}
              </Box>
              <TextField
                fullWidth
                label="Add Hashtags (press Enter)"
                placeholder="Type hashtag and press Enter"
                onKeyPress={(e) => {
                  if (e.key === 'Enter') {
                    const input = e.target as HTMLInputElement;
                    const hashtag = input.value.trim().replace('#', '');
                    if (hashtag) {
                      addHashtag(hashtag);
                      input.value = '';
                    }
                    e.preventDefault();
                  }
                }}
              />
            </Box>

            <Box>
              <FormControlLabel
                control={
                  <Switch
                    checked={newPost.auto_hashtags}
                    onChange={(e) => setNewPost(prev => ({ ...prev, auto_hashtags: e.target.checked }))}
                  />
                }
                label="Auto-generate relevant hashtags"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={newPost.trending_music}
                    onChange={(e) => setNewPost(prev => ({ ...prev, trending_music: e.target.checked }))}
                  />
                }
                label="Use trending music (Instagram)"
              />
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
          <Button 
            onClick={handleCreatePost} 
            variant="contained"
            disabled={!newPost.platform || !newPost.character_id || !newPost.content}
          >
            Schedule Post
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default SocialScheduler;
