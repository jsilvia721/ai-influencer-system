#!/usr/bin/env python3
"""Test script for the AI Influencer System."""
import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from src.utils.config import config
from src.utils.storage import storage
from src.image_generation.generator import image_generator
from src.video_generation.generator import video_generator
from src.orchestration.pipeline import content_pipeline


def test_configuration():
    """Test configuration loading."""
    logger.info("🔧 Testing configuration...")
    
    try:
        device = config.get("models.stable_diffusion.device")
        trigger_word = config.get("lora.trigger_word")
        
        logger.info(f"Device: {device}")
        logger.info(f"Trigger word: {trigger_word}")
        logger.success("✅ Configuration loaded successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Configuration test failed: {e}")
        return False


def test_storage():
    """Test storage functionality."""
    logger.info("💾 Testing storage system...")
    
    try:
        storage.ensure_local_dirs()
        loras = storage.list_loras()
        
        logger.info(f"Available LoRAs: {len(loras)}")
        for lora in loras[:3]:  # Show first 3
            logger.info(f"  - {lora}")
        
        logger.success("✅ Storage system working")
        return True
    except Exception as e:
        logger.error(f"❌ Storage test failed: {e}")
        return False


def test_image_generation():
    """Test image generation (without LoRA)."""
    logger.info("🎨 Testing image generation...")
    
    try:
        # Test basic image generation without LoRA
        test_prompt = "portrait of a woman, professional headshot, studio lighting"
        
        logger.info(f"Generating test image with prompt: '{test_prompt}'")
        
        image_path = image_generator.generate_image(
            prompt=test_prompt,
            save_image=True,
            filename="test_image.png",
            num_inference_steps=10,  # Fast test
            seed=42  # Reproducible
        )
        
        if os.path.exists(image_path):
            logger.success(f"✅ Image generated successfully: {image_path}")
            return True
        else:
            logger.error("❌ Image file not found after generation")
            return False
            
    except Exception as e:
        logger.error(f"❌ Image generation test failed: {e}")
        return False


def test_video_generation():
    """Test video generation."""
    logger.info("🎬 Testing video generation...")
    
    try:
        # Create a simple test image first
        from PIL import Image
        import numpy as np
        
        # Create a simple gradient image for testing
        test_image = Image.fromarray(
            np.random.randint(0, 255, (512, 512, 3), dtype=np.uint8)
        )
        test_image_path = storage.local_base_path / "images" / "test_video_input.png"
        test_image.save(test_image_path)
        
        logger.info("Generating test video from image...")
        
        video_path = video_generator.generate_video_from_image(
            image=test_image_path,
            save_video=True,
            filename="test_video.mp4",
            num_frames=14,  # Short test
            num_inference_steps=10  # Fast test
        )
        
        if os.path.exists(video_path):
            logger.success(f"✅ Video generated successfully: {video_path}")
            return True
        else:
            logger.error("❌ Video file not found after generation")
            return False
            
    except Exception as e:
        logger.error(f"❌ Video generation test failed: {e}")
        return False


def test_content_pipeline():
    """Test the content pipeline with mock LoRA."""
    logger.info("🎭 Testing content pipeline...")
    
    try:
        # Test with available LoRA or skip if none
        loras = storage.list_loras()
        
        if not loras:
            logger.warning("⚠️ No LoRA models found, skipping pipeline test")
            logger.info("💡 Add LoRA models to data/loras/ to test full pipeline")
            return True
        
        test_lora = loras[0]
        logger.info(f"Testing with LoRA: {test_lora}")
        
        # Test simple content creation
        result = content_pipeline.create_content_from_concept(
            concept="coffee",
            lora_name=test_lora,
            num_videos=1  # Just one for testing
        )
        
        if result["success"]:
            logger.success("✅ Content pipeline test successful")
            logger.info(f"Generated video: {result['final_video']}")
            return True
        else:
            logger.error("❌ Content pipeline test failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Content pipeline test failed: {e}")
        return False


def run_all_tests():
    """Run all system tests."""
    logger.info("🚀 Starting AI Influencer System Tests")
    logger.info("=" * 50)
    
    tests = [
        ("Configuration", test_configuration),
        ("Storage", test_storage),
        ("Image Generation", test_image_generation),
        ("Video Generation", test_video_generation),
        ("Content Pipeline", test_content_pipeline),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n🧪 Running {test_name} test...")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("📊 Test Results Summary:")
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    total = len(results)
    logger.info(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.success("🎉 All tests passed! System is ready to use.")
    else:
        logger.warning("⚠️ Some tests failed. Check the logs above for details.")
    
    return passed == total


if __name__ == "__main__":
    # Set up logging
    logger.remove()  # Remove default handler
    logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
    
    # Run tests
    success = run_all_tests()
    
    if success:
        logger.info("\n💡 Ready to start the system:")
        logger.info("   API Server: python -m src.api.main")
        logger.info("   Web UI: http://localhost:8000/docs")
    else:
        logger.error("\n🔧 Fix the failing tests before using the system")
        sys.exit(1)
