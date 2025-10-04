import os
import json
import boto3
import botocore
import time
from flask import Flask, request, render_template_string, session

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
app.secret_key = "your_secret_key"  # Needed for session-based chat history

def list_json_files(bucket):
    paginator = s3.get_paginator("list_objects_v2")
    json_files = []
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            if obj["Key"].lower().endswith(".json"):
                json_files.append(obj["Key"])
    return json_files

def load_s3_data():
    json_files = list_json_files(bucket_name)
    all_data = []
    if not json_files:
        return []
    for object_key in json_files:
        try:
            resp = s3.get_object(Bucket=bucket_name, Key=object_key)
            data = json.loads(resp["Body"].read().decode("utf-8"))
            if isinstance(data, list):
                all_data.extend(data)
            else:
                all_data.append(data)
        except Exception as e:
            print(f"Could not load S3 data from {object_key}: {e}")
    return all_data

CACHE_TTL = 600  # seconds (10 minutes)
_cached_data = None
_last_cache_time = 0

def get_cached_s3_data():
    global _cached_data, _last_cache_time
    now = time.time()
    if _cached_data is None or (now - _last_cache_time) > CACHE_TTL:
        _cached_data = load_s3_data()
        _last_cache_time = now
    return _cached_data

def query_bedrock(user_prompt: str, history: list, all_data) -> str:
    import re
    match = re.search(r"\b([A-Z][a-z]+)\b", user_prompt)
    student_name = match.group(1) if match else None

    SAMPLE_SIZE = 50

    if student_name:
        filtered = [record for record in all_data if student_name.lower() in json.dumps(record).lower()]
        sample = filtered[:SAMPLE_SIZE] if filtered else all_data[:SAMPLE_SIZE]
    else:
        sample = all_data[:SAMPLE_SIZE] if isinstance(all_data, list) else all_data

    sample_str = json.dumps(sample)

    keywords = ["attendance", "student", "school", "absent", "present", "class", "roll", "register"]
    if any(word in user_prompt.lower() for word in keywords):
        user_text = (
            f"{user_prompt}\n\nHere is a sample of the combined S3 data:\n{sample_str}\n"
            "Please analyze and answer clearly. If the sample is insufficient, say so."
        )
    else:
        user_text = user_prompt

    messages = []
    # Only add previous messages if their content is a string
    for msg in history:
        if isinstance(msg, dict) and isinstance(msg.get("content", ""), str):
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": user_text})

    try:
        resp = bedrock.converse(
            modelId=INFERENCE_PROFILE_ARN,
            messages=messages,
            inferenceConfig={"maxTokens": 256, "temperature": 0.3, "topP": 0.9},
        )
        out = resp.get("output", {}).get("message", {}).get("content", [])
        assistant_text = "".join(part.get("text", "") for part in out if "text" in part)
        return assistant_text or "(No text returned by model)"
    except Exception as e:
        return f"Error: {e}"

@app.route("/", methods=["GET", "POST"])
def index():
    if "history" not in session:
        session["history"] = []
    assistant_text = ""
    if request.method == "POST":
        user_input = request.form["user_input"]
        all_data = get_cached_s3_data()
        assistant_text = query_bedrock(user_input, session["history"], all_data)
        session["history"].append({"role": "user", "content": user_input})
        session["history"].append({"role": "assistant", "content": assistant_text})
    chat_history_html = ""
    for msg in session.get("history", []):
        if msg["role"] == "user":
            chat_history_html += f'<div><b>You:</b> {msg["content"]}</div>'
        else:
            chat_history_html += f'<div><b>AI:</b> {msg["content"]}</div>'
    return render_template_string("""
        <style>
        body { background: #1565c0; color: #fff; font-family: Arial, sans-serif; }
        .container { background: #fff; color: #1565c0; border-radius: 10px; padding: 30px; max-width: 700px; margin: 40px auto; }
        input[type="text"] { width: 80%; padding: 10px; border-radius: 5px; border: 1px solid #1565c0; }
        input[type="submit"] { background: #1565c0; color: #fff; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
        .chat-history { background: #e3f2fd; color: #1565c0; border-radius: 8px; padding: 15px; margin-bottom: 20px; }
        h2 { text-align: center; color: #1565c0; }
        .sample-prompt { color: #1565c0; font-size: 0.95em; margin-bottom: 10px; }
        </style>
        <div class="container">
            <h2>THE OASIS PUBLIC SCHOOL - STUDENT'S ATTENDANCE DETAILS</h2>
            <form method="post">
                <div class="sample-prompt">Sample prompt: What are the ways to improve attendance?</div>
                <input name="user_input" type="text" placeholder="e.g. What are the ways to improve attendance? or What is the weather today?">
                <input type="submit" value="Submit">
            </form>
            <div class="chat-history">{{chat_history_html|safe}}</div>
        </div>
    """, assistant_text=assistant_text, chat_history_html=chat_history_html)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860)