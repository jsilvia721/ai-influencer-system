#!/usr/bin/env python3
"""
Face Identity System for AI Video Generation
Extracts and preserves facial embeddings for consistent person identity
"""

import os
import cv2
import numpy as np
import torch
import pickle
from PIL import Image
from typing import List, Dict, Tuple, Optional
import insightface
from insightface.app import FaceAnalysis
from insightface.data import get_image as ins_get_image
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FaceIdentityPreserver:
    """
    System for extracting and preserving facial identity across video generation
    """
    
    def __init__(self, model_name='buffalo_l'):
        """
        Initialize the face analysis system
        
        Args:
            model_name: InsightFace model to use ('buffalo_l' for high accuracy)
        """
        self.app = FaceAnalysis(name=model_name)
        self.app.prepare(ctx_id=0, det_size=(640, 640))  # Use GPU if available
        self.identity_db = {}  # Store person identities
        
    def extract_face_embedding(self, image_path: str) -> Optional[Dict]:
        """
        Extract face embedding from a single image
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary containing face data or None if no face found
        """
        try:
            # Load image
            img = cv2.imread(image_path)
            if img is None:
                logger.error(f"Could not load image: {image_path}")
                return None
            
            # Detect faces
            faces = self.app.get(img)
            
            if len(faces) == 0:
                logger.warning(f"No faces detected in {image_path}")
                return None
            
            # Use the largest face (primary subject)
            face = max(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))
            
            face_data = {
                'embedding': face.embedding,
                'bbox': face.bbox,
                'kps': face.kps,  # keypoints
                'det_score': face.det_score,
                'image_shape': img.shape,
                'source_image': image_path
            }
            
            logger.info(f"Extracted face embedding from {image_path} (confidence: {face.det_score:.3f})")
            return face_data
            
        except Exception as e:
            logger.error(f"Error processing {image_path}: {str(e)}")
            return None
    
    def create_person_profile(self, person_id: str, image_paths: List[str]) -> Dict:
        """
        Create a comprehensive identity profile from multiple images
        
        Args:
            person_id: Unique identifier for the person
            image_paths: List of image paths showing the person
            
        Returns:
            Person profile dictionary
        """
        logger.info(f"Creating identity profile for {person_id} from {len(image_paths)} images")
        
        embeddings = []
        face_data_list = []
        
        for img_path in image_paths:
            face_data = self.extract_face_embedding(img_path)
            if face_data:
                embeddings.append(face_data['embedding'])
                face_data_list.append(face_data)
        
        if len(embeddings) == 0:
            logger.error(f"No valid face embeddings found for {person_id}")
            return None
        
        # Calculate average embedding for better identity representation
        avg_embedding = np.mean(embeddings, axis=0)
        
        # Calculate embedding consistency (lower std = more consistent identity)
        embedding_std = np.std(embeddings, axis=0).mean()
        
        person_profile = {
            'person_id': person_id,
            'avg_embedding': avg_embedding,
            'all_embeddings': embeddings,
            'face_data': face_data_list,
            'embedding_consistency': embedding_std,
            'num_reference_images': len(embeddings),
            'reference_images': image_paths
        }
        
        # Store in identity database
        self.identity_db[person_id] = person_profile
        
        logger.info(f"Created profile for {person_id}: {len(embeddings)} faces, consistency: {embedding_std:.4f}")
        return person_profile
    
    def find_similar_identity(self, target_embedding: np.ndarray, threshold: float = 0.6) -> Optional[str]:
        """
        Find the most similar identity in the database
        
        Args:
            target_embedding: Face embedding to match
            threshold: Similarity threshold (higher = more strict)
            
        Returns:
            Person ID of best match or None
        """
        best_match = None
        best_similarity = 0
        
        for person_id, profile in self.identity_db.items():
            # Calculate cosine similarity
            similarity = np.dot(target_embedding, profile['avg_embedding']) / (
                np.linalg.norm(target_embedding) * np.linalg.norm(profile['avg_embedding'])
            )
            
            if similarity > best_similarity and similarity > threshold:
                best_similarity = similarity
                best_match = person_id
        
        if best_match:
            logger.info(f"Matched identity: {best_match} (similarity: {best_similarity:.3f})")
        
        return best_match
    
    def save_identity_database(self, filepath: str):
        """Save the identity database to disk"""
        try:
            with open(filepath, 'wb') as f:
                pickle.dump(self.identity_db, f)
            logger.info(f"Saved identity database to {filepath}")
        except Exception as e:
            logger.error(f"Error saving database: {str(e)}")
    
    def load_identity_database(self, filepath: str):
        """Load identity database from disk"""
        try:
            with open(filepath, 'rb') as f:
                self.identity_db = pickle.load(f)
            logger.info(f"Loaded identity database from {filepath} ({len(self.identity_db)} identities)")
        except Exception as e:
            logger.error(f"Error loading database: {str(e)}")
    
    def get_identity_summary(self) -> Dict:
        """Get summary of all stored identities"""
        summary = {}
        for person_id, profile in self.identity_db.items():
            summary[person_id] = {
                'num_images': profile['num_reference_images'],
                'consistency': profile['embedding_consistency'],
                'reference_images': profile['reference_images']
            }
        return summary

def main():
    """
    Example usage of the Face Identity System
    """
    # Initialize the system
    face_system = FaceIdentityPreserver()
    
    # Example: Create identity profiles
    # You would replace these with actual image paths
    sample_images = [
        "/path/to/person1_image1.jpg",
        "/path/to/person1_image2.jpg",
        "/path/to/person1_image3.jpg"
    ]
    
    # Create person profile
    # profile = face_system.create_person_profile("model_alice", sample_images)
    
    # Save database
    # face_system.save_identity_database("identity_database.pkl")
    
    print("Face Identity System initialized successfully!")
    print("Ready to process reference images and create identity profiles.")

if __name__ == "__main__":
    main()
