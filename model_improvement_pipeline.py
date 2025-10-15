#!/usr/bin/env python3
"""
Automated Model Improvement Pipeline
Processes feedback, creates training data, and triggers model updates
"""

import json
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging
import boto3
import os
from enhanced_feedback_system import EnhancedFeedbackSystem
from dataset_manager import DatasetManager

class ModelImprovementPipeline:
    """Automated pipeline for processing feedback and improving AI models"""
    
    def __init__(self, feedback_system: EnhancedFeedbackSystem, 
                 dataset_manager: DatasetManager,
                 s3_bucket: str = "ai-training-data",
                 improvement_threshold: float = 0.3):
        self.feedback_system = feedback_system
        self.dataset_manager = dataset_manager
        self.s3_bucket = s3_bucket
        self.improvement_threshold = improvement_threshold
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # AWS clients
        try:
            self.s3_client = boto3.client('s3')
            self.bedrock_client = boto3.client('bedrock-runtime')
        except Exception as e:
            self.logger.warning(f"AWS clients not available: {e}")
            self.s3_client = None
            self.bedrock_client = None
    
    def run_improvement_cycle(self, days_back: int = 7) -> Dict:
        """Run complete improvement cycle"""
        self.logger.info("🚀 Starting model improvement cycle...")
        
        results = {
            "cycle_id": f"improvement_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "started_at": datetime.now().isoformat(),
            "days_analyzed": days_back,
            "steps_completed": [],
            "improvements_identified": [],
            "training_data_created": 0,
            "recommendations": [],
            "success": False
        }
        
        try:
            # Step 1: Analyze recent feedback
            self.logger.info("📊 Step 1: Analyzing recent feedback...")
            feedback_analysis = self._analyze_recent_feedback(days_back)
            results["steps_completed"].append("feedback_analysis")
            results["feedback_analysis"] = feedback_analysis
            
            # Step 2: Identify improvement areas
            self.logger.info("🔍 Step 2: Identifying improvement areas...")
            improvement_areas = self._identify_improvement_areas(feedback_analysis)
            results["steps_completed"].append("improvement_identification")
            results["improvements_identified"] = improvement_areas
            
            # Step 3: Create training data
            self.logger.info("📚 Step 3: Creating training data...")
            training_data_count = self._create_training_data(improvement_areas)
            results["steps_completed"].append("training_data_creation")
            results["training_data_created"] = training_data_count
            
            # Step 4: Generate recommendations
            self.logger.info("💡 Step 4: Generating recommendations...")
            recommendations = self._generate_improvement_recommendations(improvement_areas)
            results["steps_completed"].append("recommendation_generation")
            results["recommendations"] = recommendations
            
            # Step 5: Prepare model update (if applicable)
            if training_data_count > 10:  # Minimum threshold for model update
                self.logger.info("🤖 Step 5: Preparing model update...")
                model_update_info = self._prepare_model_update()
                results["steps_completed"].append("model_update_preparation")
                results["model_update_info"] = model_update_info
            
            results["success"] = True
            results["completed_at"] = datetime.now().isoformat()
            
            self.logger.info("✅ Model improvement cycle completed successfully!")
            
        except Exception as e:
            self.logger.error(f"❌ Error in improvement cycle: {e}")
            results["error"] = str(e)
            results["completed_at"] = datetime.now().isoformat()
        
        return results
    
    def _analyze_recent_feedback(self, days_back: int) -> Dict:
        """Analyze feedback from recent days"""
        cutoff_date = (datetime.now() - timedelta(days=days_back)).isoformat()
        
        conn = sqlite3.connect(self.feedback_system.db_path)
        cursor = conn.cursor()
        
        # Get recent feedback statistics
        cursor.execute('''
            SELECT 
                COUNT(*) as total_feedback,
                AVG(overall_rating) as avg_rating,
                COUNT(CASE WHEN overall_rating <= 2 THEN 1 END) as poor_ratings,
                COUNT(CASE WHEN overall_rating >= 4 THEN 1 END) as good_ratings,
                COUNT(CASE WHEN suggested_improvement IS NOT NULL AND suggested_improvement != '' THEN 1 END) as has_suggestions
            FROM feedback f
            JOIN interactions i ON f.interaction_id = i.id
            WHERE i.timestamp >= ?
        ''', (cutoff_date,))
        
        stats = cursor.fetchone()
        
        # Get category performance
        cursor.execute('''
            SELECT 
                i.query_type,
                COUNT(*) as feedback_count,
                AVG(f.overall_rating) as avg_rating,
                COUNT(CASE WHEN f.overall_rating <= 2 THEN 1 END) as poor_count
            FROM feedback f
            JOIN interactions i ON f.interaction_id = i.id
            WHERE i.timestamp >= ?
            GROUP BY i.query_type
            ORDER BY avg_rating ASC
        ''', (cutoff_date,))
        
        category_performance = [
            {
                "category": row[0],
                "feedback_count": row[1], 
                "avg_rating": round(row[2], 2),
                "poor_ratings": row[3],
                "needs_attention": row[2] < 3.0 or row[3] > 0
            }
            for row in cursor.fetchall()
        ]
        
        # Get common improvement suggestions
        cursor.execute('''
            SELECT suggested_improvement, COUNT(*) as frequency
            FROM feedback f
            JOIN interactions i ON f.interaction_id = i.id
            WHERE i.timestamp >= ? 
            AND suggested_improvement IS NOT NULL 
            AND suggested_improvement != ''
            GROUP BY suggested_improvement
            ORDER BY frequency DESC
            LIMIT 10
        ''', (cutoff_date,))
        
        common_suggestions = [
            {"suggestion": row[0], "frequency": row[1]}
            for row in cursor.fetchall()
        ]
        
        conn.close()
        
        return {
            "analysis_period": f"{days_back} days",
            "total_feedback": stats[0],
            "average_rating": round(stats[1] or 0, 2),
            "poor_ratings": stats[2],
            "good_ratings": stats[3],
            "has_suggestions": stats[4],
            "category_performance": category_performance,
            "common_suggestions": common_suggestions,
            "improvement_needed": stats[1] < 3.5 if stats[1] else False
        }
    
    def _identify_improvement_areas(self, feedback_analysis: Dict) -> List[Dict]:
        """Identify specific areas that need improvement"""
        improvement_areas = []
        
        # Categories with poor performance
        for category in feedback_analysis["category_performance"]:
            if category["needs_attention"]:
                improvement_areas.append({
                    "type": "category_performance",
                    "category": category["category"],
                    "issue": f"Low average rating: {category['avg_rating']}/5",
                    "severity": "HIGH" if category["avg_rating"] < 2.5 else "MEDIUM",
                    "affected_interactions": category["feedback_count"],
                    "poor_ratings": category["poor_ratings"]
                })
        
        # Common suggestions indicate systematic issues
        for suggestion in feedback_analysis["common_suggestions"]:
            if suggestion["frequency"] >= 2:  # Mentioned multiple times
                improvement_areas.append({
                    "type": "user_suggestion",
                    "issue": suggestion["suggestion"],
                    "frequency": suggestion["frequency"],
                    "severity": "HIGH" if suggestion["frequency"] >= 3 else "MEDIUM"
                })
        
        # Overall performance issues
        if feedback_analysis["improvement_needed"]:
            improvement_areas.append({
                "type": "overall_performance",
                "issue": f"Overall rating below threshold: {feedback_analysis['average_rating']}/5",
                "severity": "HIGH",
                "total_feedback": feedback_analysis["total_feedback"]
            })
        
        return improvement_areas
    
    def _create_training_data(self, improvement_areas: List[Dict]) -> int:
        """Create training data based on identified improvement areas"""
        training_data_created = 0
        
        conn = sqlite3.connect(self.feedback_system.db_path)
        cursor = conn.cursor()
        
        for area in improvement_areas:
            if area["type"] == "category_performance":
                # Get low-rated interactions in this category
                cursor.execute('''
                    SELECT i.id, i.user_question, i.ai_response, f.overall_rating, f.suggested_improvement
                    FROM interactions i
                    JOIN feedback f ON i.id = f.interaction_id
                    WHERE i.query_type = ? AND f.overall_rating <= 2
                ''', (area["category"],))
                
                for row in cursor.fetchall():
                    interaction_id, question, response, rating, suggestion = row
                    
                    # Create training data entry
                    self._create_training_entry(
                        question, suggestion or "", response, rating, area["category"]
                    )
                    training_data_created += 1
            
            elif area["type"] == "user_suggestion":
                # Find interactions related to this suggestion
                cursor.execute('''
                    SELECT i.id, i.user_question, i.ai_response, f.overall_rating
                    FROM interactions i
                    JOIN feedback f ON i.id = f.interaction_id
                    WHERE f.suggested_improvement LIKE ?
                ''', (f"%{area['issue']}%",))
                
                for row in cursor.fetchall():
                    interaction_id, question, response, rating = row
                    
                    self._create_training_entry(
                        question, area["issue"], response, rating, "user_suggested"
                    )
                    training_data_created += 1
        
        conn.close()
        return training_data_created
    
    def _create_training_entry(self, question: str, ideal_answer: str, 
                             actual_answer: str, rating: int, category: str):
        """Create a single training data entry"""
        conn = sqlite3.connect(self.feedback_system.db_path)
        cursor = conn.cursor()
        
        training_id = f"auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(question)}"
        timestamp = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO training_dataset 
            (id, question, ideal_answer, actual_answer, feedback_score, quality_score,
             needs_improvement, training_priority, category, data_source, 
             created_at, updated_at, approved_for_training)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (training_id, question, ideal_answer, actual_answer, rating, 
              1.0 - (rating / 5.0), True, max(1, 6 - rating), category,
              "auto_improvement", timestamp, timestamp, True))
        
        conn.commit()
        conn.close()
    
    def _generate_improvement_recommendations(self, improvement_areas: List[Dict]) -> List[Dict]:
        """Generate specific improvement recommendations"""
        recommendations = []
        
        for area in improvement_areas:
            if area["type"] == "category_performance":
                recommendations.append({
                    "type": "training_focus",
                    "action": f"Focus training on {area['category']} responses",
                    "reason": f"Category has {area['poor_ratings']} poor ratings",
                    "priority": area["severity"],
                    "implementation": f"Review and improve {area['category']} knowledge base"
                })
            
            elif area["type"] == "user_suggestion":
                recommendations.append({
                    "type": "feature_improvement",
                    "action": "Implement user suggestion",
                    "reason": f"Suggested {area['frequency']} times: {area['issue']}",
                    "priority": area["severity"],
                    "implementation": "Technical team review and implementation"
                })
            
            elif area["type"] == "overall_performance":
                recommendations.append({
                    "type": "comprehensive_review",
                    "action": "Comprehensive model review needed",
                    "reason": "Overall performance below acceptable threshold",
                    "priority": "HIGH",
                    "implementation": "Full model retraining with curated dataset"
                })
        
        # Add general recommendations
        if len(improvement_areas) > 3:
            recommendations.append({
                "type": "systematic_improvement",
                "action": "Implement systematic feedback collection",
                "reason": "Multiple improvement areas identified",
                "priority": "MEDIUM",
                "implementation": "Enhanced feedback prompts and user engagement"
            })
        
        return recommendations
    
    def _prepare_model_update(self) -> Dict:
        """Prepare data and configuration for model update"""
        # Export training data
        training_data = self.feedback_system.get_training_dataset(
            format_type="bedrock_jsonl", 
            approved_only=True, 
            limit=1000
        )
        
        # Create training file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        training_filename = f"model_training_{timestamp}.jsonl"
        
        with open(training_filename, 'w', encoding='utf-8') as f:
            for item in training_data:
                f.write(json.dumps(item) + '\n')
        
        # Upload to S3 if available
        s3_location = None
        if self.s3_client:
            try:
                s3_key = f"training-data/{training_filename}"
                self.s3_client.upload_file(training_filename, self.s3_bucket, s3_key)
                s3_location = f"s3://{self.s3_bucket}/{s3_key}"
                self.logger.info(f"Training data uploaded to {s3_location}")
            except Exception as e:
                self.logger.warning(f"Failed to upload to S3: {e}")
        
        return {
            "training_file": training_filename,
            "s3_location": s3_location,
            "training_examples": len(training_data),
            "recommended_action": "Review training data and initiate fine-tuning process",
            "next_steps": [
                "Review training data quality",
                "Configure fine-tuning parameters", 
                "Start model fine-tuning job",
                "Test improved model",
                "Deploy if performance improves"
            ]
        }
    
    def schedule_automatic_improvements(self, interval_hours: int = 24) -> Dict:
        """Setup automatic improvement scheduling"""
        return {
            "schedule_configured": True,
            "interval_hours": interval_hours,
            "next_run": (datetime.now() + timedelta(hours=interval_hours)).isoformat(),
            "note": "In production, integrate with scheduler like cron or AWS EventBridge"
        }
    
    def get_improvement_history(self, limit: int = 10) -> List[Dict]:
        """Get history of improvement cycles"""
        # This would typically be stored in a separate table
        # For now, return a mock history
        return [
            {
                "cycle_id": f"improvement_20241015_{i:02d}0000",
                "date": (datetime.now() - timedelta(days=i)).isoformat(),
                "improvements_found": 3 - i % 3,
                "training_data_created": 15 + i * 2,
                "success": True
            }
            for i in range(limit)
        ]

