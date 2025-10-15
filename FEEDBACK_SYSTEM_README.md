# 🤖 Enhanced AI Feedback & Training System

A comprehensive feedback collection and model improvement system that automatically creates databases from user interactions, collects feedback, and prepares training data for AI model improvements.

## 🎯 What This System Does

### 1. **Database Creation from User Prompts**
- **Formats**: SQLite, JSON, CSV
- **Automatic Structuring**: Organizes user interactions with metadata
- **Query Support**: Full SQL querying for SQLite, structured JSON/CSV access
- **Export Options**: Multiple formats for different use cases

### 2. **Intelligent Feedback Collection**
- **Periodic Prompts**: Asks users for feedback every N interactions
- **5-Star Rating System**: Overall, accuracy, helpfulness, clarity ratings
- **Text Feedback**: Optional detailed user feedback
- **Improvement Suggestions**: Users can suggest specific improvements

### 3. **Automated Model Improvement**
- **Smart Analysis**: Identifies problem areas automatically
- **Training Data Generation**: Creates datasets from poor-rated interactions
- **Multiple Export Formats**: AWS Bedrock JSONL, OpenAI format, standard JSON
- **Quality Filtering**: Only includes high-quality training examples

## 📊 Database Formats & Usage

### SQLite Database
```sql
-- Query examples
SELECT category, AVG(user_rating) FROM prompts GROUP BY category;
SELECT * FROM prompts WHERE user_rating <= 2;
SELECT COUNT(*) FROM prompts WHERE category = 'attendance';
```

### JSON Database
```json
{
  "metadata": {
    "created_at": "2024-10-15T10:30:00Z",
    "total_records": 100
  },
  "categories": {
    "attendance": {"total_prompts": 50, "average_rating": 4.2}
  },
  "prompts": [
    {
      "id": "uuid",
      "user_prompt": "What is John's attendance?",
      "ai_response": "John has 85% attendance...",
      "category": "attendance",
      "feedback": {"user_rating": 5, "feedback_text": "Perfect!"}
    }
  ]
}
```

### CSV Database
Perfect for data analysis with pandas:
```python
import pandas as pd
df = pd.read_csv('feedback_data.csv')
print(df.groupby('category')['user_rating'].mean())
```

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Complete Demo
```bash
python complete_demo.py
```

### 3. Start Main Application
```bash
python app.py
```

### 4. Access Interfaces
- **Main Chat**: http://localhost:7860/
- **Analytics Dashboard**: http://localhost:7860/admin/dashboard
- **API Documentation**: http://localhost:7860/api/info

## 🛠️ Core Components

### Enhanced Feedback System (`enhanced_feedback_system.py`)
- Comprehensive feedback collection
- Training data generation
- Performance analytics
- Improvement recommendations

### Dataset Manager (`dataset_manager.py`)
- Database creation from user prompts
- Multiple format support (SQLite, JSON, CSV)
- Query and export functionality
- AI training data preparation

### Model Improvement Pipeline (`model_improvement_pipeline.py`)
- Automated analysis of feedback
- Identifies improvement areas
- Generates training datasets
- Creates improvement recommendations

### Analytics Dashboard (`feedback_analytics_dashboard.py`)
- Web-based analytics interface
- Real-time performance metrics
- Category performance tracking
- Export and download functionality

## 📈 How Feedback Collection Works

### Automatic Prompts
The system automatically asks for feedback based on:
- **Frequency**: Every N interactions (configurable)
- **User Preferences**: Respects opt-out settings
- **Context**: Different prompts for different situations

### Feedback Processing
1. **Collection**: Star ratings + text feedback
2. **Analysis**: Identifies poor performance areas
3. **Training Data**: Automatically creates training examples
4. **Recommendations**: Generates specific improvement suggestions

## 🗄️ Database Creation Process

### From User Interactions
```python
from dataset_manager import DatasetManager

dm = DatasetManager()

# Your interaction data
interactions = [
    {
        "user_prompt": "What's the weather?",
        "ai_response": "I can't access weather data",
        "category": "weather",
        "user_rating": 2,
        "feedback_text": "Doesn't work"
    }
]

# Create databases
sqlite_db = dm.create_database_from_prompts(interactions, "weather_feedback", "sqlite")
json_db = dm.create_database_from_prompts(interactions, "weather_feedback", "json")
csv_db = dm.create_database_from_prompts(interactions, "weather_feedback", "csv")
```

### Querying Databases
```python
# SQLite queries
results = dm.query_sqlite_database(sqlite_db, "SELECT * FROM prompts WHERE user_rating < 3")

# View summaries
sqlite_summary = dm.view_database_summary(sqlite_db, "sqlite")
json_summary = dm.view_database_summary(json_db, "json")
```

## 🤖 AI Model Training Integration

### Export Training Data
```python
from enhanced_feedback_system import EnhancedFeedbackSystem

efs = EnhancedFeedbackSystem()

# Export for AWS Bedrock
bedrock_file, count = efs.export_training_data("bedrock_jsonl")

# Export for OpenAI
openai_file, count = efs.export_training_data("openai")

# Export standard JSON
json_file, count = efs.export_training_data("json")
```

### Training Data Formats

#### AWS Bedrock JSONL
```json
{"messages": [{"role": "user", "content": "Question"}, {"role": "assistant", "content": "Answer"}]}
{"messages": [{"role": "user", "content": "Question 2"}, {"role": "assistant", "content": "Answer 2"}]}
```

