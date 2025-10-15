#!/usr/bin/env python3
"""
User Interaction Database - JSON File Version
Stores user prompts, responses, and metadata in JSON format
"""

import json
import os
import time
from datetime import datetime

class UserInteractionDB:
    def __init__(self, db_file="user_interactions.json"):
        self.db_file = db_file
        self.interactions = self.load_interactions()
    
    def load_interactions(self):
        """Load existing interactions from JSON file"""
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading interactions: {e}")
                return []
        return []
    
    def save_interactions(self):
        """Save interactions to JSON file"""
        try:
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump(self.interactions, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving interactions: {e}")
    
    def add_interaction(self, user_prompt, ai_response, query_type="unknown", user_id="anonymous", api_key=None):
        """Add a new user interaction"""
        interaction = {
            "id": len(self.interactions) + 1,
            "timestamp": datetime.now().isoformat(),
            "unix_timestamp": time.time(),
            "user_id": user_id,
            "api_key": api_key,
            "user_prompt": user_prompt,
            "ai_response": ai_response,
            "query_type": query_type,
            "prompt_length": len(user_prompt),
            "response_length": len(ai_response),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M:%S")
        }
        
        self.interactions.append(interaction)
        self.save_interactions()
        return interaction["id"]
    
    def get_all_interactions(self):
        """Get all interactions"""
        return self.interactions
    
    def get_interactions_by_date(self, date):
        """Get interactions for a specific date (YYYY-MM-DD)"""
        return [i for i in self.interactions if i["date"] == date]
    
    def get_interactions_by_type(self, query_type):
        """Get interactions by query type"""
        return [i for i in self.interactions if i["query_type"] == query_type]
    
    def get_interactions_by_user(self, user_id):
        """Get interactions by user ID"""
        return [i for i in self.interactions if i["user_id"] == user_id]
    
    def get_popular_prompts(self, limit=10):
        """Get most common prompt patterns"""
        prompts = [i["user_prompt"].lower() for i in self.interactions]
        from collections import Counter
        return Counter(prompts).most_common(limit)
    
    def get_statistics(self):
        """Get database statistics"""
        if not self.interactions:
            return {"total": 0}
        
        query_types = [i["query_type"] for i in self.interactions]
        from collections import Counter
        
        return {
            "total_interactions": len(self.interactions),
            "unique_users": len(set(i["user_id"] for i in self.interactions)),
            "date_range": {
                "first": min(i["date"] for i in self.interactions),
                "last": max(i["date"] for i in self.interactions)
            },
            "query_types": dict(Counter(query_types)),
            "avg_prompt_length": sum(i["prompt_length"] for i in self.interactions) / len(self.interactions),
            "avg_response_length": sum(i["response_length"] for i in self.interactions) / len(self.interactions)
        }
    
    def export_to_csv(self, filename="interactions_export.csv"):
        """Export interactions to CSV"""
        import csv
        
        if not self.interactions:
            print("No interactions to export")
            return
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ["id", "timestamp", "user_id", "api_key", "user_prompt", 
                         "ai_response", "query_type", "prompt_length", "response_length"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for interaction in self.interactions:
                # Only write specified fields
                row = {field: interaction.get(field, '') for field in fieldnames}
                writer.writerow(row)
        
        print(f"Exported {len(self.interactions)} interactions to {filename}")

# Demo usage
if __name__ == "__main__":
    # Create database instance
    db = UserInteractionDB("demo_interactions.json")
    
    # Add sample interactions
    print("Adding sample interactions...")
    db.add_interaction(
        user_prompt="What is John's attendance?",
        ai_response="John has been present for 85% of classes this month.",
        query_type="s3_attendance",
        user_id="user123"
    )
    
    db.add_interaction(
        user_prompt="Tell me the latest news",
        ai_response="Here are the latest headlines: Technology advances...",
        query_type="external_news",
        user_id="user456"
    )
    
    db.add_interaction(
        user_prompt="What is the capital of France?",
        ai_response="The capital of France is Paris.",
        query_type="general",
        user_id="user123"
    )
    
    # Display statistics
    print("\n📊 Database Statistics:")
    stats = db.get_statistics()
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    # Show recent interactions
    print(f"\n📝 Recent Interactions ({len(db.get_all_interactions())} total):")
    for interaction in db.get_all_interactions()[-3:]:
        print(f"[{interaction['timestamp']}] {interaction['user_prompt'][:50]}...")
    
    # Export to CSV
    print(f"\n💾 Exporting to CSV...")
    db.export_to_csv("demo_export.csv")
    
    print(f"\n✅ Demo complete! Check 'demo_interactions.json' and 'demo_export.csv'")