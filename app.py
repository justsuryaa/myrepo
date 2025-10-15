import os
import json
import boto3
import botocore
import time
import logging
import requests
import re
from datetime import datetime
from functools import wraps
from flask import Flask, request, render_template_string, session, jsonify
from flask_cors import CORS

# Import our database systems
from user_database import UserInteractionDB
from feedback_system import FeedbackTrainingSystem
from enhanced_feedback_system import EnhancedFeedbackSystem
from feedback_analytics_dashboard import add_analytics_to_app

REGION = "us-east-1"
bucket_name = os.environ.get("BUCKET_NAME", "suryaatrial3")
# New bucket for storing conversation logs
conversation_bucket = os.environ.get("CONVERSATION_BUCKET", "promptstorage")

INFERENCE_PROFILE_ARN = os.environ.get(
    "BEDROCK_INFERENCE_PROFILE_ARN",
    "arn:aws:bedrock:us-east-1:705241975254:inference-profile/us.anthropic.claude-3-5-haiku-20241022-v1:0"
)
s3 = boto3.client("s3", region_name=REGION)
bedrock = boto3.client(
    "bedrock-runtime",
    region_name=REGION,
    config=botocore.config.Config(connect_timeout=5, read_timeout=30),
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "your_secret_key_change_this_in_production")

# Enable CORS for cross-origin requests
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database systems
user_db = UserInteractionDB("user_interactions.json")
feedback_system = FeedbackTrainingSystem("school_feedback.db")
enhanced_feedback = EnhancedFeedbackSystem("enhanced_feedback.db")

# Production configurations
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# -----------------------
# Conversation Logging Functions
# -----------------------
def log_conversation_to_s3(query, response, query_type, user, api_key, response_time_ms, ip_address, user_agent=None, error_message=None):
    """Log conversation to S3 bucket in JSON format"""
    try:
        conversation_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        conversation = {
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat(),
            "user": user,
            "api_key": api_key[:10] + "..." if api_key else None,  # Truncate for security
            "query": query,
            "query_type": query_type,
            "response": response,
            "response_length": len(response) if response else 0,
            "response_time_ms": response_time_ms,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "success": error_message is None,
            "error_message": error_message
        }
        
        # Store in S3 with date-based folder structure
        date_path = datetime.now().strftime('%Y/%m/%d')
        key = f"conversations/{date_path}/{conversation_id}.json"
        
        s3.put_object(
            Bucket=conversation_bucket,
            Key=key,
            Body=json.dumps(conversation, indent=2),
            ContentType='application/json'
        )
        
        logger.info(f"Conversation logged to S3: {conversation_id}")
        
    except Exception as e:
        # Don't let logging errors break the main functionality
        logger.error(f"Failed to log conversation to S3: {str(e)}")
        pass

# -----------------------
# API Configuration
# -----------------------
# API Keys for authentication
API_KEYS = {
    "sk-test-12345": {"name": "Test User", "permissions": ["read", "write"]},
    "sk-prod-67890": {"name": "Admin User", "permissions": ["read", "write", "delete"]},
    "sk-school-api-key": {"name": "School Admin", "permissions": ["read", "write"]},
    # Add more API keys as needed
}

# External API configurations
EXTERNAL_APIS = {
    "news": {
        "base_url": "https://newsapi.org/v2/top-headlines",
        "api_key": os.environ.get("NEWS_API_KEY", "e5d7c39b653d47e585dc1232323e7d06"),  # Your News API key
        "enabled": True
    }
}

