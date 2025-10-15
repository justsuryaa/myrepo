#!/usr/bin/env python3
"""
Advanced Feedback System for AI Model Training
Collects user feedback and creates training datasets for model improvement
"""

import json
import sqlite3
import os
from datetime import datetime
import uuid

class FeedbackTrainingSystem:
    def __init__(self, db_path="feedback_training.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the SQLite database with feedback and training tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # User interactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interactions (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                user_question TEXT NOT NULL,
                ai_response TEXT NOT NULL,
                query_type TEXT,
                response_time_ms INTEGER,
                user_ip TEXT,
                session_id TEXT
            )
        ''')
        
        # User feedback table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                interaction_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
                feedback_text TEXT,
                is_helpful BOOLEAN,
                suggested_improvement TEXT,
                user_ip TEXT,
                FOREIGN KEY (interaction_id) REFERENCES interactions (id)
            )
        ''')
        
        # Training data table for AI model improvement
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS training_data (
                id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                expected_answer TEXT,
                actual_answer TEXT,
                feedback_score REAL,
                needs_improvement BOOLEAN DEFAULT FALSE,
                training_priority INTEGER DEFAULT 1,
                category TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                approved_for_training BOOLEAN DEFAULT FALSE
            )
        ''')
        
        # Model performance tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS model_performance (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                model_version TEXT,
                accuracy_score REAL,
                user_satisfaction REAL,
                total_interactions INTEGER,
                total_feedback INTEGER,
                improvement_suggestions INTEGER
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def log_interaction(self, user_question, ai_response, query_type, response_time_ms=None, user_ip=None, session_id=None):
        """Log a user interaction"""
        interaction_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO interactions 
            (id, timestamp, user_question, ai_response, query_type, response_time_ms, user_ip, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (interaction_id, timestamp, user_question, ai_response, query_type, response_time_ms, user_ip, session_id))
        
        conn.commit()
        conn.close()
        
        return interaction_id
    
    def add_feedback(self, interaction_id, rating, feedback_text=None, is_helpful=None, suggested_improvement=None, user_ip=None):
        """Add user feedback and automatically create training data if needed"""
        feedback_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO feedback 
            (id, interaction_id, timestamp, rating, feedback_text, is_helpful, suggested_improvement, user_ip)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (feedback_id, interaction_id, timestamp, rating, feedback_text, is_helpful, suggested_improvement, user_ip))
        
        conn.commit()
        conn.close()
        
        # Automatically create training data for low ratings or suggestions
        if rating <= 2 or suggested_improvement:
            self.create_training_data_from_feedback(interaction_id, rating, suggested_improvement)
        
        return feedback_id
    
    def create_training_data_from_feedback(self, interaction_id, rating, suggested_improvement=None):
        """Create training data entry from feedback"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get interaction details
        cursor.execute('''
            SELECT user_question, ai_response, query_type 
            FROM interactions 
            WHERE id = ?
        ''', (interaction_id,))
        
        result = cursor.fetchone()
        if result:
            question, actual_answer, query_type = result
            
            training_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()
            
            # Calculate priority: lower rating = higher priority
            priority = 6 - rating if rating <= 5 else 1
            
            # Use suggested improvement as expected answer if provided
            expected_answer = suggested_improvement if suggested_improvement else ""
            
            cursor.execute('''
                INSERT INTO training_data 
                (id, question, expected_answer, actual_answer, feedback_score, needs_improvement, 
                 training_priority, category, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (training_id, question, expected_answer, actual_answer, rating, True, 
                  priority, query_type, timestamp, timestamp))
        
        conn.commit()
        conn.close()
    
    def get_questions_for_feedback(self, limit=5):
        """Get recent interactions that need user feedback"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT i.id, i.timestamp, i.user_question, i.ai_response, i.query_type
            FROM interactions i
            LEFT JOIN feedback f ON i.id = f.interaction_id
            WHERE f.interaction_id IS NULL
            ORDER BY i.timestamp DESC
            LIMIT ?
        ''', (limit,))
        
        results = cursor.fetchall()
        conn.close()
        
        return [{"id": r[0], "timestamp": r[1], "question": r[2], "response": r[3], "type": r[4]} for r in results]
    
    def get_training_dataset(self, approved_only=False, limit=100):
        """Get training data for model improvement"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if approved_only:
            cursor.execute('''
                SELECT question, expected_answer, actual_answer, feedback_score, category
                FROM training_data
                WHERE approved_for_training = TRUE
                ORDER BY training_priority DESC, feedback_score ASC
                LIMIT ?
            ''', (limit,))
        else:
            cursor.execute('''
                SELECT question, expected_answer, actual_answer, feedback_score, category
                FROM training_data
                WHERE needs_improvement = TRUE
                ORDER BY training_priority DESC, feedback_score ASC
                LIMIT ?
            ''', (limit,))
        
        results = cursor.fetchall()
        conn.close()
        
        return [{"question": r[0], "expected": r[1], "actual": r[2], "score": r[3], "category": r[4]} for r in results]
    
    def approve_training_data(self, training_id):
        """Approve training data for model training"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE training_data 
            SET approved_for_training = TRUE, updated_at = ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), training_id))
        
        conn.commit()
        conn.close()
    
    def get_analytics_dashboard(self):
        """Get comprehensive analytics for the feedback system"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Basic stats
        cursor.execute("SELECT COUNT(*) FROM interactions")
        total_interactions = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM feedback")
        total_feedback = cursor.fetchone()[0]
        
        cursor.execute("SELECT AVG(rating) FROM feedback")
        avg_rating = cursor.fetchone()[0] or 0
        
        # Rating distribution
        cursor.execute("SELECT rating, COUNT(*) FROM feedback GROUP BY rating ORDER BY rating")
        rating_distribution = dict(cursor.fetchall())
        
        # Query type performance
        cursor.execute('''
            SELECT i.query_type, AVG(f.rating) as avg_rating, COUNT(f.rating) as feedback_count
            FROM interactions i
            JOIN feedback f ON i.id = f.interaction_id
            GROUP BY i.query_type
        ''')
        query_performance = [{"type": r[0], "avg_rating": r[1], "count": r[2]} for r in cursor.fetchall()]
        
        # Training data stats
        cursor.execute("SELECT COUNT(*) FROM training_data WHERE needs_improvement = TRUE")
        needs_improvement = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM training_data WHERE approved_for_training = TRUE")
        approved_for_training = cursor.fetchone()[0]
        
        # Recent trends (last 7 days)
        cursor.execute('''
            SELECT DATE(timestamp) as date, COUNT(*) as interactions, AVG(rating) as avg_rating
            FROM interactions i
            LEFT JOIN feedback f ON i.id = f.interaction_id
            WHERE DATE(i.timestamp) >= DATE('now', '-7 days')
            GROUP BY DATE(timestamp)
            ORDER BY date
        ''')
        daily_trends = [{"date": r[0], "interactions": r[1], "avg_rating": r[2]} for r in cursor.fetchall()]
        
        conn.close()
        
        return {
            "overview": {
                "total_interactions": total_interactions,
                "total_feedback": total_feedback,
                "average_rating": round(avg_rating, 2),
                "feedback_rate": round((total_feedback / max(total_interactions, 1)) * 100, 2)
            },
            "rating_distribution": rating_distribution,
            "query_performance": query_performance,
            "training_data": {
                "needs_improvement": needs_improvement,
                "approved_for_training": approved_for_training
            },
            "daily_trends": daily_trends
        }
    
    def export_training_dataset(self, filename="ai_training_data.json", format="json"):
        """Export training data in various formats for AI model training"""
        training_data = self.get_training_dataset(approved_only=True, limit=1000)
        
        if format == "json":
            # Format for general ML training
            formatted_data = []
            for item in training_data:
                if item["expected"]:  # Only include items with expected answers
                    formatted_data.append({
                        "input": item["question"],
                        "output": item["expected"],
                        "category": item["category"],
                        "quality_score": item["score"]
                    })
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(formatted_data, f, indent=2, ensure_ascii=False)
        
        elif format == "bedrock":
            # Format for AWS Bedrock fine-tuning
            formatted_data = []
            for item in training_data:
                if item["expected"]:
                    formatted_data.append({
                        "messages": [
                            {"role": "user", "content": item["question"]},
                            {"role": "assistant", "content": item["expected"]}
                        ]
                    })
            
            with open(filename, 'w', encoding='utf-8') as f:
                for item in formatted_data:
                    f.write(json.dumps(item) + '\n')  # JSONL format
        
        return filename, len(formatted_data)
    
    def generate_improvement_report(self):
        """Generate a report on areas needing improvement"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Low-rated interactions by category
        cursor.execute('''
            SELECT i.query_type, AVG(f.rating) as avg_rating, COUNT(*) as count,
                   GROUP_CONCAT(DISTINCT i.user_question) as sample_questions
            FROM interactions i
            JOIN feedback f ON i.id = f.interaction_id
            WHERE f.rating <= 2
            GROUP BY i.query_type
            ORDER BY avg_rating ASC
        ''')
        
        problem_areas = []
        for row in cursor.fetchall():
            query_type, avg_rating, count, sample_questions = row
            problem_areas.append({
                "category": query_type,
                "average_rating": round(avg_rating, 2),
                "problem_count": count,
                "sample_questions": sample_questions.split(',')[:3] if sample_questions else []
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
        
        common_suggestions = [{"suggestion": r[0], "frequency": r[1]} for r in cursor.fetchall()]
        
        conn.close()
        
        return {
            "problem_areas": problem_areas,
            "common_suggestions": common_suggestions,
            "generated_at": datetime.now().isoformat()
        }

# Global instance
feedback_system = FeedbackTrainingSystem()

if __name__ == "__main__":
    # Demo the feedback system
    fs = FeedbackTrainingSystem("demo_feedback.db")
    
    print("🚀 Testing Feedback Training System")
    
    # Log some interactions
    interaction1 = fs.log_interaction(
        "What is John's attendance?",
        "John has 85% attendance this month.",
        "s3_attendance"
    )
    
    interaction2 = fs.log_interaction(
        "Tell me the news",
        "I couldn't fetch the news right now.",
        "external_news"
    )
    
    # Add feedback
    fs.add_feedback(interaction1, 5, "Perfect answer!", True)
    fs.add_feedback(interaction2, 2, "Didn't work", False, "Should show actual news headlines")
    
    # Get analytics
    analytics = fs.get_analytics_dashboard()
    print("\n📊 Analytics:")
    print(json.dumps(analytics, indent=2))
    
    # Get training data
    training_data = fs.get_training_dataset()
    print(f"\n📚 Training Data: {len(training_data)} items")
    for item in training_data:
        print(f"Q: {item['question']}")
        print(f"Expected: {item['expected']}")
        print(f"Score: {item['score']}")
        print()
    
    # Generate improvement report
    report = fs.generate_improvement_report()
    print("📋 Improvement Report:")
    print(json.dumps(report, indent=2))
    
    print("\n✅ Demo complete!")