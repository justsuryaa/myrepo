import os
import json
import boto3
import botocore
import gradio as gr

REGION = "us-east-1"
bucket_name = os.environ.get("BUCKET_NAME", "suryaatrial3")

# Paste your inference profile ARN from Bedrock Playground > View API request (Python)
# Example from your earlier CLI: arn:aws:bedrock:us-east-1:705241975254:inference-profile/us.anthropic.claude-3-5-haiku-20241022-v1:0
INFERENCE_PROFILE_ARN = os.environ.get(
    "BEDROCK_INFERENCE_PROFILE_ARN",
    "arn:aws:bedrock:us-east-1:705241975254:inference-profile/us.anthropic.claude-3-5-haiku-20241022-v1:0"
)
# Clients
s3 = boto3.client("s3", region_name=REGION)
bedrock = boto3.client(
    "bedrock-runtime",
    region_name=REGION,
    config=botocore.config.Config(connect_timeout=10, read_timeout=120),
)

# Chat history will be managed per session in Gradio

def list_json_files(bucket):
    paginator = s3.get_paginator("list_objects_v2")
    json_files = []
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            if obj["Key"].lower().endswith(".json"):
                json_files.append(obj["Key"])
    return json_files

# Load and combine all JSON datasets in the bucket (once at startup)
json_files = list_json_files(bucket_name)
all_data = []
if not json_files:
    s3_data_str = "(No JSON datasets found in bucket)"
else:
    for object_key in json_files:
        try:
            resp = s3.get_object(Bucket=bucket_name, Key=object_key)
            data = json.loads(resp["Body"].read().decode("utf-8"))
            if isinstance(data, list):
                all_data.extend(data)
            else:
                all_data.append(data)
            print(f"Loaded JSON from bucket '{bucket_name}', file '{object_key}'")
        except Exception as e:
            print(f"Could not load S3 data from {object_key}: {e}")
    s3_data_str = json.dumps(all_data)

def query_bedrock(user_prompt: str, history: list) -> tuple:
    # Sample up to 20 records to control prompt size and improve speed
    try:
        sample = all_data[:20] if isinstance(all_data, list) else all_data
        sample_str = json.dumps(sample)
    except Exception:
        sample_str = s3_data_str[:2000]

    # Build messages from history
    messages = []
    for user, assistant in history:
        messages.append({"role": "user", "content": [{"text": user}]})
        messages.append({"role": "assistant", "content": [{"text": assistant}]})

    # Detect if the question is about attendance or students
    keywords = ["attendance", "student", "school", "absent", "present", "class", "roll", "register"]
    if any(word in user_prompt.lower() for word in keywords):
        # Add S3 data to prompt
        user_text = (
            f"{user_prompt}\n\nHere is a sample of the combined S3 data:\n{sample_str}\n"
            "Please analyze and answer clearly. If the sample is insufficient, say so."
        )
    else:
        # Generic question, no S3 data
        user_text = user_prompt

    messages.append({"role": "user", "content": [{"text": user_text}]})

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



with gr.Blocks(theme=gr.themes.Base(), css="body {background: #1565c0;} .gradio-container {background: #1565c0;} .white-bg {background: #fff; border-radius: 10px; padding: 20px;} .black-btn {color: #000 !important;}") as demo:
    gr.Markdown("<h1 style='color:white;text-align:center;'>THE OASIS PUBLIC SCHOOL</h1>")
    gr.Markdown("<h2 style='color:white;text-align:center;'>STUDENT'S ATTENDANCE DETAILS</h2>")
    with gr.Row():
        with gr.Column():
            chatbot = gr.Chatbot(label="Chat History", elem_classes=["white-bg"])
            input_box = gr.Textbox(lines=5, label="Ask about the S3 data", placeholder="e.g. What are the ways to improve attendance?", elem_classes=["white-bg"])
            submit_btn = gr.Button("Submit", elem_classes=["white-bg", "black-btn"])
    gr.Markdown("<div style='color:white;text-align:center;'>Asks Anthropic Claude via Amazon Bedrock using a sample of JSON data from your S3 bucket.<br>Sample prompt: What are the ways to improve attendance?</div>")

    def chat(user_input, history=[]):
        # Prevent sending empty input to Bedrock
        if not user_input or not user_input.strip():
            return history, ""
        history = history or []
        history = [tuple(pair) for pair in history]
        updated_history, assistant_text = query_bedrock(user_input, history)
        return updated_history, ""

    submit_btn.click(chat, inputs=[input_box, chatbot], outputs=[chatbot, input_box])


if __name__ == "__main__":
    demo.launch(show_error=True)

