#!/usr/bin/env python3
"""
Simple test to validate the News API key
"""

import requests

def test_news_api():
    """Test the News API directly"""
    api_key = "e5d7c39b653d47e585dc1232323e7d06"
    url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={api_key}&pageSize=3"
    
    print("🧪 Testing News API Key...")
    print(f"URL: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            articles = data.get('articles', [])
            print(f"✅ Success! Found {len(articles)} articles")
            
            if articles:
                print("\n📰 Sample Headlines:")
                for i, article in enumerate(articles[:3], 1):
                    print(f"{i}. {article['title']}")
                    print(f"   Source: {article['source']['name']}")
                print()
            
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def test_weather_api():
    """Test if we can get weather data (using a free service)"""
    print("🌤️ Testing Weather Service...")
    
    # Using a free weather service that doesn't require API key
    url = "https://api.open-meteo.com/v1/forecast?latitude=40.7589&longitude=-73.9851&current_weather=true"
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            current = data.get('current_weather', {})
            temp = current.get('temperature', 'N/A')
            print(f"✅ Weather API working! Temperature: {temp}°C")
            return True
        else:
            print(f"❌ Weather API Error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Weather API Exception: {e}")
        return False

if __name__ == "__main__":
    print("🔑 API Key Validation Test")
    print("=" * 50)
    
    news_works = test_news_api()
    weather_works = test_weather_api()
    
    print("=" * 50)
    print("📊 Results:")
    print(f"News API: {'✅ Working' if news_works else '❌ Not Working'}")
    print(f"Weather API: {'✅ Working' if weather_works else '❌ Not Working'}")
    
    if news_works:
        print("\n🎉 Great! Your News API key is working!")
        print("📝 Next steps:")
        print("1. Add a Weather API key from https://openweathermap.org/api")
        print("2. Deploy to your EC2 server")
        print("3. Test the full hybrid chatbot functionality")
    else:
        print("\n⚠️ Please check your News API key")
        print("Make sure you got it from https://newsapi.org/")