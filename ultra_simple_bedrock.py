#!/usr/bin/env python3
"""
ULTRA-SIMPLE Bedrock Feedback System
Works with existing database, focuses ONLY on collecting feedback and creating Bedrock training data
"""

import sqlite3
import json
import uuid
from datetime import datetime
from typing import List, Dict

class SimpleBedrock:
    """Super simple system: Feedback → Bedrock training data"""
    
    def __init__(self, db_path: str = "school_feedback.db"):
        self.db_path = db_path
    
    def add_feedback(self, user_question: str, ai_response: str, rating: int, feedback_text: str = ""):
        """Add feedback to existing database structure"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Add to interactions table
        interaction_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO interactions (id, timestamp, user_question, ai_response, query_type, response_time_ms, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (interaction_id, timestamp, user_question, ai_response, "feedback", 1000, "system"))
        
        # Add to feedback table
        feedback_id = str(uuid.uuid4())
        cursor.execute('''
            INSERT INTO feedback (id, interaction_id, timestamp, rating, feedback_text, is_helpful, user_ip)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (feedback_id, interaction_id, timestamp, rating, feedback_text, rating >= 4, "127.0.0.1"))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Added feedback: {rating}/5 stars")
        return interaction_id
    
    def create_bedrock_training(self, output_file: str = None) -> str:
        """Create Bedrock training file from feedback data"""
        
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"bedrock_training_{timestamp}.jsonl"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all interactions with feedback
        cursor.execute('''
            SELECT i.user_question, i.ai_response, f.rating, f.feedback_text
            FROM interactions i
            JOIN feedback f ON i.id = f.interaction_id
            ORDER BY f.rating DESC
        ''')
        
        data = cursor.fetchall()
        conn.close()
        
        if not data:
            print("❌ No feedback data found!")
            return None
        
        # Create Bedrock format
        training_examples = []
        
        for question, response, rating, feedback in data:
            # Use high-rated responses as positive examples
            if rating >= 4:
                training_examples.append({
                    "messages": [
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": response}
                    ],
                    "metadata": {
                        "rating": rating,
                        "quality": "high"
                    }
                })
            
            # Use feedback text as improved responses for low ratings
            elif rating <= 3 and feedback.strip():
                training_examples.append({
                    "messages": [
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": feedback}
                    ],
                    "metadata": {
                        "rating": rating,
                        "quality": "improved",
                        "original_response": response
                    }
                })
        
        # Write JSONL file
        with open(output_file, 'w') as f:
            for example in training_examples:
                f.write(json.dumps(example) + '\n')
        
        print(f"🤖 Created Bedrock training file: {output_file}")
        print(f"   • Training examples: {len(training_examples)}")
        print(f"   • Total feedback entries: {len(data)}")
        
        return output_file
    
    def get_stats(self):
        """Simple statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*), AVG(rating) FROM feedback')
        count, avg_rating = cursor.fetchone()
        
        cursor.execute('SELECT rating, COUNT(*) FROM feedback GROUP BY rating ORDER BY rating')
        rating_dist = cursor.fetchall()
        
        conn.close()
        
        print(f"📊 FEEDBACK STATS:")
        print(f"   • Total feedback: {count or 0}")
        print(f"   • Average rating: {avg_rating or 0:.1f}/5")
        print(f"   • Rating distribution:")
        for rating, cnt in (rating_dist or []):
            print(f"     {rating} stars: {cnt} responses")

def main():
    """Main function - simple demo"""
    print("🎯 ULTRA-SIMPLE BEDROCK FEEDBACK SYSTEM")
    print("=" * 50)
    
    system = SimpleBedrock()
    
    # Add sample feedback
    print("📝 Adding sample feedback...")
    system.add_feedback("What is attendance?", "85% this month", 5, "Perfect!")
    system.add_feedback("Show news", "Cannot access news", 2, "Connect to real news API")
    system.add_feedback("Tell joke", "Why did chicken cross road?", 3, "Need better jokes")
    
    # Show stats
    system.get_stats()
    
    # Create training data
    print(f"\n🤖 Creating Bedrock training data...")
    training_file = system.create_bedrock_training()
    
    if training_file:
        print(f"\n🎉 SUCCESS!")
        print(f"   📄 Training file: {training_file}")
        print(f"   📤 Upload to S3 for Bedrock fine-tuning")
        
        # Show file content
        print(f"\n📋 Sample training data:")
        with open(training_file, 'r') as f:
            lines = f.readlines()[:2]  # Show first 2 examples
            for i, line in enumerate(lines, 1):
                data = json.loads(line)
                print(f"   Example {i}: {data['messages'][0]['content'][:30]}...")

if __name__ == "__main__":
    main()