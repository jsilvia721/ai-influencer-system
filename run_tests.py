#!/usr/bin/env python3
"""
Test runner for training image generator tests.
Run this to execute all tests without making actual API calls.
"""

import subprocess
import sys
import os

def run_tests():
    """Run the training image generator tests"""
    
    # Change to the project directory
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)
    
    print("Running Training Image Generator Tests")
    print("=" * 50)
    print("These tests mock all Replicate API calls to avoid charges.")
    print("They test the retry logic and progress tracking functionality.")
    print("=" * 50)
    
    # Install required test dependencies if not already installed
    try:
        import pytest
    except ImportError:
        print("Installing pytest...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pytest"], check=True)
    
    # Run the tests
    test_file = "tests/test_training_image_generator.py"
    
    if not os.path.exists(test_file):
        print(f"Error: Test file {test_file} not found!")
        return 1
    
    # Run tests with verbose output
    cmd = [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short"]
    
    print(f"Running command: {' '.join(cmd)}")
    print()
    
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print()
        print("✅ All tests passed!")
        print("The retry mechanism is working correctly.")
    else:
        print()
        print("❌ Some tests failed.")
        print("Check the output above for details.")
    
    return result.returncode

if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