# -----------------------
# API Authentication
# -----------------------
def require_api_key(f):
    """Decorator to require API key authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('Authorization')
        if not api_key:
            api_key = request.args.get('api_key')
        
        if not api_key:
            return jsonify({"error": "API key is required", "code": "MISSING_API_KEY"}), 401
        
        # Remove 'Bearer ' prefix if present
        if api_key.startswith('Bearer '):
            api_key = api_key[7:]
        
        if api_key not in API_KEYS:
            return jsonify({"error": "Invalid API key", "code": "INVALID_API_KEY"}), 401
        
        # Add user info to request context
        request.api_user = API_KEYS[api_key]
        return f(*args, **kwargs)
    return decorated_function

# -----------------------
# Health check endpoints
# -----------------------
# Returns a simple "I'm alive" message for AWS Load Balancer to check if the app is working
@app.route("/health")
def health():
    """Basic health check for ALB"""
    return jsonify({"status": "healthy", "service": "school-chatbot"}), 200

# Another health check endpoint that just returns "pong" - like playing ping-pong to test connectivity
@app.route("/ping")
def ping():
    """Additional health check endpoint"""
    return "pong", 200

# -----------------------
# Conversation Logging Functions
# -----------------------
def log_conversation_to_s3(query, response, query_type, user_name, api_key, response_time_ms=0):
    """Log conversation data to S3 for analytics and monitoring"""
    try:
        conversation_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        conversation_data = {
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat(),
            "user_name": user_name,
            "api_key": api_key,
            "query": query,
            "query_type": query_type,
            "response": response,
            "response_length": len(response) if response else 0,
            "response_time_ms": response_time_ms,
            "ip_address": request.remote_addr if request else "unknown",
            "user_agent": request.headers.get('User-Agent', 'unknown') if request else "unknown",
            "success": True,
            "error_message": None
        }
        
        # Create S3 key with date-based folder structure
        date_folder = datetime.now().strftime('%Y/%m/%d')
        s3_key = f"conversations/{date_folder}/{conversation_id}.json"
        
        # Upload to S3
        s3.put_object(
            Bucket=conversation_bucket,
            Key=s3_key,
            Body=json.dumps(conversation_data, indent=2),
            ContentType='application/json'
        )
        
        logger.info(f"Conversation logged to S3: {s3_key}")
        
    except Exception as e:
        logger.error(f"Failed to log conversation to S3: {e}")

def log_error_to_s3(query, error_message, query_type, user_name, api_key):
    """Log error conversations to S3"""
    try:
        conversation_id = f"error_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        error_data = {
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat(),
            "user_name": user_name,
            "api_key": api_key,
            "query": query,
            "query_type": query_type,
            "response": None,
            "response_length": 0,
            "response_time_ms": 0,
            "ip_address": request.remote_addr if request else "unknown",
            "user_agent": request.headers.get('User-Agent', 'unknown') if request else "unknown",
            "success": False,
            "error_message": str(error_message)
        }
        
        # Create S3 key with date-based folder structure
        date_folder = datetime.now().strftime('%Y/%m/%d')
        s3_key = f"errors/{date_folder}/{conversation_id}.json"
        
        # Upload to S3
        s3.put_object(
            Bucket=conversation_bucket,
            Key=s3_key,
            Body=json.dumps(error_data, indent=2),
            ContentType='application/json'
        )
        
        logger.info(f"Error logged to S3: {s3_key}")
        
    except Exception as e:
        logger.error(f"Failed to log error to S3: {e}")

# -----------------------
# S3 utility functions
# -----------------------
# Gets a list of all JSON files stored in the specified S3 bucket
def list_json_files(bucket):
    paginator = s3.get_paginator("list_objects_v2")
    json_files = []
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            if obj["Key"].lower().endswith(".json"):
                json_files.append(obj["Key"])
    return json_files

# Downloads all attendance data from S3 bucket and combines it into one big list
def load_s3_data():
    try:
        print("=== LOADING S3 DATA ===")
        data = []
        # List all JSON files in the bucket
        resp = s3.list_objects_v2(Bucket=bucket_name)
        json_files = [obj['Key'] for obj in resp.get('Contents', []) if obj['Key'].endswith('.json')]
        print(f"Found {len(json_files)} JSON files in S3")
        
        for key in json_files:
            try:
                print(f"Loading file: {key}")
                obj = s3.get_object(Bucket=bucket_name, Key=key)
                records = json.loads(obj['Body'].read().decode('utf-8'))
                if isinstance(records, list):
                    data.extend(records)
                else:
                    data.append(records)
                print(f"Loaded {len(records) if isinstance(records, list) else 1} records from {key}")
            except Exception as e:
                print(f"Error loading {key}: {e}")
                logger.error(f"Error loading {key}: {e}")
                continue
        
        # Flatten if we have nested lists
        all_data = []
        for item in data:
            if isinstance(item, list):
                all_data.extend(item)
            else:
                all_data.append(item)
        
        print(f"Total flattened records: {len(all_data)}")
        
    except Exception as e:
        print(f"ERROR in load_s3_data: {e}")
        logger.error(f"Error loading S3 data: {e}")
        all_data = []
    
    logger.info(f"Loaded {len(all_data)} records from S3")
    return all_data

CACHE_TTL = 600  # seconds (10 minutes)
_cached_data = None
_last_cache_time = 0

# Returns S3 data from memory cache to avoid downloading it every time (saves time and money)
def get_cached_s3_data():
    global _cached_data, _last_cache_time
    now = time.time()
    if _cached_data is None or (now - _last_cache_time) > CACHE_TTL:
        _cached_data = load_s3_data()
        _last_cache_time = now
    return _cached_data

# -----------------------
# Intelligent Query Classification
# -----------------------
def classify_query(user_query):
    """
    Determines whether the query is about:
    - S3 attendance data (internal)
    - News (external API)
    - General knowledge (use Bedrock only)
    """
    query_lower = user_query.lower()
    
    # S3 attendance keywords
    attendance_keywords = [
        "attendance", "student", "school", "absent", "present", "class", 
        "roll", "register", "grade", "students", "names", "list",
        "who is", "john", "sarah", "alex", "attendance rate", "missing"
    ]
    
    # News API keywords
    news_keywords = ["news", "headlines", "current events", "today's news", "breaking news", "latest news"]
    
    # Check for S3 attendance queries
    if any(keyword in query_lower for keyword in attendance_keywords):
        return "s3_attendance"
    
    # Check for news queries
    elif any(keyword in query_lower for keyword in news_keywords):
        return "external_news"
    
    # Default to general knowledge (Bedrock only)
    return "general"

# -----------------------
# External API Functions
# -----------------------
def get_news_data(query=""):
    """Get latest news headlines"""
    try:
        if not EXTERNAL_APIS["news"]["enabled"]:
            return {"error": "News service is currently disabled"}
        
        api_key = EXTERNAL_APIS["news"]["api_key"]
        if api_key == "demo_key":
            return {
                "news": [
                    {"title": "Demo News: Technology Advances in Education", "source": "Demo Source"},
                    {"title": "Demo News: School Attendance Tracking Improvements", "source": "Demo Source"}
                ],
                "note": "This is demo data. Set NEWS_API_KEY environment variable for real data."
            }
        
        # Determine country based on query
        country = "us"  # default
        if any(city in query.lower() for city in ["chennai", "mumbai", "delhi", "bangalore", "india", "indian"]):
            country = "in"
        elif any(city in query.lower() for city in ["london", "uk", "britain", "british"]):
            country = "gb"
        
        url = f"{EXTERNAL_APIS['news']['base_url']}?country={country}&apiKey={api_key}&pageSize=5"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            articles = []
            for article in data.get("articles", [])[:5]:
                articles.append({
                    "title": article["title"],
                    "source": article["source"]["name"],
                    "description": article.get("description", "")[:100] + "..."
                })
            return {"news": articles}
        else:
            return {"error": f"News API error: {response.status_code}"}
    except Exception as e:
        return {"error": f"News service error: {str(e)}"}

# -----------------------
# Hybrid Query Processing
# -----------------------
def process_hybrid_query(user_query, history=None):
    """
    Main function that routes queries to appropriate data sources
    """
    start_time = time.time()
    query_type = classify_query(user_query)
    logger.info(f"Query classified as: {query_type}")
    
    try:
        response = ""
        
        if query_type == "s3_attendance":
            # Use S3 data + Bedrock
            all_data = get_cached_s3_data()
            response = query_bedrock(user_query, history or [], all_data)
        
        elif query_type == "external_news":
            # Get news data
            news_data = get_news_data()
            if "error" in news_data:
                response = f"Sorry, I couldn't get news information: {news_data['error']}"
            elif "note" in news_data:
                response = "📰 Latest News Headlines:\n\n"
                for article in news_data["news"]:
                    response += f"• {article['title']} - {article['source']}\n"
                response += f"\nNote: {news_data['note']}"
            else:
                response = "📰 Latest News Headlines:\n\n"
                for article in news_data["news"]:
                    response += f"• {article['title']} - {article['source']}\n"
                    if article.get('description'):
                        response += f"  {article['description']}\n"
        
        else:  # general queries
            # Use Bedrock for general knowledge
            response = query_bedrock(user_query, history or [], [])
        
        # Log the interaction for feedback collection
        response_time = int((time.time() - start_time) * 1000)  # Convert to milliseconds
        interaction_id = feedback_system.log_interaction(
            user_question=user_query,
            ai_response=response,
            query_type=query_type,
            response_time_ms=response_time,
            user_ip=request.remote_addr if request else None,
            session_id=session.get('session_id') if 'session' in globals() else None
        )
        
        return response
    
    except Exception as e:
        logger.error(f"Error in process_hybrid_query: {e}")
        error_response = f"Sorry, I encountered an error processing your request: {str(e)}"
        
        # Log error interactions too
        response_time = int((time.time() - start_time) * 1000)
        feedback_system.log_interaction(
            user_question=user_query,
            ai_response=error_response,
            query_type="error",
            response_time_ms=response_time,
            user_ip=request.remote_addr if request else None
        )
        
        return error_response

# -----------------------
# Summarize and query
# -----------------------
# Takes messy attendance data and formats it nicely for the AI to understand
def summarize_records(records):
    summary = []
    for rec in records:
        name = rec.get("Unnamed: 2", "")
        grade = rec.get("Unnamed: 5", "")
        attendance = rec.get("Unnamed: 8", "")
        present = rec.get("Unnamed: 17", "")
        summary.append(f"Name: {name}, Grade: {grade}, Attendance: {attendance}, Present: {present}")
    return "\n".join(summary)

# The main AI brain - takes user question, finds relevant data, asks AI, and returns smart answer
def query_bedrock(user_prompt: str, history: list, all_data) -> str:
    import re
    logger.info(f"Processing query: {user_prompt[:50]}...")
    
    match = re.search(r"\b([A-Z][a-z]+)\b", user_prompt)
    student_name = match.group(1) if match else None

    if student_name:
        filtered = [record for record in all_data if student_name.lower() in json.dumps(record).lower()]
        sample = filtered if filtered else all_data
        logger.info(f"Filtered {len(sample)} records for student: {student_name}")
    else:
        sample = all_data[:min(100, len(all_data))] if isinstance(all_data, list) else all_data

    keywords = ["attendance", "student", "school", "absent", "present", "class", "roll", "register"]
    if any(word in user_prompt.lower() for word in keywords):
        summary_str = summarize_records(sample)
        user_text = (
            f"{user_prompt}\n\n"
            "Here is a summary of the S3 attendance data for all grades and students:\n"
            f"{summary_str}\n"
            "Please answer the question using this summary. If the sample is insufficient, say so."
        )
    else:
        user_text = user_prompt

    messages = []
    for msg in history:
        if isinstance(msg, dict) and isinstance(msg.get("content", ""), str):
            messages.append({"role": msg.get("role", "user"), "content": [{"text": str(msg.get("content", ""))}]})
    messages.append({"role": "user", "content": [{"text": str(user_text)}]})

    try:
        print("=== SENDING TO BEDROCK ===")
        print(f"Model ID: {INFERENCE_PROFILE_ARN}")
        print(f"Messages count: {len(messages)}")
        logger.info("Sending request to Bedrock...")
        
        resp = bedrock.converse(
            modelId=INFERENCE_PROFILE_ARN,
            messages=messages,
            inferenceConfig={"maxTokens": 256, "temperature": 0.3, "topP": 0.9},
        )
        print("Bedrock response received")
        out = resp.get("output", {}).get("message", {}).get("content", [])
        assistant_text = "".join(part.get("text", "") for part in out if "text" in part)
        print(f"Assistant text: {assistant_text[:100]}...")
        logger.info("Successfully received response from Bedrock")
        return assistant_text or "(No text returned by model)"
    except Exception as e:
        print(f"BEDROCK ERROR: {e}")
        logger.error(f"Bedrock error: {e}")
        return f"Sorry, I'm having trouble processing your request right now. Please try again later. Error: {e}"

# -----------------------
# Main chat route
# -----------------------
# The main webpage - shows the chat interface and processes user questions
@app.route("/", methods=["GET", "POST"])
def index():
    try:
        if "history" not in session:
            session["history"] = []
        
        assistant_text = ""
        if request.method == "POST":
            print("=== POST REQUEST RECEIVED ===")
            user_input = request.form.get("user_input", "").strip()
            print(f"User input: {user_input}")
            if not user_input:
                assistant_text = "Please enter a question."
                print("No user input provided")
            else:
                print(f"Processing user input: {user_input[:50]}...")
                logger.info(f"User input received: {user_input[:50]}...")
                try:
                    print("Processing with hybrid query system...")
                    assistant_text = process_hybrid_query(user_input, session["history"])
                    print(f"Hybrid response: {assistant_text[:100]}...")
                    
                    session["history"].append({"role": "user", "content": user_input})
                    session["history"].append({"role": "assistant", "content": assistant_text})
                    print("Session updated successfully")
                except Exception as e:
                    print(f"ERROR in POST processing: {e}")
                    assistant_text = f"Sorry, there was an error: {e}"
        
        chat_history_html = ""
        for msg in session.get("history", []):
            if msg["role"] == "user":
                chat_history_html += f'<div class="user-msg"><b>You:</b> {msg["content"]}</div>'
            else:
                chat_history_html += f'<div class="ai-msg"><b>AI:</b> {msg["content"]}</div>'
        
        # Check if we should ask for feedback
        should_ask_feedback, feedback_prompt = enhanced_feedback.should_request_feedback(
            session_id=session.get('session_id', 'anonymous')
        )
        
        return render_template_string("""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>School Attendance Chatbot - Auto Deploy v1.0</title>
            <style>
            * { box-sizing: border-box; }
            body { background: #1565c0; color: #fff; font-family: Arial, sans-serif; margin: 0; padding: 10px; }
            .container { background: #fff; color: #1565c0; border-radius: 10px; padding: 20px; max-width: 700px; margin: 20px auto; } 
            input[type="text"] { width: 100%; padding: 12px; border-radius: 5px; border: 1px solid #1565c0; margin-bottom: 10px; font-size: 16px; }
            input[type="submit"] { background: #1565c0; color: #fff; border: none; padding: 12px 20px; border-radius: 5px; cursor: pointer; width: 100%; font-size: 16px; transition: all 0.3s; }
            input[type="submit"]:hover { background: #0d47a1; }
            input[type="submit"]:disabled { background: #ccc; cursor: not-allowed; }
            
            /* Feedback Modal Styles */
            .feedback-modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.5); }
            .feedback-content { background-color: #fff; margin: 10% auto; padding: 20px; border-radius: 10px; width: 90%; max-width: 500px; color: #1565c0; }
            .close { color: #aaa; float: right; font-size: 28px; font-weight: bold; cursor: pointer; }
            .close:hover { color: #000; }
            .rating-stars { font-size: 2em; margin: 15px 0; text-align: center; }
            .star { color: #ddd; cursor: pointer; transition: color 0.2s; }
            .star:hover, .star.selected { color: #ffd700; }
            .feedback-textarea { width: 100%; min-height: 80px; padding: 10px; border: 1px solid #ddd; border-radius: 5px; margin: 10px 0; }
            .feedback-submit { background: #27ae60; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
            .feedback-skip { background: #95a5a6; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin-left: 10px; }
            
            /* Loading Spinner Styles */
            .loading-container { text-align: center; margin: 15px 0; display: none; }
            .spinner { border: 3px solid #e3f2fd; border-top: 3px solid #1565c0; border-radius: 50%; width: 30px; height: 30px; animation: spin 1s linear infinite; display: inline-block; margin-right: 10px; }
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            .loading-text { color: #1565c0; font-style: italic; font-weight: bold; }
            .chat-box { background: #e3f2fd; color: #1565c0; border-radius: 8px; padding: 15px; margin-bottom: 20px; height: 300px; overflow-y: auto; }
            .user-msg { text-align: right; margin: 8px 0; word-wrap: break-word; }
            .ai-msg { text-align: left; margin: 8px 0; word-wrap: break-word; }
            h2 { text-align: center; color: #1565c0; font-size: 1.2em; margin-bottom: 20px; }
            .sample-prompt { color: #1565c0; font-size: 0.9em; margin-bottom: 10px; }
            .error-msg { background: #ffebee; color: #c62828; padding: 10px; border-radius: 5px; margin: 10px 0; border-left: 4px solid #c62828; }
            .success-msg { background: #e8f5e8; color: #2e7d32; padding: 10px; border-radius: 5px; margin: 10px 0; border-left: 4px solid #2e7d32; }
            .feedback-prompt { background: #fff3cd; color: #856404; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #ffc107; }
            .feedback-btn { background: #ffc107; color: #212529; border: none; padding: 8px 16px; border-radius: 5px; cursor: pointer; margin-left: 10px; }
            @media (max-width: 600px) {
                .container { margin: 10px; padding: 15px; }
                h2 { font-size: 1.1em; }
                .chat-box { height: 250px; }
                input[type="text"], input[type="submit"] { font-size: 16px; } /* Prevents zoom on iOS */
                .feedback-content { margin: 5% auto; width: 95%; }
            }
            </style>
        </head>
        <body>
            <div class="container">
                <h2>🎓 SMART SCHOOL ASSISTANT - Attendance • Weather • News • More!</h2>
                
                {% if should_ask_feedback %}
                <div class="feedback-prompt">
                    <strong>💭 Quick Feedback:</strong> {{ feedback_prompt }}
                    <button class="feedback-btn" onclick="showFeedbackModal()">Rate Previous Response</button>
                </div>
                {% endif %}
                
                <form method="post" id="chatForm">
                    <div class="sample-prompt">Try: "John's attendance" | "Latest news" | "Tell me a joke"</div>
                    <input name="user_input" type="text" placeholder="Ask about attendance, news, or anything!" required id="userInput">
                    <input type="submit" value="Submit" id="submitBtn">
                </form>
                <div class="loading-container" id="loadingContainer">
                    <div class="spinner"></div>
                    <span class="loading-text">🤖 AI is thinking... Please wait</span>
                </div>
                <div class="chat-box">{{chat_history_html|safe}}</div>
            </div>
            
            <!-- Feedback Modal -->
            <div id="feedbackModal" class="feedback-modal">
                <div class="feedback-content">
                    <span class="close" onclick="closeFeedbackModal()">&times;</span>
                    <h3>📝 How was my response?</h3>
                    <p>Please rate the helpfulness of my previous answer:</p>
                    
                    <div class="rating-stars" id="ratingStars">
                        <span class="star" data-rating="1">★</span>
                        <span class="star" data-rating="2">★</span>
                        <span class="star" data-rating="3">★</span>
                        <span class="star" data-rating="4">★</span>
                        <span class="star" data-rating="5">★</span>
                    </div>
                    
                    <textarea class="feedback-textarea" id="feedbackText" placeholder="Optional: Tell me how I can improve my responses..."></textarea>
                    
                    <div style="text-align: center;">
                        <button class="feedback-submit" onclick="submitFeedback()">Submit Feedback</button>
                        <button class="feedback-skip" onclick="closeFeedbackModal()">Skip</button>
                    </div>
                </div>
            </div>
            
            <script>
            let selectedRating = 0;
            let lastInteractionId = null;
            
            document.getElementById('chatForm').addEventListener('submit', function(e) {
                // Show loading spinner
                document.getElementById('loadingContainer').style.display = 'block';
                
                // Disable submit button but NOT the input (so form data gets sent)
                document.getElementById('submitBtn').disabled = true;
                document.getElementById('submitBtn').value = '🤖 Processing...';
                // Don't disable the input field - we need its value to be submitted!
                
                // Scroll to show loading spinner
                document.getElementById('loadingContainer').scrollIntoView({ behavior: 'smooth' });
                
                // Add timeout to re-enable form if request takes too long (30 seconds)
                setTimeout(function() {
                    if (document.getElementById('submitBtn').disabled) {
                        // Re-enable form controls
                        document.getElementById('submitBtn').disabled = false;
                        document.getElementById('submitBtn').value = 'Submit';
                        document.getElementById('loadingContainer').style.display = 'none';
                        
                        // Show timeout message
                        alert('Request timed out. Please try again.');
                        document.getElementById('userInput').focus();
                    }
                }, 30000); // 30 second timeout
            });
            
            // Auto-focus on input field and scroll chat to bottom
            window.addEventListener('load', function() {
                document.getElementById('userInput').focus();
                // Scroll chat box to bottom to show latest messages
                const chatBox = document.querySelector('.chat-box');
                if (chatBox) {
                    chatBox.scrollTop = chatBox.scrollHeight;
                }
            });
            
            // Handle page visibility change (if user switches tabs and comes back)
            document.addEventListener('visibilitychange', function() {
                if (!document.hidden && document.getElementById('submitBtn').disabled) {
                    // If page becomes visible and form is still disabled, re-enable it
                    setTimeout(function() {
                        if (document.getElementById('submitBtn').disabled) {
                            document.getElementById('submitBtn').disabled = false;
                            document.getElementById('submitBtn').value = 'Submit';
                            document.getElementById('loadingContainer').style.display = 'none';
                        }
                    }, 1000);
                }
            });
            
            // Feedback Modal Functions
            function showFeedbackModal() {
                document.getElementById('feedbackModal').style.display = 'block';
            }
            
            function closeFeedbackModal() {
                document.getElementById('feedbackModal').style.display = 'none';
                resetFeedbackForm();
            }
            
            function resetFeedbackForm() {
                selectedRating = 0;
                document.querySelectorAll('.star').forEach(star => {
                    star.classList.remove('selected');
                });
                document.getElementById('feedbackText').value = '';
            }
            
            // Star rating functionality
            document.querySelectorAll('.star').forEach(star => {
                star.addEventListener('click', function() {
                    selectedRating = parseInt(this.getAttribute('data-rating'));
                    updateStarDisplay();
                });
                
                star.addEventListener('mouseover', function() {
                    const rating = parseInt(this.getAttribute('data-rating'));
                    highlightStars(rating);
                });
            });
            
            document.getElementById('ratingStars').addEventListener('mouseleave', function() {
                updateStarDisplay();
            });
            
            function highlightStars(rating) {
                document.querySelectorAll('.star').forEach((star, index) => {
                    if (index < rating) {
                        star.style.color = '#ffd700';
                    } else {
                        star.style.color = '#ddd';
                    }
                });
            }
            
            function updateStarDisplay() {
                document.querySelectorAll('.star').forEach((star, index) => {
                    if (index < selectedRating) {
                        star.classList.add('selected');
                        star.style.color = '#ffd700';
                    } else {
                        star.classList.remove('selected');
                        star.style.color = '#ddd';
                    }
                });
            }
            
            async function submitFeedback() {
                if (selectedRating === 0) {
                    alert('Please select a rating before submitting.');
                    return;
                }
                
                const feedbackText = document.getElementById('feedbackText').value.trim();
                
                try {
                    const response = await fetch('/api/feedback/submit', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            rating: selectedRating,
                            feedback_text: feedbackText,
                            session_id: 'web_session_' + Date.now()
                        })
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        alert('Thank you for your feedback! 🙏');
                        closeFeedbackModal();
                    } else {
                        alert('Failed to submit feedback. Please try again.');
                    }
                } catch (error) {
                    console.error('Error submitting feedback:', error);
                    alert('Error submitting feedback. Please try again.');
                }
            }
            
            // Close modal when clicking outside
            window.onclick = function(event) {
                const modal = document.getElementById('feedbackModal');
                if (event.target === modal) {
                    closeFeedbackModal();
                }
            }
            </script>
        </body>
        </html>
        """, assistant_text=assistant_text, chat_history_html=chat_history_html, 
            should_ask_feedback=should_ask_feedback, feedback_prompt=feedback_prompt)
    
    except Exception as e:
        logger.error(f"Error in index route: {e}")
        return f"Sorry, there was an error processing your request: {e}", 500

# -----------------------
# REST API Endpoints
# -----------------------

@app.route("/api/info", methods=["GET"])
def api_info():
    """Public API information"""
    return jsonify({
        "service": "School Attendance Chatbot API",
        "version": "2.0.0",
        "description": "Simplified hybrid API supporting S3 attendance data and news",
        "capabilities": [
            "Student attendance queries",
            "News headlines", 
            "General knowledge questions"
        ],
        "endpoints": {
            "POST /api/chat": "Main chat endpoint with hybrid intelligence",
            "GET /api/students": "List all students from attendance data",
            "GET /api/news": "Get latest news headlines",
            "PUT /api/attendance": "Update attendance records"
        },
        "authentication": "API key required (Authorization header or api_key parameter)",
        "demo_keys": ["sk-test-12345", "sk-prod-67890", "sk-school-api-key"]
    })

@app.route("/api/chat", methods=["POST"])
@require_api_key
def api_chat():
    """
    Main hybrid chat endpoint - handles both S3 data and external API queries
    """
    start_time = time.time()
    user_message = None
    query_type = None
    response = None
    error_message = None
    
    try:
        data = request.get_json()
        if not data or "message" not in data:
            error_message = "Request must include 'message' field"
            return jsonify({
                "error": error_message,
                "code": "MISSING_MESSAGE"
            }), 400
        
        user_message = data["message"]
        history = data.get("history", [])
        
        # Classify and process with hybrid system
        query_type = classify_query(user_message)
        response = process_hybrid_query(user_message, history)
        
        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Log conversation to S3
        log_conversation_to_s3(
            query=user_message,
            response=response,
            query_type=query_type,
            user=request.api_user["name"],
            api_key=request.headers.get('Authorization', '').replace('Bearer ', ''),
            response_time_ms=response_time_ms,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            error_message=None
        )
        
        return jsonify({
            "response": response,
            "query_type": query_type,
            "user": request.api_user["name"],
            "timestamp": time.time()
        })
    
    except Exception as e:
        error_message = str(e)
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Log error conversation to S3
        log_conversation_to_s3(
            query=user_message or "Unknown",
            response=None,
            query_type=query_type or "error",
            user=request.api_user.get("name", "Unknown") if hasattr(request, 'api_user') else "Unknown",
            api_key=request.headers.get('Authorization', '').replace('Bearer ', ''),
            response_time_ms=response_time_ms,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            error_message=error_message
        )
        
        logger.error(f"API chat error: {e}")
        return jsonify({
            "error": f"Internal server error: {error_message}",
            "code": "INTERNAL_ERROR"
        }), 500

@app.route("/api/students", methods=["GET"])
@require_api_key
def api_students():
    """Get list of all students from S3 attendance data"""
    try:
        all_data = get_cached_s3_data()
        students = []
        seen_names = set()
        
        for record in all_data:
            name = record.get("Unnamed: 2", "").strip()
            grade = record.get("Unnamed: 5", "").strip()
            if name and name not in seen_names:
                students.append({
                    "name": name,
                    "grade": grade,
                    "attendance": record.get("Unnamed: 8", ""),
                    "present": record.get("Unnamed: 17", "")
                })
                seen_names.add(name)
        
        return jsonify({
            "students": students[:50],  # Limit to first 50 for API response
            "total_count": len(students),
            "user": request.api_user["name"],
            "timestamp": time.time()
        })
    
    except Exception as e:
        logger.error(f"API students error: {e}")
        return jsonify({
            "error": f"Error fetching students: {str(e)}",
            "code": "FETCH_ERROR"
        }), 500

@app.route("/api/news", methods=["GET"])
@require_api_key
def api_news():
    """Get latest news headlines"""
    try:
        location = request.args.get("location", "")
        news_data = get_news_data(location)
        
        return jsonify({
            **news_data,
            "user": request.api_user["name"],
            "timestamp": time.time()
        })
    
    except Exception as e:
        logger.error(f"API news error: {e}")
        return jsonify({
            "error": f"News service error: {str(e)}",
            "code": "NEWS_ERROR"
        }), 500

@app.route("/api/attendance", methods=["PUT"])
@require_api_key
def api_update_attendance():
    """Update attendance records (demo endpoint)"""
    try:
        if "write" not in request.api_user["permissions"]:
            return jsonify({
                "error": "Insufficient permissions",
                "code": "PERMISSION_DENIED"
            }), 403
        
        data = request.get_json()
        if not data:
            return jsonify({
                "error": "Request body required",
                "code": "MISSING_DATA"
            }), 400
        
        # This is a demo endpoint - in real implementation, you'd update S3
        return jsonify({
            "message": "Attendance update received (demo mode)",
            "data": data,
            "user": request.api_user["name"],
            "timestamp": time.time(),
            "note": "This is a demo endpoint. Real implementation would update S3 bucket."
        })
    
    except Exception as e:
        logger.error(f"API attendance update error: {e}")
        return jsonify({
            "error": f"Update error: {str(e)}",
            "code": "UPDATE_ERROR"
        }), 500

@app.route("/api/conversations", methods=["GET"])
@require_api_key
def api_conversations():
    """Get conversation logs from S3"""
    try:
        # Get query parameters
        date = request.args.get('date', datetime.now().strftime('%Y/%m/%d'))
        limit = int(request.args.get('limit', 50))
        
        # List objects in S3 for the specified date
        prefix = f"conversations/{date}/"
        
        try:
            response = s3.list_objects_v2(
                Bucket=conversation_bucket,
                Prefix=prefix,
                MaxKeys=limit
            )
        except Exception as e:
            if "NoSuchBucket" in str(e):
                return jsonify({
                    "error": f"Conversation bucket '{conversation_bucket}' does not exist. Please create it first.",
                    "code": "BUCKET_NOT_FOUND",
                    "conversations": [],
                    "count": 0
                }), 404
            raise e
        
        conversations = []
        
        if 'Contents' in response:
            for obj in response['Contents']:
                try:
                    # Get the conversation file
                    file_response = s3.get_object(
                        Bucket=conversation_bucket,
                        Key=obj['Key']
                    )
                    conversation_data = json.loads(file_response['Body'].read().decode('utf-8'))
                    conversations.append(conversation_data)
                except Exception as e:
                    logger.error(f"Error reading conversation file {obj['Key']}: {e}")
                    continue
        
        # Sort by timestamp (newest first)
        conversations.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return jsonify({
            "conversations": conversations,
            "count": len(conversations),
            "date": date,
            "bucket": conversation_bucket,
            "user": request.api_user["name"],
            "timestamp": time.time()
        })
    
    except Exception as e:
        logger.error(f"API conversations error: {e}")
        return jsonify({
            "error": f"Error fetching conversations: {str(e)}",
            "code": "FETCH_ERROR"
        }), 500

@app.route("/api/feedback/submit", methods=["POST"])
def submit_feedback():
    """Submit user feedback"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        rating = data.get('rating')
        feedback_text = data.get('feedback_text', '')
        session_id = data.get('session_id')
        
        if not rating or rating < 1 or rating > 5:
            return jsonify({"success": False, "error": "Valid rating (1-5) required"}), 400
        
        # Get the most recent interaction for this session
        # In a real implementation, you'd track interaction IDs more precisely
        interaction_id = enhanced_feedback.log_interaction(
            user_question="Previous interaction feedback",
            ai_response="Feedback collection",
            query_type="feedback",
            session_id=session_id
        )
        
        # Submit feedback
        feedback_id = enhanced_feedback.collect_feedback(
            interaction_id=interaction_id,
            overall_rating=rating,
            feedback_text=feedback_text,
            user_ip=request.remote_addr
        )
        
        return jsonify({
            "success": True,
            "feedback_id": feedback_id,
            "message": "Thank you for your feedback!"
        })
        
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# -----------------------
# S3 Bucket Creation (Run once)
# -----------------------
def create_conversation_bucket():
    """Create the S3 bucket for storing conversations if it doesn't exist"""
    try:
        s3.head_bucket(Bucket=conversation_bucket)
        print(f"Bucket '{conversation_bucket}' already exists.")
    except:
        try:
            if REGION == 'us-east-1':
                s3.create_bucket(Bucket=conversation_bucket)
            else:
                s3.create_bucket(
                    Bucket=conversation_bucket,
                    CreateBucketConfiguration={'LocationConstraint': REGION}
                )
            print(f"Created bucket '{conversation_bucket}' successfully!")
        except Exception as e:
            print(f"Error creating bucket '{conversation_bucket}': {e}")

# Initialize analytics dashboard
add_analytics_to_app(app, enhanced_feedback)

# Starts the web server when this file is run directly (not imported)
if __name__ == "__main__":
    # Create conversation bucket if it doesn't exist
    create_conversation_bucket()
    
    print("🚀 School Chatbot with Enhanced Feedback System")
    print("📊 Analytics Dashboard: http://localhost:7860/admin/dashboard")
    print("🔗 Main Chat: http://localhost:7860/")
    
    port = int(os.environ.get("PORT", 7860))
    app.run(host="0.0.0.0", port=port, debug=False)