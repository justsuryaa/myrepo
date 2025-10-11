# 🔑 API Keys Setup Guide

## Quick Start

### 1. Get Your External API Keys

#### Weather API (OpenWeatherMap)
1. Go to https://openweathermap.org/api
2. Click "Sign Up" 
3. Create free account
4. Go to "My API keys"
5. Copy your API key (looks like: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`)

#### News API (NewsAPI.org)
1. Go to https://newsapi.org/
2. Click "Get API Key"
3. Create free account
4. Copy your API key (looks like: `1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p`)

### 2. Add Keys to Your App

Open `app.py` and replace the placeholder text:

```python
# Find these lines around line 56-63:
"api_key": os.environ.get("OPENWEATHER_API_KEY", "YOUR_OPENWEATHER_API_KEY_HERE"),
"api_key": os.environ.get("NEWS_API_KEY", "YOUR_NEWS_API_KEY_HERE"),

# Replace with your actual keys:
"api_key": os.environ.get("OPENWEATHER_API_KEY", "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"),
"api_key": os.environ.get("NEWS_API_KEY", "1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p"),
```

### 3. Test Your Setup

Run the test script:
```bash
python3 test_api_keys.py
```

### 4. Use Your API

#### Your App's API Keys (for accessing the chatbot):
- `sk-school-api-key` - Use this in your requests
- `sk-test-12345` - For testing
- `sk-prod-67890` - For admin access

#### Example API Call:
```bash
curl -X POST http://localhost:7860/api/chat \
  -H "Authorization: Bearer sk-school-api-key" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the weather in London?"}'
```

## What Each API Does

### Internal APIs (Your School Data)
- **Student Attendance:** "What is John's attendance?"
- **Student Lists:** "Show me all students"
- **Attendance Updates:** "Mark John present today"

### External APIs (World Data)
- **Weather:** "What's the weather in Tokyo?"
- **News:** "Show me latest news"
- **Facts:** "Tell me a random fact"
- **Quotes:** "Give me an inspiring quote"

## Troubleshooting

### API Key Not Working?
1. Check if you copied the full key
2. Make sure there are no extra spaces
3. Verify the key is active on the provider's website

### "demo_key" in responses?
- You haven't added your real API key yet
- Replace "YOUR_API_KEY_HERE" with your actual key

### 401 Unauthorized?
- Check your Authorization header
- Use: `Authorization: Bearer sk-school-api-key`

## Security Notes

- Never commit real API keys to Git
- Use environment variables for production
- Each API key has usage limits (check provider docs)
- Weather API: 1000 calls/day (free)
- News API: 100 calls/day (free)

## Ready to Deploy?

Once you have your API keys:
1. Update the keys in app.py
2. Push to GitHub: `git add . && git commit -m "Add API keys" && git push`
3. SSH to EC2 and pull updates
4. Restart the app

Your hybrid chatbot will then answer both school questions AND general questions! 🎉