#### OpenAI Format
```json
{
  "messages": [
    {"role": "system", "content": "You are a helpful assistant..."},
    {"role": "user", "content": "Question"},
    {"role": "assistant", "content": "Answer"}
  ]
}
```

## 📊 Analytics & Monitoring

### Key Metrics
- **Feedback Rate**: Percentage of interactions with feedback
- **Average Rating**: Overall user satisfaction
- **Category Performance**: Rating by interaction type
- **Response Time**: AI response performance
- **Improvement Areas**: Identified problem categories

### Dashboard Features
- Real-time analytics
- Interactive charts
- Feedback management
- Training data export
- Improvement recommendations

## 🔄 Automated Improvement Pipeline

### How It Works
1. **Analyze Feedback**: Reviews recent user feedback
2. **Identify Issues**: Finds categories with poor ratings
3. **Create Training Data**: Generates examples from feedback
4. **Export for Training**: Prepares data in ML-ready formats
5. **Generate Recommendations**: Provides specific improvement suggestions

### Running Improvement Cycles
```python
from model_improvement_pipeline import ModelImprovementPipeline

pipeline = ModelImprovementPipeline(feedback_system, dataset_manager)
results = pipeline.run_improvement_cycle(days_back=7)

print(f"Found {len(results['improvements_identified'])} areas for improvement")
print(f"Created {results['training_data_created']} training examples")
```

## 🔗 API Endpoints

### Feedback Collection
```bash
POST /api/feedback/submit
{
  "rating": 4,
  "feedback_text": "Good response but could be clearer",
  "session_id": "user_session_123"
}
```

### Analytics
```bash
GET /api/admin/analytics/overview
GET /api/admin/analytics/categories
GET /api/admin/analytics/trends?days=30
```

### Training Data Export
```bash
POST /api/admin/training/export
{
  "format": "bedrock_jsonl",
  "quality_threshold": 0.3,
  "approved_only": true
}
```

### Improvement Pipeline
```bash
POST /api/admin/improvement/run
{
  "days_back": 7
}
```

## 🎛️ Configuration

### Feedback Frequency
```python
# User can be asked for feedback every N interactions
feedback_system.update_user_preferences(
    user_id="user123",
    feedback_frequency=5,  # Every 5 interactions
    feedback_opt_out=False
)
```

### Quality Thresholds
```python
# Only include high-quality training data
training_data = feedback_system.get_training_dataset(
    quality_threshold=0.7,  # Only ratings 3.5+ stars
    approved_only=True
)
```

## 📁 File Structure

```
📦 feedback-system/
├── 📄 app.py                           # Main Flask application
├── 📄 enhanced_feedback_system.py      # Core feedback system
├── 📄 dataset_manager.py               # Database creation & management
├── 📄 model_improvement_pipeline.py    # Automated improvement
├── 📄 feedback_analytics_dashboard.py  # Web analytics interface
├── 📄 complete_demo.py                 # Comprehensive demonstration
├── 📄 requirements.txt                 # Python dependencies
├── 📁 datasets/                        # Generated databases
├── 📁 training_data/                   # Exported training files
└── 📄 README.md                        # This file
```

## ✨ Key Features

### ✅ Automatic Database Creation
- **Multiple Formats**: SQLite, JSON, CSV
- **Structured Data**: Organized with metadata
- **Query Support**: Full SQL and programmatic access

### ✅ Smart Feedback Collection
- **Periodic Prompts**: User-configurable frequency
- **Multi-dimensional Ratings**: Overall, accuracy, helpfulness, clarity
- **Improvement Suggestions**: Direct user input for improvements

### ✅ Automated Model Improvement
- **Problem Detection**: Identifies low-performing areas
- **Training Data Generation**: Creates ML-ready datasets
- **Multiple Export Formats**: AWS Bedrock, OpenAI, standard JSON

### ✅ Real-time Analytics
- **Performance Monitoring**: Track ratings and response times
- **Category Analysis**: Performance by interaction type
- **Trend Analysis**: Historical performance tracking

### ✅ Easy Integration
- **Flask Integration**: Seamless integration with existing apps
- **API Endpoints**: RESTful API for all functionality
- **Web Dashboard**: User-friendly analytics interface

## 🎯 Use Cases

### 1. Customer Support Chatbots
- Collect feedback on support responses
- Identify common problem areas
- Create training data to improve responses

### 2. Educational AI Systems
- Track student satisfaction with explanations
- Improve subject-specific responses
- Generate training data for better educational content

### 3. Internal Business AI
- Monitor employee satisfaction with AI tools
- Identify workflow bottlenecks
- Continuously improve business processes

### 4. Content Creation AI
- Gather feedback on generated content
- Improve writing quality over time
- Create training datasets for better outputs

## 🔮 Next Steps

1. **Run the Demo**: `python complete_demo.py`
2. **Explore the Dashboard**: Visit the analytics interface
3. **Integrate with Your App**: Use the feedback system in your application
4. **Analyze Results**: Review generated databases and training data
5. **Improve Your AI**: Use exported training data to fine-tune your models

## 🆘 Support

- 📊 **Analytics Dashboard**: Real-time monitoring and insights
- 🗄️ **Database Flexibility**: SQLite, JSON, CSV support
- 📈 **Performance Tracking**: Comprehensive metrics and trends
- 🤖 **AI Training Ready**: Export formats for major ML platforms
- 🔄 **Automated Pipeline**: Continuous improvement without manual intervention

---

**Happy AI Training!** 🚀✨