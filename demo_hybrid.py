#!/usr/bin/env python3
"""
Simplified test script to demonstrate hybrid query classification
Tests the query routing logic without requiring AWS or external API calls
"""

import re

def classify_query(user_query):
    """
    Determines whether the query is about:
    - S3 attendance data (internal)
    - External API call (weather, news, etc.)
    - General knowledge (use Bedrock only)
    """
    query_lower = user_query.lower()
    
    # S3 attendance keywords
    attendance_keywords = [
        "attendance", "student", "school", "absent", "present", "class", 
        "roll", "register", "grade", "students", "names", "list",
        "who is", "john", "sarah", "alex", "attendance rate", "missing"
    ]
    
    # External API keywords
    weather_keywords = ["weather", "temperature", "rain", "sunny", "cloudy", "forecast", "climate"]
    news_keywords = ["news", "headlines", "current events", "today's news", "breaking news"]
    quote_keywords = ["quote", "inspiration", "motivational", "wisdom", "saying"]
    fact_keywords = ["fact", "random fact", "interesting", "did you know", "trivia"]
    
    # Check for S3 attendance queries
    if any(keyword in query_lower for keyword in attendance_keywords):
        return "s3_attendance"
    
    # Check for external API queries
    if any(keyword in query_lower for keyword in weather_keywords):
        return "external_weather"
    elif any(keyword in query_lower for keyword in news_keywords):
        return "external_news"
    elif any(keyword in query_lower for keyword in quote_keywords):
        return "external_quotes"
    elif any(keyword in query_lower for keyword in fact_keywords):
        return "external_facts"
    
    # Default to general knowledge (Bedrock only)
    return "general"

def demo_hybrid_responses():
    """Demo the different response types"""
    test_queries = [
        "What is John's attendance rate this month?",
        "List all students in grade 10",
        "Who was absent yesterday?",
        "What's the weather in London today?", 
        "Is it going to rain tomorrow?",
        "Tell me the latest news headlines",
        "What's happening in the world?",
        "Give me an inspirational quote",
        "Share some motivational wisdom",
        "Tell me a random fact",
        "Did you know any interesting trivia?",
        "What is the capital of France?",
        "How do I solve quadratic equations?",
        "Tell me a joke"
    ]
    
    print("🤖 Hybrid Query Classification Demo")
    print("="*60)
    
    for query in test_queries:
        query_type = classify_query(query)
        
        # Simulate different response types
        if query_type == "s3_attendance":
            response = "📊 [S3 DATA] Student attendance information from school database..."
        elif query_type == "external_weather":
            response = "🌤️ [WEATHER API] Current weather conditions and forecast..."
        elif query_type == "external_news":
            response = "📰 [NEWS API] Latest headlines and current events..."
        elif query_type == "external_quotes":
            response = "💭 [QUOTES API] Inspirational quote from famous personalities..."
        elif query_type == "external_facts":
            response = "🔍 [FACTS API] Interesting random fact or trivia..."
        else:
            response = "🧠 [BEDROCK AI] General knowledge response from AI model..."
        
        print(f"Query: {query}")
        print(f"Type:  {query_type}")
        print(f"Response: {response}")
        print("-" * 60)

def test_api_endpoints():
    """Demo API endpoint structure"""
    print("\n🚀 API Endpoints Available:")
    print("="*60)
    
    endpoints = [
        ("GET /api/info", "Public API information", "No auth required"),
        ("POST /api/chat", "Hybrid chat with intelligent routing", "API key required"),
        ("GET /api/students", "List all students from S3 data", "API key required"),
        ("GET /api/weather?city=London", "Weather information", "API key required"),
        ("GET /api/news", "Latest news headlines", "API key required"),
        ("GET /api/quote", "Inspirational quote", "API key required"),
        ("GET /api/fact", "Random interesting fact", "API key required"),
        ("PUT /api/attendance", "Update attendance records", "API key + write permission")
    ]
    
    for endpoint, description, auth in endpoints:
        print(f"Endpoint: {endpoint}")
        print(f"Purpose:  {description}")
        print(f"Auth:     {auth}")
        print("-" * 60)

def show_usage_examples():
    """Show usage examples"""
    print("\n💡 Usage Examples:")
    print("="*60)
    
    examples = [
        {
            "type": "S3 Attendance Queries",
            "examples": [
                "What is John's attendance this month?",
                "List all students in grade 10",
                "Who has the highest attendance rate?",
                "Show me absent students yesterday"
            ]
        },
        {
            "type": "Weather Queries", 
            "examples": [
                "What's the weather in London?",
                "Is it raining in New York?",
                "What's the temperature today?",
                "Weather forecast for tomorrow"
            ]
        },
        {
            "type": "News Queries",
            "examples": [
                "What's in the news today?",
                "Latest headlines",
                "Breaking news updates",
                "Current events summary"
            ]
        },
        {
            "type": "Quote Queries",
            "examples": [
                "Give me an inspirational quote",
                "Share some wisdom",
                "Motivational saying for students",
                "Quote about education"
            ]
        },
        {
            "type": "Fact Queries",
            "examples": [
                "Tell me a random fact",
                "Interesting trivia",
                "Did you know something cool?",
                "Fun fact about science"
            ]
        },
        {
            "type": "General Knowledge",
            "examples": [
                "What is the capital of France?",
                "How do photosynthesis work?",
                "Explain quantum physics",
                "Tell me a joke"
            ]
        }
    ]
    
    for category in examples:
        print(f"\n{category['type']}:")
        for example in category['examples']:
            query_type = classify_query(example)
            print(f"  • \"{example}\" → {query_type}")

if __name__ == "__main__":
    print("🎓 Smart School Assistant - Hybrid API Demo")
    print("This demonstrates the intelligent query routing system")
    print("that determines whether to use S3 data, external APIs, or general AI\n")
    
    demo_hybrid_responses()
    test_api_endpoints()
    show_usage_examples()
    
    print("\n" + "="*60)
    print("🏁 Demo Complete!")
    print("\nKey Features:")
    print("✅ Intelligent query classification")
    print("✅ Multiple data source routing") 
    print("✅ REST API with authentication")
    print("✅ External API integration ready")
    print("✅ Backward compatible with existing S3 functionality")
    print("\nTo test live: Deploy to EC2 and test with curl or Python requests")