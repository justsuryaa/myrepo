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

def query_bedrock(user_prompt: str) -> str:
    # Sample up to 100 records to control prompt size
    try:
        sample = all_data[:100] if isinstance(all_data, list) else all_data
        sample_str = json.dumps(sample)
    except Exception:
        sample_str = s3_data_str[:2000]

    user_text = (
        f"{user_prompt}\n\nHere is a sample of the combined S3 data:\n{sample_str}\n"
        "Please analyze and answer clearly. If the sample is insufficient, say so."
    )

    # Converse API with inference profile
    messages = [
        {"role": "user", "content": [{"text": user_text}]}
    ]

    try:
        resp = bedrock.converse(
            modelId=INFERENCE_PROFILE_ARN,  # inference profile ARN or ID (e.g., us.anthropic.claude-3-5-haiku-20241022-v1:0)
            messages=messages,
            inferenceConfig={"maxTokens": 256, "temperature": 0.3, "topP": 0.9},
        )
        out = resp.get("output", {}).get("message", {}).get("content", [])
        assistant_text = "".join(part.get("text", "") for part in out if "text" in part)
        return assistant_text or "(No text returned by model)"
    except Exception as e:
        return f"Error: {e}"

iface = gr.Interface(
    fn=query_bedrock,
    inputs=gr.Textbox(lines=5, label="Ask about the S3 data"),
    outputs=gr.Textbox(lines=15, label="output"),
    title="Bedrock LLM Chat with S3 Data",
    description="Asks Anthropic Claude via Amazon Bedrock using a sample of JSON data from your S3 bucket.",
)

if __name__ == "__main__":
    iface.launch(show_error=True)

