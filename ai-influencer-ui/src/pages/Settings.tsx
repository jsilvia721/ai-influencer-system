import React from 'react';
import { 
  Box, 
  Typography, 
  Card, 
  CardContent,
  Button,
  Alert
} from '@mui/material';

const Settings: React.FC = () => {
  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Settings
      </Typography>
      
      <Alert severity="info" sx={{ mb: 3 }}>
        Settings interface coming soon! This will allow you to configure API keys and system preferences.
      </Alert>

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            System Configuration
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            Configure API keys for Replicate, Flux, Kling, and social media platforms.
          </Typography>
          <Button variant="contained" disabled>
            Configure Settings (Coming Soon)
          </Button>
        </CardContent>
      </Card>
    </Box>
  );
};

export default Settings;
