#!/usr/bin/env python3
"""
Dataset Creation and Management System
Creates structured databases from user prompts and feedback
"""

import json
import sqlite3
import pandas as pd
import csv
from datetime import datetime
from typing import List, Dict, Optional, Any
import uuid
import os

class DatasetManager:
    """Manages creation, querying, and export of datasets from user interactions"""
    
    def __init__(self, base_path: str = "./datasets"):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)
        
    def create_database_from_prompts(self, prompts_data: List[Dict], 
                                   db_name: str = "user_prompts", 
                                   db_type: str = "sqlite") -> str:
        """
        Create a structured database from user prompts and responses
        
        Args:
            prompts_data: List of dictionaries containing prompt data
            db_name: Name for the database
            db_type: Type of database ('sqlite', 'json', 'csv')
            
        Returns:
            Path to created database file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if db_type == "sqlite":
            return self._create_sqlite_database(prompts_data, f"{db_name}_{timestamp}.db")
        elif db_type == "json":
            return self._create_json_database(prompts_data, f"{db_name}_{timestamp}.json")
        elif db_type == "csv":
            return self._create_csv_database(prompts_data, f"{db_name}_{timestamp}.csv")
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
    
    def _create_sqlite_database(self, data: List[Dict], filename: str) -> str:
        """Create SQLite database from prompt data"""
        db_path = os.path.join(self.base_path, filename)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create main prompts table
        cursor.execute('''
            CREATE TABLE prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_prompt TEXT NOT NULL,
                ai_response TEXT,
                category TEXT,
                sentiment TEXT,
                complexity_score REAL DEFAULT 0.5,
                response_time_ms INTEGER,
                user_rating INTEGER,
                feedback_text TEXT,
                data_sources TEXT,
                confidence_score REAL DEFAULT 0.5,
                created_at TEXT NOT NULL
            )
        ''')
        
        # Create categories table for better organization
        cursor.execute('''
            CREATE TABLE categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL
            )
        ''')
        
        # Create analytics view
        cursor.execute('''
            CREATE VIEW prompt_analytics AS
            SELECT 
                category,
                COUNT(*) as total_prompts,
                AVG(user_rating) as avg_rating,
                AVG(complexity_score) as avg_complexity,
                AVG(response_time_ms) as avg_response_time,
                AVG(confidence_score) as avg_confidence
            FROM prompts 
            WHERE user_rating IS NOT NULL
            GROUP BY category
        ''')
        
        # Insert data
        categories = set()
        for item in data:
            category = item.get('category', 'general')
            categories.add(category)
            
            cursor.execute('''
                INSERT INTO prompts 
                (timestamp, user_prompt, ai_response, category, sentiment, 
                 complexity_score, response_time_ms, user_rating, feedback_text,
                 data_sources, confidence_score, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                item.get('timestamp', datetime.now().isoformat()),
                item.get('user_prompt', ''),
                item.get('ai_response', ''),
                category,
                item.get('sentiment', 'neutral'),
                item.get('complexity_score', 0.5),
                item.get('response_time_ms'),
                item.get('user_rating'),
                item.get('feedback_text'),
                json.dumps(item.get('data_sources', [])),
                item.get('confidence_score', 0.5),
                datetime.now().isoformat()
            ))
        
        # Insert categories
        for category in categories:
            cursor.execute('''
                INSERT OR IGNORE INTO categories (name, description, created_at)
                VALUES (?, ?, ?)
            ''', (category, f"Auto-generated category for {category} prompts", 
                  datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        print(f"✅ SQLite database created: {db_path}")
        print(f"   - {len(data)} records inserted")
        print(f"   - {len(categories)} categories created")
        
        return db_path
    
    def _create_json_database(self, data: List[Dict], filename: str) -> str:
        """Create structured JSON database"""
        db_path = os.path.join(self.base_path, filename)
        
        # Structure the data with metadata
        structured_data = {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "total_records": len(data),
                "version": "1.0",
                "format": "user_prompt_database"
            },
            "categories": {},
            "prompts": []
        }
        
        # Process and categorize data
        category_stats = {}
        for item in data:
            category = item.get('category', 'general')
            
            # Track category statistics
            if category not in category_stats:
                category_stats[category] = {
                    "count": 0,
                    "avg_rating": 0,
                    "total_rating": 0,
                    "rated_count": 0
                }
            
            category_stats[category]["count"] += 1
            if item.get('user_rating'):
                category_stats[category]["total_rating"] += item['user_rating']
                category_stats[category]["rated_count"] += 1
            
            # Add structured prompt data
            structured_item = {
                "id": str(uuid.uuid4()),
                "timestamp": item.get('timestamp', datetime.now().isoformat()),
                "user_prompt": item.get('user_prompt', ''),
                "ai_response": item.get('ai_response', ''),
                "category": category,
                "metadata": {
                    "sentiment": item.get('sentiment', 'neutral'),
                    "complexity_score": item.get('complexity_score', 0.5),
                    "response_time_ms": item.get('response_time_ms'),
                    "confidence_score": item.get('confidence_score', 0.5),
                    "data_sources": item.get('data_sources', [])
                },
                "feedback": {
                    "user_rating": item.get('user_rating'),
                    "feedback_text": item.get('feedback_text')
                }
            }
            structured_data["prompts"].append(structured_item)
        
        # Calculate category averages
        for category, stats in category_stats.items():
            avg_rating = stats["total_rating"] / max(stats["rated_count"], 1)
            structured_data["categories"][category] = {
                "total_prompts": stats["count"],
                "average_rating": round(avg_rating, 2) if stats["rated_count"] > 0 else None,
                "rated_prompts": stats["rated_count"]
            }
        
        # Save to file
        with open(db_path, 'w', encoding='utf-8') as f:
            json.dump(structured_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ JSON database created: {db_path}")
        print(f"   - {len(data)} records")
        print(f"   - {len(structured_data['categories'])} categories")
        
        return db_path
    
    def _create_csv_database(self, data: List[Dict], filename: str) -> str:
        """Create CSV database for easy analysis"""
        db_path = os.path.join(self.base_path, filename)
        
        # Flatten the data for CSV format
        flattened_data = []
        for item in data:
            flat_item = {
                'id': str(uuid.uuid4()),
                'timestamp': item.get('timestamp', datetime.now().isoformat()),
                'user_prompt': item.get('user_prompt', ''),
                'ai_response': item.get('ai_response', ''),
                'category': item.get('category', 'general'),
                'sentiment': item.get('sentiment', 'neutral'),
                'complexity_score': item.get('complexity_score', 0.5),
                'response_time_ms': item.get('response_time_ms'),
                'user_rating': item.get('user_rating'),
                'feedback_text': item.get('feedback_text', ''),
                'confidence_score': item.get('confidence_score', 0.5),
                'data_sources': ','.join(item.get('data_sources', [])),
                'prompt_length': len(item.get('user_prompt', '')),
                'response_length': len(item.get('ai_response', '')),
                'created_at': datetime.now().isoformat()
            }
            flattened_data.append(flat_item)
        
        # Create DataFrame and save as CSV
        df = pd.DataFrame(flattened_data)
        df.to_csv(db_path, index=False, encoding='utf-8')
        
        print(f"✅ CSV database created: {db_path}")
        print(f"   - {len(data)} records")
        print(f"   - {len(df.columns)} columns")
        
        return db_path
    
    def query_sqlite_database(self, db_path: str, query: str) -> List[Dict]:
        """Execute SQL query on SQLite database"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(query)
        columns = [description[0] for description in cursor.description]
        results = cursor.fetchall()
        
        conn.close()
        
        return [dict(zip(columns, row)) for row in results]
    
    def view_database_summary(self, db_path: str, db_type: str = "sqlite") -> Dict:
        """Get summary statistics of the database"""
        if db_type == "sqlite":
            return self._view_sqlite_summary(db_path)
        elif db_type == "json":
            return self._view_json_summary(db_path)
        elif db_type == "csv":
            return self._view_csv_summary(db_path)
    
    def _view_sqlite_summary(self, db_path: str) -> Dict:
        """Get SQLite database summary"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Basic stats
        cursor.execute("SELECT COUNT(*) FROM prompts")
        total_prompts = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT category) FROM prompts")
        total_categories = cursor.fetchone()[0]
        
        cursor.execute("SELECT AVG(user_rating) FROM prompts WHERE user_rating IS NOT NULL")
        avg_rating = cursor.fetchone()[0] or 0
        
        # Category breakdown
        cursor.execute("SELECT * FROM prompt_analytics ORDER BY total_prompts DESC")
        columns = [description[0] for description in cursor.description]
        category_stats = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        # Recent activity
        cursor.execute('''
            SELECT DATE(timestamp) as date, COUNT(*) as prompts
            FROM prompts
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
            LIMIT 7
        ''')
        recent_activity = [{"date": row[0], "prompts": row[1]} for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            "database_path": db_path,
            "database_type": "SQLite",
            "total_prompts": total_prompts,
            "total_categories": total_categories,
            "average_rating": round(avg_rating, 2),
            "category_breakdown": category_stats,
            "recent_activity": recent_activity
        }
    
    def _view_json_summary(self, db_path: str) -> Dict:
        """Get JSON database summary"""
        with open(db_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return {
            "database_path": db_path,
            "database_type": "JSON",
            "metadata": data.get("metadata", {}),
            "total_prompts": len(data.get("prompts", [])),
            "categories": data.get("categories", {}),
            "sample_prompt": data["prompts"][0] if data.get("prompts") else None
        }
    
    def _view_csv_summary(self, db_path: str) -> Dict:
        """Get CSV database summary"""
        df = pd.read_csv(db_path)
        
        return {
            "database_path": db_path,
            "database_type": "CSV",
            "total_records": len(df),
            "columns": list(df.columns),
            "categories": df['category'].value_counts().to_dict(),
            "average_rating": df['user_rating'].mean() if 'user_rating' in df.columns else None,
            "date_range": {
                "first": df['timestamp'].min() if 'timestamp' in df.columns else None,
                "last": df['timestamp'].max() if 'timestamp' in df.columns else None
            }
        }
    
    def export_for_ai_training(self, db_path: str, db_type: str = "sqlite", 
                             format_type: str = "bedrock", quality_filter: bool = True) -> str:
        """Export database in format suitable for AI model training"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_filename = f"ai_training_export_{timestamp}.jsonl"
        export_path = os.path.join(self.base_path, export_filename)
        
        # Get data based on database type
        if db_type == "sqlite":
            if quality_filter:
                query = "SELECT * FROM prompts WHERE user_rating >= 3 AND ai_response IS NOT NULL AND ai_response != ''"
            else:
                query = "SELECT * FROM prompts WHERE ai_response IS NOT NULL AND ai_response != ''"
            data = self.query_sqlite_database(db_path, query)
        elif db_type == "json":
            with open(db_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            data = json_data.get("prompts", [])
            if quality_filter:
                data = [item for item in data if item.get("feedback", {}).get("user_rating", 0) >= 3]
        elif db_type == "csv":
            df = pd.read_csv(db_path)
            if quality_filter:
                df = df[(df['user_rating'] >= 3) & (df['ai_response'].notna()) & (df['ai_response'] != '')]
            data = df.to_dict('records')
        
        # Format for AI training
        training_data = []
        for item in data:
            if format_type == "bedrock":
                training_item = {
                    "messages": [
                        {"role": "user", "content": item.get("user_prompt", "")},
                        {"role": "assistant", "content": item.get("ai_response", "")}
                    ],
                    "metadata": {
                        "category": item.get("category", "general"),
                        "rating": item.get("user_rating"),
                        "confidence": item.get("confidence_score", 0.5)
                    }
                }
            elif format_type == "openai":
                training_item = {
                    "messages": [
                        {"role": "system", "content": f"You are a helpful AI assistant specializing in {item.get('category', 'general')} questions."},
                        {"role": "user", "content": item.get("user_prompt", "")},
                        {"role": "assistant", "content": item.get("ai_response", "")}
                    ]
                }
            else:  # Simple format
                training_item = {
                    "input": item.get("user_prompt", ""),
                    "output": item.get("ai_response", ""),
                    "category": item.get("category", "general")
                }
            
            training_data.append(training_item)
        
        # Save as JSONL (each line is a JSON object)
        with open(export_path, 'w', encoding='utf-8') as f:
            for item in training_data:
                f.write(json.dumps(item) + '\n')
        
        print(f"✅ AI training data exported: {export_path}")
        print(f"   - {len(training_data)} training examples")
        print(f"   - Format: {format_type}")
        
        return export_path

# Example usage and demonstration
if __name__ == "__main__":
    print("🗄️  Dataset Manager Demo")
    
    # Initialize dataset manager
    dm = DatasetManager("./demo_datasets")
    
    # Sample prompt data
    sample_data = [
        {
            "timestamp": "2024-10-15T10:30:00Z",
            "user_prompt": "What is John's attendance rate?",
            "ai_response": "John has 85% attendance this month with 17 out of 20 days present.",
            "category": "attendance",
            "sentiment": "neutral",
            "complexity_score": 0.3,
            "response_time_ms": 1200,
            "user_rating": 5,
            "feedback_text": "Perfect answer!",
            "data_sources": ["s3_bucket", "attendance_records"],
            "confidence_score": 0.9
        },
        {
            "timestamp": "2024-10-15T10:35:00Z", 
            "user_prompt": "Tell me the latest news",
            "ai_response": "I couldn't fetch the news right now. Please try again later.",
            "category": "news",
            "sentiment": "negative",
            "complexity_score": 0.5,
            "response_time_ms": 800,
            "user_rating": 2,
            "feedback_text": "Didn't work at all",
            "data_sources": ["news_api"],
            "confidence_score": 0.3
        },
        {
            "timestamp": "2024-10-15T10:40:00Z",
            "user_prompt": "Explain quantum computing",
            "ai_response": "Quantum computing uses quantum mechanical phenomena like superposition and entanglement to process information in ways that classical computers cannot.",
            "category": "education",
            "sentiment": "neutral",
            "complexity_score": 0.8,
            "response_time_ms": 2000,
            "user_rating": 4,
            "feedback_text": "Good explanation but could be simpler",
            "data_sources": ["knowledge_base"],
            "confidence_score": 0.7
        }
    ]
    
    print(f"\n📊 Creating databases from {len(sample_data)} sample prompts...")
    
    # Create different database formats
    sqlite_path = dm.create_database_from_prompts(sample_data, "sample_prompts", "sqlite")
    json_path = dm.create_database_from_prompts(sample_data, "sample_prompts", "json")
    csv_path = dm.create_database_from_prompts(sample_data, "sample_prompts", "csv")
    
    print(f"\n🔍 Database Summaries:")
    
    # SQLite summary
    print(f"\n📋 SQLite Summary:")
    sqlite_summary = dm.view_database_summary(sqlite_path, "sqlite")
    print(json.dumps(sqlite_summary, indent=2, default=str))
    
    # Query examples
    print(f"\n🔎 Sample Queries:")
    high_rated = dm.query_sqlite_database(sqlite_path, "SELECT user_prompt, user_rating FROM prompts WHERE user_rating >= 4")
    print(f"High-rated prompts: {len(high_rated)}")
    for prompt in high_rated:
        print(f"  - '{prompt['user_prompt'][:50]}...' (Rating: {prompt['user_rating']})")
    
    # JSON summary
    print(f"\n📄 JSON Summary:")
    json_summary = dm.view_database_summary(json_path, "json")
    print(json.dumps(json_summary, indent=2, default=str))
    
    # Export for AI training
    print(f"\n🤖 Exporting for AI Training:")
    training_file = dm.export_for_ai_training(sqlite_path, "sqlite", "bedrock", True)
    
    print(f"\n✅ Demo complete! Check the ./demo_datasets folder for created files.")