import os
import json
import boto3
import botocore
import time
import logging
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
    config=botocore.config.Config(connect_timeout=10, read_timeout=120),
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
                    print("Loading S3 data...")
                    all_data = get_cached_s3_data()
                    print(f"Loaded {len(all_data) if all_data else 0} records")
                    
                    print("Calling Bedrock...")
                    assistant_text = query_bedrock(user_input, session["history"], all_data)
                    print(f"Bedrock response: {assistant_text[:100]}...")
                    
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
                <h2>THE OASIS PUBLIC SCHOOL - STUDENT'S ATTENDANCE DETAILS (Auto-Deploy Test)</h2>
                <form method="post" id="chatForm">
                    <div class="sample-prompt">Sample prompt: What are the ways to improve attendance?</div>
                    <input name="user_input" type="text" placeholder="e.g. What are the ways to improve attendance?" required id="userInput">
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

# Starts the web server when this file is run directly (not imported)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    app.run(host="0.0.0.0", port=port, debug=False)