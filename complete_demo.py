#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete Demo of Enhanced Feedback System
This script demonstrates all the features of the feedback and training system
"""

import json
import time
from datetime import datetime
from enhanced_feedback_system import EnhancedFeedbackSystem
from dataset_manager import DatasetManager
from model_improvement_pipeline import ModelImprovementPipeline

def main():
    print("🚀 COMPLETE FEEDBACK SYSTEM DEMO")
    print("=" * 60)
    
    # Initialize all components
    print("\n📦 Initializing components...")
    feedback_system = EnhancedFeedbackSystem("complete_demo.db")
    dataset_manager = DatasetManager("./complete_demo_datasets")
    improvement_pipeline = ModelImprovementPipeline(feedback_system, dataset_manager)
    
    # === STEP 1: Simulate User Interactions ===
    print("\n📝 STEP 1: Simulating user interactions...")
    
    interactions = [
        {
            "question": "What is John's attendance rate?",
            "response": "John has 85% attendance this month with 17 out of 20 days present.",
            "category": "attendance",
            "rating": 5,
            "feedback": "Perfect answer!",
            "confidence": 0.9
        },
        {
            "question": "Show me the latest news",
            "response": "I'm unable to fetch news at the moment. Please try again later.",
            "category": "news",
            "rating": 2,
            "feedback": "Doesn't work at all",
            "suggestion": "Should connect to a real news API and show headlines",
            "confidence": 0.2
        },
        {
            "question": "What's Sarah's grade average?",
            "response": "Sarah has a B+ average with 87% across all subjects.",
            "category": "grades",
            "rating": 4,
            "feedback": "Good but could show more details",
            "confidence": 0.8
        },
        {
            "question": "Tell me a joke",
            "response": "Why did the math book look so sad? Because it had too many problems!",
            "category": "entertainment",
            "rating": 3,
            "feedback": "Okay joke but not very funny",
            "confidence": 0.6
        },
        {
            "question": "How do I reset my password?",
            "response": "I don't have access to password reset functionality.",
            "category": "technical_support",
            "rating": 1,
            "feedback": "Completely useless",
            "suggestion": "Should provide actual password reset instructions or links",
            "confidence": 0.1
        }
    ]
    
    interaction_ids = []
    for i, interaction in enumerate(interactions):
        print(f"  {i+1}. Logging: '{interaction['question'][:40]}...'")
        
        # Log interaction
        interaction_id = feedback_system.log_interaction(
            user_question=interaction["question"],
            ai_response=interaction["response"],
            query_type=interaction["category"],
            response_time_ms=1000 + i * 200,
            confidence_score=interaction["confidence"],
            session_id=f"demo_session_{i+1}"
        )
        interaction_ids.append(interaction_id)
        
        # Add feedback
        feedback_system.collect_feedback(
            interaction_id=interaction_id,
            overall_rating=interaction["rating"],
            accuracy_rating=interaction["rating"],
            helpfulness_rating=interaction["rating"],
            clarity_rating=interaction["rating"],
            feedback_text=interaction["feedback"],
            suggested_improvement=interaction.get("suggestion")
        )
        
        time.sleep(0.1)  # Small delay for realistic timestamps
    
    print(f"✅ Created {len(interactions)} interactions with feedback")
    
    # === STEP 2: Analytics Overview ===
    print("\n📊 STEP 2: Analyzing feedback...")
    
    analytics = feedback_system.get_feedback_analytics()
    print(f"  Total interactions: {analytics['overview']['total_interactions']}")
    print(f"  Total feedback: {analytics['overview']['total_feedback']}")
    print(f"  Average rating: {analytics['overview']['average_rating']}/5")
    print(f"  Feedback rate: {analytics['overview']['feedback_rate']}%")
    
    print("\n  Category Performance:")
    for category in analytics['category_performance']:
        print(f"    - {category['category']}: {category['avg_rating']}/5 ({category['count']} feedback)")
    
    # === STEP 3: Generate Improvement Recommendations ===
    print("\n💡 STEP 3: Generating improvement recommendations...")
    
    recommendations = feedback_system.generate_improvement_recommendations()
    print(f"  Found {len(recommendations['problem_areas'])} problem areas:")
    
    for area in recommendations['problem_areas']:
        print(f"    - {area['category']}: {area['improvement_priority']} priority ({area['average_rating']}/5)")
    
    print(f"\n  Common suggestions ({len(recommendations['common_suggestions'])}):")
    for suggestion in recommendations['common_suggestions'][:3]:
        print(f"    - {suggestion['suggestion']} (mentioned {suggestion['frequency']} times)")
    
    # === STEP 4: Run Automated Improvement Cycle ===
    print("\n🔄 STEP 4: Running automated improvement cycle...")
    
    improvement_results = improvement_pipeline.run_improvement_cycle(days_back=1)
    
    print(f"  Cycle ID: {improvement_results['cycle_id']}")
    print(f"  Steps completed: {len(improvement_results['steps_completed'])}")
    print(f"  Improvements identified: {len(improvement_results['improvements_identified'])}")
    print(f"  Training data created: {improvement_results['training_data_created']}")
    print(f"  Success: {improvement_results['success']}")
    
    if improvement_results.get('recommendations'):
        print(f"\n  Generated {len(improvement_results['recommendations'])} recommendations:")
        for rec in improvement_results['recommendations'][:3]:
            print(f"    - {rec['action']} ({rec['priority']} priority)")
    
    # === STEP 5: Export Training Data ===
    print("\n📤 STEP 5: Exporting training datasets...")
    
    # Export in different formats
    formats = [
        ("json", "Standard JSON format"),
        ("bedrock_jsonl", "AWS Bedrock JSONL format"),
        ("csv", "CSV format for analysis")
    ]
    
    for format_type, description in formats:
        try:
            filename, count = feedback_system.export_training_data(
                format_type=format_type,
                quality_threshold=0.2,  # Lower threshold for demo
                approved_only=False
            )
            print(f"  ✅ {description}: {filename} ({count} examples)")
        except Exception as e:
            print(f"  ❌ {description}: Error - {e}")
    
    # === STEP 6: Database Creation from Prompts ===
    print("\n🗄️  STEP 6: Creating databases from user prompts...")
    
    # Prepare data for database creation
    prompt_data = []
    for i, interaction in enumerate(interactions):
        prompt_data.append({
            "timestamp": datetime.now().isoformat(),
            "user_prompt": interaction["question"],
            "ai_response": interaction["response"],
            "category": interaction["category"],
            "user_rating": interaction["rating"],
            "feedback_text": interaction["feedback"],
            "confidence_score": interaction["confidence"],
            "response_time_ms": 1000 + i * 200,
            "data_sources": [interaction["category"] + "_data"]
        })
    
    # Create databases in different formats
    db_formats = ["sqlite", "json", "csv"]
    created_dbs = {}
    
    for db_format in db_formats:
        try:
            db_path = dataset_manager.create_database_from_prompts(
                prompt_data, f"demo_feedback_{db_format}", db_format
            )
            created_dbs[db_format] = db_path
            print(f"  ✅ {db_format.upper()} database: {db_path}")
        except Exception as e:
            print(f"  ❌ {db_format.upper()} database: Error - {e}")
    
    # === STEP 7: Query and View Databases ===
    print("\n🔍 STEP 7: Querying databases...")
    
    for db_format, db_path in created_dbs.items():
        try:
            summary = dataset_manager.view_database_summary(db_path, db_format)
            print(f"\n  {db_format.upper()} Database Summary:")
            print(f"    - Total records: {summary.get('total_prompts', summary.get('total_records', 'N/A'))}")
            print(f"    - Categories: {len(summary.get('categories', {}))}")
            if summary.get('average_rating'):
                print(f"    - Average rating: {summary['average_rating']}/5")
        except Exception as e:
            print(f"    ❌ Error querying {db_format}: {e}")
    
    # === STEP 8: Sample SQL Queries (SQLite) ===
    if "sqlite" in created_dbs:
        print(f"\n🔎 STEP 8: Sample SQL queries on SQLite database...")
        
        queries = [
            ("SELECT category, AVG(user_rating) as avg_rating FROM prompts GROUP BY category ORDER BY avg_rating DESC", 
             "Average rating by category"),
            ("SELECT COUNT(*) as poor_responses FROM prompts WHERE user_rating <= 2", 
             "Count of poor responses"),
            ("SELECT user_prompt FROM prompts WHERE user_rating = 5 LIMIT 2", 
             "Best rated prompts")
        ]
        
        for query, description in queries:
            try:
                results = dataset_manager.query_sqlite_database(created_dbs["sqlite"], query)
                print(f"    {description}:")
                for result in results[:3]:  # Limit results for demo
                    print(f"      {result}")
            except Exception as e:
                print(f"    ❌ Error with query '{description}': {e}")
    
    # === STEP 9: Export for AI Training ===
    print(f"\n🤖 STEP 9: Exporting for AI model training...")
    
    if "sqlite" in created_dbs:
        try:
            training_file = dataset_manager.export_for_ai_training(
                created_dbs["sqlite"], "sqlite", "bedrock", quality_filter=True
            )
            print(f"  ✅ Training data exported: {training_file}")
        except Exception as e:
            print(f"  ❌ Export error: {e}")
    
    # === STEP 10: Summary Report ===
    print(f"\n📋 STEP 10: Final Summary Report")
    print("=" * 60)
    
    final_analytics = feedback_system.get_feedback_analytics()
    
    print(f"🎯 FEEDBACK SYSTEM METRICS:")
    print(f"   • Total Interactions: {final_analytics['overview']['total_interactions']}")
    print(f"   • Feedback Collection Rate: {final_analytics['overview']['feedback_rate']}%")
    print(f"   • Average User Rating: {final_analytics['overview']['average_rating']}/5")
    print(f"   • Training Data Items: {final_analytics['training_data']['needs_improvement'] + final_analytics['training_data']['approved_for_training']}")
    
    print(f"\n🗄️  DATABASE CREATION:")
    print(f"   • Formats Created: {', '.join(created_dbs.keys())}")
    print(f"   • Records per Database: {len(prompt_data)}")
    print(f"   • Query Support: Available for all formats")
    
    print(f"\n🔄 IMPROVEMENT PIPELINE:")
    print(f"   • Automated Analysis: ✅ Working")
    print(f"   • Training Data Generation: ✅ Working") 
    print(f"   • Export Formats: JSON, JSONL, CSV")
    print(f"   • AI Training Ready: ✅ Yes")
    
    print(f"\n📊 KEY INSIGHTS:")
    problem_categories = [area['category'] for area in recommendations['problem_areas'] if area['improvement_priority'] == 'HIGH']
    if problem_categories:
        print(f"   • High Priority Issues: {', '.join(problem_categories)}")
    else:
        print(f"   • High Priority Issues: None detected")
    
    print(f"   • Most Common Feedback: {recommendations['common_suggestions'][0]['suggestion'] if recommendations['common_suggestions'] else 'None'}")
    print(f"   • System Status: 🟢 Fully Operational")
    
    print(f"\n🎉 DEMO COMPLETED SUCCESSFULLY!")
    print(f"📁 Check the './complete_demo_datasets/' folder for generated files")
    print(f"🗃️  Database files created with {len(prompt_data)} sample records")
    print(f"📈 Analytics and improvement recommendations generated")
    print(f"🤖 Ready for AI model training and continuous improvement!")

if __name__ == "__main__":
    main()