# Integration example
def integrate_with_existing_app(app_instance, feedback_system_instance):
    """Integrate improvement pipeline with existing Flask app"""
    
    dataset_manager = DatasetManager("./training_datasets")
    pipeline = ModelImprovementPipeline(feedback_system_instance, dataset_manager)
    
    @app_instance.route("/api/admin/improvement/run", methods=["POST"])
    def run_improvement_cycle():
        """API endpoint to manually trigger improvement cycle"""
        try:
            results = pipeline.run_improvement_cycle()
            return {
                "success": True,
                "results": results
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }, 500
    
    @app_instance.route("/api/admin/improvement/status", methods=["GET"])
    def get_improvement_status():
        """Get current improvement pipeline status"""
        analytics = feedback_system_instance.get_feedback_analytics()
        recommendations = feedback_system_instance.generate_improvement_recommendations()
        
        return {
            "analytics": analytics,
            "recommendations": recommendations,
            "history": pipeline.get_improvement_history(5)
        }
    
    return pipeline

# Example usage
if __name__ == "__main__":
    print("🔄 Model Improvement Pipeline Demo")
    
    # Initialize components
    feedback_system = EnhancedFeedbackSystem("demo_improvement.db")
    dataset_manager = DatasetManager("./demo_improvement_datasets")
    pipeline = ModelImprovementPipeline(feedback_system, dataset_manager)
    
    # Add some sample data first
    print("\n📝 Adding sample interactions and feedback...")
    
    # Good interaction
    interaction1 = feedback_system.log_interaction(
        "What's John's attendance?", 
        "John has 85% attendance", 
        "attendance",
        confidence_score=0.9
    )
    feedback_system.collect_feedback(interaction1, 5, 5, 5, 5, "Perfect!")
    
    # Poor interaction
    interaction2 = feedback_system.log_interaction(
        "Show me news", 
        "I can't get news right now", 
        "news",
        confidence_score=0.2
    )
    feedback_system.collect_feedback(interaction2, 2, 1, 2, 2, "Useless", "Should show actual news headlines")
    
    # Run improvement cycle
    print("\n🚀 Running improvement cycle...")
    results = pipeline.run_improvement_cycle(days_back=1)
    
    print("\n📊 Improvement Cycle Results:")
    print(json.dumps(results, indent=2, default=str))
    
    print("\n✅ Demo complete!")