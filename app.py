import os
import json
import boto3
import botocore
import gradio as gr
import time

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

# --- Caching logic ---
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

def query_bedrock(user_prompt: str, history: list, all_data) -> tuple:
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

    messages = []
    for user, assistant in history:
        if user:
            messages.append({"role": "user", "content": user})
        if assistant:
            messages.append({"role": "assistant", "content": assistant})

    keywords = ["attendance", "student", "school", "absent", "present", "class", "roll", "register"]
    if any(word in user_prompt.lower() for word in keywords):
        user_text = (
            f"{user_prompt}\n\nHere is a sample of the combined S3 data:\n{sample_str}\n"
            "Please analyze and answer clearly. If the sample is insufficient, say so."
        )
    else:
        user_text = user_prompt

    messages.append({"role": "user", "content": user_text})

    try:
        resp = bedrock.converse(
            modelId=INFERENCE_PROFILE_ARN,
            messages=messages,
            inferenceConfig={"maxTokens": 256, "temperature": 0.3, "topP": 0.9},
        )
        out = resp.get("output", {}).get("message", {}).get("content", [])
        assistant_text = "".join(part.get("text", "") for part in out if "text" in part)
        history.append((user_prompt, assistant_text or "(No text returned by model)"))
        return history, assistant_text or "(No text returned by model)"
    except Exception as e:
        history.append((user_prompt, f"Error: {e}"))
        return history, f"Error: {e}"

# ...existing imports and setup...

# ...existing code...

with gr.Blocks(theme=gr.themes.Base(), css="body {background: #1565c0;} .gradio-container {background: #1565c0;} .white-bg {background: #fff; border-radius: 10px; padding: 20px;} .black-btn {color: #000 !important;}") as demo:
    gr.Markdown("<h1 style='color:white;text-align:center;'>THE OASIS PUBLIC SCHOOL</h1>")
    gr.Markdown("<h2 style='color:white;text-align:center;'>STUDENT'S ATTENDANCE DETAILS</h2>")
    with gr.Row():
        with gr.Column():
            chatbot = gr.Chatbot(label="Chat History", value=[], elem_classes=["white-bg"])
            input_box = gr.Textbox(lines=5, label="Ask about the S3 data", placeholder="e.g. What are the ways to improve attendance?", elem_classes=["white-bg"])
            submit_btn = gr.Button("Submit", elem_classes=["white-bg", "black-btn"])
    gr.Markdown("<div style='color:white;text-align:center;'>Asks Anthropic Claude via Amazon Bedrock using a sample of JSON data from your S3 bucket.<br>Sample prompt: What are the ways to improve attendance?</div>")

    def chat(user_input, history=None):
        if history is None:
            history = []
        # Use cached S3 data
        all_data = get_cached_s3_data()
        updated_history, assistant_text = query_bedrock(user_input, history, all_data)
        return updated_history, ""

    submit_btn.click(chat, inputs=[input_box, chatbot], outputs=[chatbot, input_box])

if __name__ == "__main__":
    demo.launch(show_error=True, share=True)