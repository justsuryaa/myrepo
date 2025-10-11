#!/usr/bin/env python3
"""
Test script for the Hybrid School Chatbot API
Tests all endpoints with different query types
"""

import requests
import json
import time

# Configuration
BASE_URL = "http://localhost:7860"  # Change to ALB URL for production testing
API_KEY = "sk-test-12345"

# Headers for authentication
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def test_api_info():
    """Test the API info endpoint (no auth required)"""
    print("🔍 Testing API Info...")
    try:
        response = requests.get(f"{BASE_URL}/api/info", timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Service: {data['service']}")
            print(f"Version: {data['version']}")
            print(f"Capabilities: {len(data['capabilities'])} features")
            print("✅ API Info test passed\n")
        else:
            print(f"❌ API Info test failed: {response.text}\n")
    except Exception as e:
        print(f"❌ API Info test error: {e}\n")

def test_hybrid_chat():
    """Test the hybrid chat endpoint with different query types"""
    print("🤖 Testing Hybrid Chat...")
    
    test_cases = [
        ("What is John's attendance?", "s3_attendance"),
        ("What's the weather in London?", "external_weather"), 
        ("Tell me the latest news", "external_news"),
        ("Give me an inspirational quote", "external_quotes"),
        ("Tell me a random fact", "external_facts"),
        ("What is the capital of France?", "general")
    ]
    
    for message, expected_type in test_cases:
        try:
            print(f"  Query: {message}")
            response = requests.post(
                f"{BASE_URL}/api/chat",
                headers=headers,
                json={"message": message},
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                query_type = data.get("query_type", "unknown")
                response_text = data.get("response", "")[:100] + "..."
                print(f"  Type: {query_type} (expected: {expected_type})")
                print(f"  Response: {response_text}")
                
                if query_type == expected_type:
                    print("  ✅ Correct routing")
                else:
                    print("  ⚠️  Unexpected routing")
            else:
                print(f"  ❌ Error {response.status_code}: {response.text}")
            
            print()
            time.sleep(1)  # Rate limiting
            
        except Exception as e:
            print(f"  ❌ Chat test error: {e}\n")

def test_students_endpoint():
    """Test the students list endpoint"""
    print("👥 Testing Students Endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/students", headers=headers, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            student_count = len(data.get("students", []))
            total_count = data.get("total_count", 0)
            print(f"Students returned: {student_count}")
            print(f"Total count: {total_count}")
            
            if student_count > 0:
                first_student = data["students"][0]
                print(f"Sample student: {first_student.get('name', 'N/A')}")
                print("✅ Students test passed")
            else:
                print("⚠️  No students returned")
        else:
            print(f"❌ Students test failed: {response.text}")
    except Exception as e:
        print(f"❌ Students test error: {e}")
    print()

def test_external_apis():
    """Test individual external API endpoints"""
    print("🌍 Testing External API Endpoints...")
    
    endpoints = [
        ("weather", "/api/weather?city=London"),
        ("news", "/api/news"), 
        ("quote", "/api/quote"),
        ("fact", "/api/fact")
    ]
    
    for name, endpoint in endpoints:
        try:
            print(f"  Testing {name}...")
            response = requests.get(f"{BASE_URL}{endpoint}", headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if name in data or "error" not in data:
                    print(f"  ✅ {name.title()} endpoint working")
                else:
                    print(f"  ⚠️  {name.title()} returned: {data.get('error', 'Unknown')}")
            else:
                print(f"  ❌ {name.title()} failed: {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ {name.title()} error: {e}")
    print()

def test_authentication():
    """Test API authentication"""
    print("🔐 Testing Authentication...")
    
    # Test without API key
    try:
        response = requests.post(f"{BASE_URL}/api/chat", json={"message": "test"}, timeout=5)
        if response.status_code == 401:
            print("✅ Correctly rejected request without API key")
        else:
            print(f"⚠️  Unexpected response without API key: {response.status_code}")
    except Exception as e:
        print(f"❌ Auth test error: {e}")
    
    # Test with invalid API key
    try:
        invalid_headers = {"Authorization": "Bearer invalid-key", "Content-Type": "application/json"}
        response = requests.post(f"{BASE_URL}/api/chat", headers=invalid_headers, json={"message": "test"}, timeout=5)
        if response.status_code == 401:
            print("✅ Correctly rejected invalid API key")
        else:
            print(f"⚠️  Unexpected response with invalid key: {response.status_code}")
    except Exception as e:
        print(f"❌ Invalid key test error: {e}")
    print()

def main():
    """Run all tests"""
    print("🚀 Starting Hybrid School Chatbot API Tests")
    print(f"Testing against: {BASE_URL}")
    print(f"Using API key: {API_KEY}")
    print("="*60)
    
    # Run all tests
    test_api_info()
    test_authentication()
    test_students_endpoint()
    test_external_apis()
    test_hybrid_chat()
    
    print("="*60)
    print("🏁 API Testing Complete!")
    print("\nTo test against production ALB:")
    print("1. Change BASE_URL to: http://schoolchatbot-213277610.us-east-1.elb.amazonaws.com")
    print("2. Run: python test_api.py")

if __name__ == "__main__":
    main()