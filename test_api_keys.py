#!/usr/bin/env python3
"""
API Testing Script for School Chatbot
Shows how to use API keys and test different endpoints
"""

import requests
import json

# Your app's API endpoint
BASE_URL = "http://localhost:7860"  # For local testing
# BASE_URL = "http://schoolchatbot-213277610.us-east-1.elb.amazonaws.com"  # For production

# Your app's API key (use any from the configured keys)
API_KEY = "sk-school-api-key"

# Headers for authentication
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def test_health():
    """Test if the API is running"""
    print("🏥 Testing Health Endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

def test_students():
    """Test getting student list"""
    print("👥 Testing Students Endpoint...")
    response = requests.get(f"{BASE_URL}/api/students", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Found {len(data.get('students', []))} students")
    else:
        print(f"Error: {response.text}")
    print()

def test_s3_question():
    """Test asking a question about attendance data"""
    print("📊 Testing S3 Data Question...")
    question_data = {
        "message": "What is John's attendance percentage?"
    }
    response = requests.post(f"{BASE_URL}/api/chat", headers=headers, json=question_data)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {data.get('response', 'No response')}")
    else:
        print(f"Error: {response.text}")
    print()

def test_weather_question():
    """Test asking a weather question (external API)"""
    print("🌤️ Testing Weather Question...")
    question_data = {
        "message": "What's the weather like in New York?"
    }
    response = requests.post(f"{BASE_URL}/api/chat", headers=headers, json=question_data)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {data.get('response', 'No response')}")
    else:
        print(f"Error: {response.text}")
    print()

def test_general_question():
    """Test asking a general question"""
    print("🤔 Testing General Question...")
    question_data = {
        "message": "Tell me a random fact"
    }
    response = requests.post(f"{BASE_URL}/api/chat", headers=headers, json=question_data)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {data.get('response', 'No response')}")
    else:
        print(f"Error: {response.text}")
    print()

if __name__ == "__main__":
    print("🚀 School Chatbot API Test Suite")
    print("=" * 50)
    
    # Test basic functionality
    test_health()
    
    # Test API endpoints (requires API key)
    test_students()
    test_s3_question()
    test_weather_question()
    test_general_question()
    
    print("✅ Testing Complete!")
    print("\n📝 Instructions:")
    print("1. Get API keys from:")
    print("   - Weather: https://openweathermap.org/api")
    print("   - News: https://newsapi.org/")
    print("2. Replace 'YOUR_API_KEY_HERE' in app.py with your actual keys")
    print("3. Run the app: python3 app.py")
    print("4. Test with this script: python3 test_api_keys.py")