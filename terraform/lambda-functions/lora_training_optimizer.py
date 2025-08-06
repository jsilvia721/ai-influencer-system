import json
import boto3
import os
from datetime import datetime

class LoRATrainingOptimizer:
    """
    Smart LoRA training cost optimizer that chooses the best platform
    based on volume, budget, and performance requirements
    """
    
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.secrets_client = boto3.client('secretsmanager')
        self.bucket_name = os.environ.get('S3_BUCKET_NAME')
        
        # Cost per training job (estimated)
        self.platform_costs = {
            'replicate': 1.50,      # $1.50 per job (reliable, fast)
            'runpod_serverless': 0.50,  # $0.50 per job (flexible)
            'runpod_dedicated': 0.25,   # $0.25 per job (bulk discount)
            'aws_batch': 0.75       # In-house option for future
        }
        
        # Platform capabilities and limits
        self.platform_limits = {
            'replicate': {'max_concurrent': 3, 'reliability': 0.95},
            'runpod_serverless': {'max_concurrent': 5, 'reliability': 0.85},
            'runpod_dedicated': {'max_concurrent': 10, 'reliability': 0.90},
            'aws_batch': {'max_concurrent': 20, 'reliability': 0.80}
        }
    
    def recommend_platform(self, training_request):
        """
        Recommend the best platform based on request parameters
        
        Args:
            training_request: {
                'character_count': int,
                'priority': 'low'|'medium'|'high',
                'budget_per_character': float,
                'timeline_hours': int
            }
        """
        character_count = training_request.get('character_count', 1)
        priority = training_request.get('priority', 'medium')
        budget_per_character = training_request.get('budget_per_character', 2.0)
        timeline_hours = training_request.get('timeline_hours', 24)
        
        # Get current usage stats
        monthly_stats = self._get_monthly_training_stats()
        
        recommendations = []
        
        # Replicate: Best for small volumes and high priority
        if character_count <= 10 and priority in ['medium', 'high']:
            replicate_cost = character_count * self.platform_costs['replicate']
            if replicate_cost <= budget_per_character * character_count:
                recommendations.append({
                    'platform': 'replicate',
                    'cost': replicate_cost,
                    'estimated_time_hours': character_count * 0.5,  # 30 min per character
                    'reliability': 0.95,
                    'pros': ['Fastest setup', 'Highest reliability', 'Zero maintenance'],
                    'cons': ['Higher cost per unit', 'Limited concurrent jobs']
                })
        
        # RunPod Serverless: Good middle ground
        if character_count <= 20:
            runpod_cost = character_count * self.platform_costs['runpod_serverless']
            if runpod_cost <= budget_per_character * character_count:
                recommendations.append({
                    'platform': 'runpod_serverless',
                    'cost': runpod_cost,
                    'estimated_time_hours': character_count * 0.6,  # 36 min per character
                    'reliability': 0.85,
                    'pros': ['Cost effective', 'More concurrent jobs', 'Custom containers'],
                    'cons': ['Setup complexity', 'Lower reliability than Replicate']
                })
        
        # Bulk recommendation for high volume
        if monthly_stats['total_characters'] > 30:
            recommendations.append({
                'platform': 'bulk_discount',
                'message': 'Consider negotiating bulk pricing with RunPod or moving to dedicated instances',
                'estimated_savings': f"${monthly_stats['total_characters'] * 0.5:.2f}/month"
            })
        
        # Sort by cost-effectiveness (cost per character / reliability)
        recommendations.sort(key=lambda x: x.get('cost', 999) / x.get('reliability', 0.1))
        
        return {
            'recommended_platform': recommendations[0] if recommendations else None,
            'all_options': recommendations,
            'monthly_stats': monthly_stats,
            'cost_analysis': self._generate_cost_analysis(character_count)
        }
    
    def _get_monthly_training_stats(self):
        """Get training statistics for the current month"""
        try:
            # Query S3 for training job logs from current month
            current_month = datetime.utcnow().strftime('%Y-%m')
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=f'training/stats/{current_month}/'
            )
            
            # Calculate stats (simplified - in production you'd aggregate from logs)
            total_jobs = len(response.get('Contents', []))
            
            return {
                'total_characters': total_jobs,
                'month': current_month,
                'average_cost_per_character': 1.2,  # Would calculate from actual data
                'success_rate': 0.92
            }
        except Exception as e:
            print(f"Error getting training stats: {e}")
            return {
                'total_characters': 0,
                'month': datetime.utcnow().strftime('%Y-%m'),
                'average_cost_per_character': 0,
                'success_rate': 0
            }
    
    def _generate_cost_analysis(self, character_count):
        """Generate detailed cost breakdown for different scenarios"""
        
        scenarios = {
            'current_month': character_count,
            'next_3_months': character_count * 3,
            'scale_10x': character_count * 10
        }
        
        analysis = {}
        
        for scenario, count in scenarios.items():
            analysis[scenario] = {
                'replicate': {
                    'total_cost': count * self.platform_costs['replicate'],
                    'per_character': self.platform_costs['replicate']
                },
                'runpod': {
                    'total_cost': count * self.platform_costs['runpod_serverless'],
                    'per_character': self.platform_costs['runpod_serverless']
                },
                'savings_vs_replicate': (count * (self.platform_costs['replicate'] - self.platform_costs['runpod_serverless']))
            }
        
        return analysis
    
    def get_training_budget_recommendation(self, monthly_characters, growth_rate=2.0):
        """
        Recommend training budget based on projected usage
        
        Args:
            monthly_characters: Expected characters per month
            growth_rate: Monthly growth multiplier
        """
        
        # 6-month projection
        projections = []
        current_chars = monthly_characters
        
        for month in range(6):
            month_cost_replicate = current_chars * self.platform_costs['replicate']
            month_cost_runpod = current_chars * self.platform_costs['runpod_serverless']
            
            projections.append({
                'month': month + 1,
                'characters': current_chars,
                'replicate_cost': month_cost_replicate,
                'runpod_cost': month_cost_runpod,
                'recommended_platform': 'replicate' if current_chars < 15 else 'runpod'
            })
            
            current_chars = int(current_chars * growth_rate)
        
        # Calculate breakeven point for in-house solution
        infrastructure_cost = 500  # Monthly AWS infrastructure cost
        in_house_per_character = 0.3  # Estimated cost per character in-house
        
        breakeven_characters = infrastructure_cost / (self.platform_costs['replicate'] - in_house_per_character)
        
        return {
            'projections': projections,
            'breakeven_analysis': {
                'characters_per_month_for_in_house': int(breakeven_characters),
                'infrastructure_monthly_cost': infrastructure_cost,
                'estimated_timeline_to_breakeven': f"{breakeven_characters / monthly_characters:.1f} months"
            },
            'recommendations': {
                'phase_1': 'Use Replicate for first 0-10 characters',
                'phase_2': 'Switch to RunPod at 10-50 characters/month',
                'phase_3': 'Consider in-house at 50+ characters/month'
            }
        }

def handler(event, context):
    """
    Lambda handler for training cost optimization
    """
    try:
        optimizer = LoRATrainingOptimizer()
        
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        action = body.get('action')
        
        if action == 'recommend_platform':
            result = optimizer.recommend_platform(body.get('training_request', {}))
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(result)
            }
        
        elif action == 'budget_analysis':
            result = optimizer.get_training_budget_recommendation(
                monthly_characters=body.get('monthly_characters', 5),
                growth_rate=body.get('growth_rate', 1.5)
            )
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(result)
            }
        
        else:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Invalid action',
                    'available_actions': ['recommend_platform', 'budget_analysis']
                })
            }
    
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': str(e)
            })
        }
