import React from 'react';
import { 
  Box, 
  Typography, 
  Card, 
  CardContent,
  Button,
  Alert
} from '@mui/material';

const Analytics: React.FC = () => {
  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Analytics
      </Typography>
      
      <Alert severity="info" sx={{ mb: 3 }}>
        Analytics dashboard coming soon! This will show performance metrics for your AI influencer content.
      </Alert>

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Performance Metrics
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            Track engagement, reach, and performance of your AI-generated social media content.
          </Typography>
          <Button variant="contained" disabled>
            View Analytics (Coming Soon)
          </Button>
        </CardContent>
      </Card>
    </Box>
  );
};

export default Analytics;
