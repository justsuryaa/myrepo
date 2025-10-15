#!/usr/bin/env python3
"""
Enhanced Feedback System for AI Model Training
Advanced feedback collection, dataset creation, and model improvement pipeline
"""

import json
import sqlite3
import os
import csv
import pandas as pd
from datetime import datetime, timedelta
import uuid
import random
from typing import List, Dict, Optional, Tuple

class EnhancedFeedbackSystem:
    def __init__(self, db_path="enhanced_feedback.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize comprehensive database schema for feedback and training"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # User interactions table - stores all AI conversations
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interactions (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                user_question TEXT NOT NULL,
                ai_response TEXT NOT NULL,
                query_type TEXT,
                response_time_ms INTEGER,
                user_ip TEXT,
                session_id TEXT,
                user_id TEXT,
                conversation_context TEXT,
                data_sources_used TEXT,
                confidence_score REAL DEFAULT 0.5
            )
        ''')
        
        # Enhanced feedback table with detailed ratings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                interaction_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                overall_rating INTEGER NOT NULL CHECK (overall_rating >= 1 AND overall_rating <= 5),
                accuracy_rating INTEGER CHECK (accuracy_rating >= 1 AND accuracy_rating <= 5),
                helpfulness_rating INTEGER CHECK (helpfulness_rating >= 1 AND helpfulness_rating <= 5),
                clarity_rating INTEGER CHECK (clarity_rating >= 1 AND clarity_rating <= 5),
                feedback_text TEXT,
                is_helpful BOOLEAN,
                suggested_improvement TEXT,
                category_feedback TEXT,
                user_ip TEXT,
                feedback_type TEXT DEFAULT 'manual',
                FOREIGN KEY (interaction_id) REFERENCES interactions (id)
            )
        ''')
        
        # Training dataset table - curated data for model training
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS training_dataset (
                id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                ideal_answer TEXT,
                actual_answer TEXT,
                feedback_score REAL,
                quality_score REAL DEFAULT 0.0,
                needs_improvement BOOLEAN DEFAULT FALSE,
                training_priority INTEGER DEFAULT 1,
                category TEXT,
                subcategory TEXT,
                difficulty_level TEXT DEFAULT 'medium',
                data_source TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                approved_for_training BOOLEAN DEFAULT FALSE,
                human_verified BOOLEAN DEFAULT FALSE,
                training_format TEXT DEFAULT 'conversation'
            )
        ''')
        
        # Model performance tracking over time
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS model_performance (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                model_version TEXT,
                accuracy_score REAL,
                user_satisfaction REAL,
                total_interactions INTEGER,
                total_feedback INTEGER,
                improvement_suggestions INTEGER,
                avg_response_time REAL,
                success_rate REAL,
                category_performance TEXT
            )
        ''')
        
        # Feedback prompts management
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback_prompts (
                id TEXT PRIMARY KEY,
                prompt_text TEXT NOT NULL,
                prompt_type TEXT NOT NULL,
                frequency INTEGER DEFAULT 5,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TEXT NOT NULL,
                usage_count INTEGER DEFAULT 0
            )
        ''')
        
        # User preferences for feedback frequency
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id TEXT PRIMARY KEY,
                feedback_frequency INTEGER DEFAULT 5,
                last_feedback_request TEXT,
                feedback_opt_out BOOLEAN DEFAULT FALSE,
                preferred_feedback_type TEXT DEFAULT 'rating'
            )
        ''')
        
        conn.commit()
        conn.close()
        
        # Initialize default feedback prompts
        self._init_default_prompts()
    
    def _init_default_prompts(self):
        """Initialize default feedback prompts"""
        default_prompts = [
            {
                "prompt_text": "How helpful was my previous response?",
                "prompt_type": "helpfulness",
                "frequency": 5
            },
            {
                "prompt_text": "Was my answer accurate and complete?",
                "prompt_type": "accuracy",
                "frequency": 3
            },
            {
                "prompt_text": "How can I improve my responses?",
                "prompt_type": "improvement",
                "frequency": 10
            },
            {
                "prompt_text": "Rate the clarity of my explanation (1-5 stars)",
                "prompt_type": "clarity",
                "frequency": 7
            }
        ]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for prompt in default_prompts:
            cursor.execute('''
                INSERT OR IGNORE INTO feedback_prompts 
                (id, prompt_text, prompt_type, frequency, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (str(uuid.uuid4()), prompt["prompt_text"], prompt["prompt_type"], 
                  prompt["frequency"], datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def log_interaction(self, user_question: str, ai_response: str, query_type: str = "general", 
                       response_time_ms: int = None, user_ip: str = None, session_id: str = None,
                       user_id: str = None, data_sources_used: List[str] = None, 
                       confidence_score: float = 0.5) -> str:
        """Log a detailed user interaction"""
        interaction_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO interactions 
            (id, timestamp, user_question, ai_response, query_type, response_time_ms, 
             user_ip, session_id, user_id, data_sources_used, confidence_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (interaction_id, timestamp, user_question, ai_response, query_type, 
              response_time_ms, user_ip, session_id, user_id, 
              json.dumps(data_sources_used) if data_sources_used else None, confidence_score))
        
        conn.commit()
        conn.close()
        
        return interaction_id
    
    def should_request_feedback(self, user_id: str = None, session_id: str = None) -> Tuple[bool, str]:
        """Determine if we should ask for feedback and what type"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get user preferences
        if user_id:
            cursor.execute('SELECT feedback_frequency, last_feedback_request, feedback_opt_out FROM user_preferences WHERE user_id = ?', (user_id,))
            prefs = cursor.fetchone()
            if prefs and prefs[2]:  # User opted out
                return False, ""
            frequency = prefs[0] if prefs else 5
            last_request = prefs[1] if prefs else None
        else:
            frequency = 5
            last_request = None
        
        # Count interactions since last feedback request
        if session_id:
            cursor.execute('SELECT COUNT(*) FROM interactions WHERE session_id = ?', (session_id,))
            interaction_count = cursor.fetchone()[0]
        else:
            interaction_count = random.randint(1, 10)  # Random for demo
        
        # Check if it's time for feedback
        if interaction_count % frequency == 0:
            # Get an active prompt
            cursor.execute('SELECT prompt_text, prompt_type FROM feedback_prompts WHERE is_active = TRUE ORDER BY RANDOM() LIMIT 1')
            prompt = cursor.fetchone()
            if prompt:
                return True, prompt[0]
        
        conn.close()
        return False, ""
    
    def collect_feedback(self, interaction_id: str, overall_rating: int, 
                        accuracy_rating: int = None, helpfulness_rating: int = None,
                        clarity_rating: int = None, feedback_text: str = None,
                        suggested_improvement: str = None, user_ip: str = None) -> str:
        """Collect comprehensive user feedback"""
        feedback_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO feedback 
            (id, interaction_id, timestamp, overall_rating, accuracy_rating, 
             helpfulness_rating, clarity_rating, feedback_text, 
             suggested_improvement, user_ip, is_helpful)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (feedback_id, interaction_id, timestamp, overall_rating, accuracy_rating,
              helpfulness_rating, clarity_rating, feedback_text, suggested_improvement, 
              user_ip, overall_rating >= 3))
        
        conn.commit()
        conn.close()
        
        # Automatically create training data for low ratings or improvements
        if overall_rating <= 2 or suggested_improvement:
            self._create_training_data_from_feedback(interaction_id, overall_rating, suggested_improvement)
        
        return feedback_id
    
    def _create_training_data_from_feedback(self, interaction_id: str, rating: int, 
                                          suggested_improvement: str = None):
        """Create training data entry from feedback"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get interaction details
        cursor.execute('''
            SELECT user_question, ai_response, query_type, confidence_score
            FROM interactions 
            WHERE id = ?
        ''', (interaction_id,))
        
        result = cursor.fetchone()
        if result:
            question, actual_answer, query_type, confidence = result
            
            training_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()
            
            # Calculate priority and quality scores
            priority = max(1, 6 - rating)  # Lower rating = higher priority
            quality_score = 1.0 - (rating / 5.0)  # Convert rating to quality score
            
            # Determine difficulty level based on question complexity
            difficulty = "easy" if len(question.split()) < 10 else "medium" if len(question.split()) < 20 else "hard"
            
            cursor.execute('''
                INSERT INTO training_dataset 
                (id, question, ideal_answer, actual_answer, feedback_score, quality_score,
                 needs_improvement, training_priority, category, difficulty_level,
                 data_source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (training_id, question, suggested_improvement or "", actual_answer, 
                  rating, quality_score, True, priority, query_type, difficulty,
                  "user_feedback", timestamp, timestamp))
        
        conn.commit()
        conn.close()
    
    def get_training_dataset(self, format_type: str = "json", quality_threshold: float = 0.3,
                           approved_only: bool = False, limit: int = 1000) -> List[Dict]:
        """Get training data in various formats"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = '''
            SELECT question, ideal_answer, actual_answer, feedback_score, 
                   category, difficulty_level, quality_score
            FROM training_dataset
            WHERE quality_score >= ? 
        '''
        params = [quality_threshold]
        
        if approved_only:
            query += " AND approved_for_training = TRUE"
        
        query += " ORDER BY training_priority DESC, quality_score DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        # Format data based on requested format
        if format_type == "bedrock_jsonl":
            return self._format_for_bedrock(results)
        elif format_type == "openai":
            return self._format_for_openai(results)
        elif format_type == "csv":
            return self._format_for_csv(results)
        else:
            return self._format_for_json(results)
    
    def _format_for_bedrock(self, results: List[Tuple]) -> List[Dict]:
        """Format training data for AWS Bedrock fine-tuning (JSONL)"""
        formatted_data = []
        for row in results:
            question, ideal_answer, actual_answer, score, category, difficulty, quality = row
            if ideal_answer:  # Only include items with ideal answers
                formatted_data.append({
                    "messages": [
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": ideal_answer}
                    ],
                    "metadata": {
                        "category": category,
                        "difficulty": difficulty,
                        "quality_score": quality
                    }
                })
        return formatted_data
    
    def _format_for_openai(self, results: List[Tuple]) -> List[Dict]:
        """Format training data for OpenAI fine-tuning"""
        formatted_data = []
        for row in results:
            question, ideal_answer, actual_answer, score, category, difficulty, quality = row
            if ideal_answer:
                formatted_data.append({
                    "messages": [
                        {"role": "system", "content": f"You are a helpful AI assistant specializing in {category} questions."},
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": ideal_answer}
                    ]
                })
        return formatted_data
    
    def _format_for_json(self, results: List[Tuple]) -> List[Dict]:
        """Format training data as JSON"""
        formatted_data = []
        for row in results:
            question, ideal_answer, actual_answer, score, category, difficulty, quality = row
            formatted_data.append({
                "question": question,
                "ideal_answer": ideal_answer,
                "actual_answer": actual_answer,
                "feedback_score": score,
                "category": category,
                "difficulty": difficulty,
                "quality_score": quality
            })
        return formatted_data
    
    def _format_for_csv(self, results: List[Tuple]) -> List[Dict]:
        """Format training data for CSV export"""
        formatted_data = []
        for row in results:
            question, ideal_answer, actual_answer, score, category, difficulty, quality = row
            formatted_data.append({
                "question": question,
                "ideal_answer": ideal_answer,
                "actual_answer": actual_answer,
                "feedback_score": score,
                "category": category,
                "difficulty": difficulty,
                "quality_score": quality,
                "needs_improvement": quality > 0.5
            })
        return formatted_data
    
    def export_training_data(self, filename: str = None, format_type: str = "json",
                           quality_threshold: float = 0.3, approved_only: bool = False) -> Tuple[str, int]:
        """Export training data to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"training_data_{timestamp}.{format_type.split('_')[0]}"
        
        data = self.get_training_dataset(format_type, quality_threshold, approved_only)
        
        if format_type == "bedrock_jsonl":
            with open(filename, 'w', encoding='utf-8') as f:
                for item in data:
                    f.write(json.dumps(item) + '\n')
        elif format_type == "csv":
            if data:
                df = pd.DataFrame(data)
                df.to_csv(filename, index=False, encoding='utf-8')
        else:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        
        return filename, len(data)
    
    def get_feedback_analytics(self) -> Dict:
        """Get comprehensive feedback analytics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Basic statistics
        cursor.execute("SELECT COUNT(*) FROM interactions")
        total_interactions = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM feedback")
        total_feedback = cursor.fetchone()[0]
        
        cursor.execute("SELECT AVG(overall_rating) FROM feedback")
        avg_rating = cursor.fetchone()[0] or 0
        
        # Rating distribution
        cursor.execute("""
            SELECT overall_rating, COUNT(*) 
            FROM feedback 
            GROUP BY overall_rating 
            ORDER BY overall_rating
        """)
        rating_distribution = dict(cursor.fetchall())
        
        # Category performance
        cursor.execute('''
            SELECT i.query_type, AVG(f.overall_rating) as avg_rating, 
                   COUNT(f.overall_rating) as feedback_count
            FROM interactions i
            JOIN feedback f ON i.id = f.interaction_id
            GROUP BY i.query_type
            ORDER BY avg_rating DESC
        ''')
        category_performance = [
            {"category": r[0], "avg_rating": round(r[1], 2), "count": r[2]} 
            for r in cursor.fetchall()
        ]
        
        # Training data statistics
        cursor.execute("SELECT COUNT(*) FROM training_dataset WHERE needs_improvement = TRUE")
        needs_improvement = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM training_dataset WHERE approved_for_training = TRUE")
        approved_for_training = cursor.fetchone()[0]
        
        # Recent trends (last 7 days)
        cursor.execute('''
            SELECT DATE(i.timestamp) as date, COUNT(*) as interactions, 
                   AVG(f.overall_rating) as avg_rating
            FROM interactions i
            LEFT JOIN feedback f ON i.id = f.interaction_id
            WHERE DATE(i.timestamp) >= DATE('now', '-7 days')
            GROUP BY DATE(i.timestamp)
            ORDER BY date
        ''')
        daily_trends = [
            {"date": r[0], "interactions": r[1], "avg_rating": round(r[2] or 0, 2)} 
            for r in cursor.fetchall()
        ]
        
        # Response time analysis
        cursor.execute('''
            SELECT AVG(response_time_ms), MIN(response_time_ms), MAX(response_time_ms)
            FROM interactions 
            WHERE response_time_ms IS NOT NULL
        ''')
        response_times = cursor.fetchone()
        
        conn.close()
        
        return {
            "overview": {
                "total_interactions": total_interactions,
                "total_feedback": total_feedback,
                "average_rating": round(avg_rating, 2),
                "feedback_rate": round((total_feedback / max(total_interactions, 1)) * 100, 2)
            },
            "rating_distribution": rating_distribution,
            "category_performance": category_performance,
            "training_data": {
                "needs_improvement": needs_improvement,
                "approved_for_training": approved_for_training,
                "total_training_items": needs_improvement + approved_for_training
            },
            "daily_trends": daily_trends,
            "performance_metrics": {
                "avg_response_time": round(response_times[0] or 0, 2),
                "min_response_time": response_times[1] or 0,
                "max_response_time": response_times[2] or 0
            }
        }
    
    def generate_improvement_recommendations(self) -> Dict:
        """Generate AI model improvement recommendations"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Find problem areas (low ratings by category)
        cursor.execute('''
            SELECT i.query_type, AVG(f.overall_rating) as avg_rating, COUNT(*) as count,
                   COUNT(CASE WHEN f.overall_rating <= 2 THEN 1 END) as poor_ratings
            FROM interactions i
            JOIN feedback f ON i.id = f.interaction_id
            GROUP BY i.query_type
            ORDER BY avg_rating ASC
        ''')
        
        problem_areas = []
        for row in cursor.fetchall():
            category, avg_rating, count, poor_count = row
            problem_areas.append({
                "category": category,
                "average_rating": round(avg_rating, 2),
                "total_feedback": count,
                "poor_ratings": poor_count,
                "improvement_priority": "HIGH" if avg_rating < 2.5 else "MEDIUM" if avg_rating < 3.5 else "LOW"
            })
        
        # Common improvement suggestions
        cursor.execute('''
            SELECT suggested_improvement, COUNT(*) as frequency
            FROM feedback
            WHERE suggested_improvement IS NOT NULL AND suggested_improvement != ''
            GROUP BY suggested_improvement
            ORDER BY frequency DESC
            LIMIT 10
        ''')
        
        common_suggestions = [
            {"suggestion": r[0], "frequency": r[1]} 
            for r in cursor.fetchall()
        ]
        
        # Training data readiness
        cursor.execute('''
            SELECT category, COUNT(*) as training_items, AVG(quality_score) as avg_quality
            FROM training_dataset
            WHERE needs_improvement = TRUE
            GROUP BY category
            ORDER BY training_items DESC
        ''')
        
        training_readiness = [
            {"category": r[0], "training_items": r[1], "avg_quality": round(r[2], 2)}
            for r in cursor.fetchall()
        ]
        
        conn.close()
        
        return {
            "problem_areas": problem_areas,
            "common_suggestions": common_suggestions,
            "training_readiness": training_readiness,
            "recommendations": self._generate_specific_recommendations(problem_areas, common_suggestions),
            "generated_at": datetime.now().isoformat()
        }
    
    def _generate_specific_recommendations(self, problem_areas: List[Dict], 
                                         suggestions: List[Dict]) -> List[str]:
        """Generate specific improvement recommendations"""
        recommendations = []
        
        # Category-specific recommendations
        for area in problem_areas[:3]:  # Top 3 problem areas
            if area["improvement_priority"] == "HIGH":
                recommendations.append(
                    f"URGENT: Improve {area['category']} responses - only {area['average_rating']:.1f}/5 rating"
                )
            elif area["improvement_priority"] == "MEDIUM":
                recommendations.append(
                    f"Focus on {area['category']} accuracy - current rating: {area['average_rating']:.1f}/5"
                )
        
        # Suggestion-based recommendations
        for suggestion in suggestions[:2]:  # Top 2 suggestions
            recommendations.append(f"Consider: {suggestion['suggestion']} (mentioned {suggestion['frequency']} times)")
        
        # General recommendations
        if not recommendations:
            recommendations.append("Overall performance is good - continue monitoring user feedback")
        
        return recommendations

# Example usage and testing
if __name__ == "__main__":
    print("🚀 Enhanced Feedback System Demo")
    
    # Initialize system
    efs = EnhancedFeedbackSystem("demo_enhanced_feedback.db")
    
    # Simulate some interactions and feedback
    print("\n📝 Adding sample interactions and feedback...")
    
    # Good interaction
    interaction1 = efs.log_interaction(
        user_question="What is John's attendance rate?",
        ai_response="John has 85% attendance this month with 17 out of 20 days present.",
        query_type="s3_attendance",
        response_time_ms=1200,
        confidence_score=0.9
    )
    
    # Poor interaction
    interaction2 = efs.log_interaction(
        user_question="Tell me the latest news",
        ai_response="I couldn't fetch the news right now.",
        query_type="external_news",
        response_time_ms=800,
        confidence_score=0.3
    )
    
    # Collect feedback
    efs.collect_feedback(interaction1, overall_rating=5, accuracy_rating=5, 
                        helpfulness_rating=5, feedback_text="Perfect answer!")
    
    efs.collect_feedback(interaction2, overall_rating=2, accuracy_rating=1,
                        helpfulness_rating=2, feedback_text="Didn't work at all",
                        suggested_improvement="Should show actual news headlines from reliable sources")
    
    # Check if we should request feedback
    should_ask, prompt = efs.should_request_feedback(session_id="demo_session")
    print(f"\n🤖 Should ask for feedback: {should_ask}")
    if should_ask:
        print(f"Prompt: {prompt}")
    
    # Get analytics
    print("\n📊 Feedback Analytics:")
    analytics = efs.get_feedback_analytics()
    print(json.dumps(analytics, indent=2))
    
    # Generate improvement recommendations
    print("\n💡 Improvement Recommendations:")
    recommendations = efs.generate_improvement_recommendations()
    print(json.dumps(recommendations, indent=2))
    
    # Export training data in different formats
    print(f"\n💾 Exporting training data...")
    
    # JSON format
    json_file, json_count = efs.export_training_data("demo_training.json", "json")
    print(f"JSON: {json_file} ({json_count} items)")
    
    # Bedrock JSONL format
    bedrock_file, bedrock_count = efs.export_training_data("demo_training.jsonl", "bedrock_jsonl")
    print(f"Bedrock JSONL: {bedrock_file} ({bedrock_count} items)")
    
    # CSV format
    csv_file, csv_count = efs.export_training_data("demo_training.csv", "csv")
    print(f"CSV: {csv_file} ({csv_count} items)")
    
    print(f"\n✅ Demo complete! Check the generated files and database.")