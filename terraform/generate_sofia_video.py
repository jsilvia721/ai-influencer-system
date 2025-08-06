#!/usr/bin/env python3
"""
Sofia Video Generator - Command Line Interface
Generate Sofia videos with custom activity descriptions
"""

import sys
from sofia_video_system import SofiaVideoSystem
import logging

def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_sofia_video.py \"<activity_description>\" [motion_intensity]")
        print("\nExamples:")
        print('  python generate_sofia_video.py "Sofia waving at the camera"')
        print('  python generate_sofia_video.py "Sofia doing a fashion pose" high')
        print('  python generate_sofia_video.py "Sofia smiling confidently" low')
        print("\nMotion intensity options: low, medium (default), high")
        return
    
    activity_description = sys.argv[1]
    motion_intensity = sys.argv[2] if len(sys.argv) > 2 else "medium"
    
    try:
        print(f"🎬 Generating Sofia video: '{activity_description}'")
        print(f"📸 Motion intensity: {motion_intensity}")
        print("⏳ This will take about 2-3 minutes...")
        
        # Initialize Sofia system (reuses existing identity profile)
        sofia_system = SofiaVideoSystem()
        
        # Generate video
        video_path = sofia_system.generate_sofia_video(
            activity_description=activity_description,
            motion_intensity=motion_intensity,
            seed=42  # Fixed seed for consistency
        )
        
        print(f"\n🎉 SUCCESS! Sofia video generated: {video_path}")
        print("📱 Ready for social media!")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return 1

if __name__ == "__main__":
    main()
