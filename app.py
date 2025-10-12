import os
import json
import boto3
import botocore
import time
import logging
import requests
import re
from functools import wraps
from flask import Flask, request, render_template_string, session, jsonify
from flask_cors import CORS

REGION = "us-east-1"
bucket_name = os.environ.get("BUCKET_NAME", "suryaatrial3")

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

# Production configurations
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

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
def get_news_data():
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
        
        url = f"{EXTERNAL_APIS['news']['base_url']}?country=us&apiKey={api_key}&pageSize=5"
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
    query_type = classify_query(user_query)
    logger.info(f"Query classified as: {query_type}")
    
    try:
        if query_type == "s3_attendance":
            # Use S3 data + Bedrock
            all_data = get_cached_s3_data()
            return query_bedrock(user_query, history or [], all_data)
        
        elif query_type == "external_news":
            # Get news data
            news_data = get_news_data()
            if "error" in news_data:
                return f"Sorry, I couldn't get news information: {news_data['error']}"
            
            if "note" in news_data:
                response = "📰 Latest News Headlines:\n\n"
                for article in news_data["news"]:
                    response += f"• {article['title']} - {article['source']}\n"
                response += f"\nNote: {news_data['note']}"
                return response
            else:
                response = "📰 Latest News Headlines:\n\n"
                for article in news_data["news"]:
                    response += f"• {article['title']} - {article['source']}\n"
                    if article.get('description'):
                        response += f"  {article['description']}\n"
                return response
        
        else:  # general queries
            # Use Bedrock for general knowledge
            return query_bedrock(user_query, history or [], [])
    
    except Exception as e:
        logger.error(f"Error in process_hybrid_query: {e}")
        return f"Sorry, I encountered an error processing your request: {str(e)}"

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
            @media (max-width: 600px) {
                .container { margin: 10px; padding: 15px; }
                h2 { font-size: 1.1em; }
                .chat-box { height: 250px; }
                input[type="text"], input[type="submit"] { font-size: 16px; } /* Prevents zoom on iOS */
            }
            </style>
        </head>
        <body>
            <div class="container">
                <h2>🎓 SMART SCHOOL ASSISTANT - Attendance • Weather • News • More!</h2>
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
            
            <script>
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
            </script>
        </body>
        </html>
        """, assistant_text=assistant_text, chat_history_html=chat_history_html)
    
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
    try:
        data = request.get_json()
        if not data or "message" not in data:
            return jsonify({
                "error": "Request must include 'message' field",
                "code": "MISSING_MESSAGE"
            }), 400
        
        user_message = data["message"]
        history = data.get("history", [])
        
        # Process with hybrid system
        response = process_hybrid_query(user_message, history)
        
        return jsonify({
            "response": response,
            "query_type": classify_query(user_message),
            "user": request.api_user["name"],
            "timestamp": time.time()
        })
    
    except Exception as e:
        logger.error(f"API chat error: {e}")
        return jsonify({
            "error": f"Internal server error: {str(e)}",
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
        news_data = get_news_data()
        
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

# Starts the web server when this file is run directly (not imported)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    app.run(host="0.0.0.0", port=port, debug=False)