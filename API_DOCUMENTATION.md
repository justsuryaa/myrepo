# School Attendance Chatbot API Documentation v2.0

## Overview
This hybrid API combines S3 attendance data with external APIs to provide comprehensive responses to various queries including student attendance, weather, news, quotes, and general knowledge questions.

## Base URL
- **Production**: `http://schoolchatbot-213277610.us-east-1.elb.amazonaws.com`
- **Local**: `http://localhost:7860`

## Authentication
All API endpoints require authentication using API keys.

### Methods:
1. **Header**: `Authorization: Bearer your-api-key`
2. **Query Parameter**: `?api_key=your-api-key`

### Demo API Keys:
- `sk-test-12345` - Test User (read, write permissions)
- `sk-prod-67890` - Admin User (read, write, delete permissions)
- `sk-school-api-key` - School Admin (read, write permissions)

## Endpoints

### 1. API Information
```http
GET /api/info
```
**Description**: Get API service information and capabilities  
**Authentication**: None required  
**Response**:
```json
{
  "service": "School Attendance Chatbot API",
  "version": "2.0.0",
  "capabilities": [
    "Student attendance queries",
    "Weather information",
    "News headlines",
    "Inspirational quotes",
    "Random facts",
    "General knowledge questions"
  ]
}
```

### 2. Hybrid Chat (Main Endpoint)
```http
POST /api/chat
```
**Description**: Main intelligent chat endpoint that routes queries to appropriate data sources  
**Authentication**: Required  
**Request Body**:
```json
{
  "message": "What is John's attendance?",
  "history": [
    {"role": "user", "content": "Previous message"},
    {"role": "assistant", "content": "Previous response"}
  ]
}
```
**Response**:
```json
{
  "response": "John has been present for 85% of classes this month...",
  "query_type": "s3_attendance",
  "user": "Test User",
  "timestamp": 1703123456.789
}
```

**Query Types Supported**:
- `s3_attendance` - Student attendance data from S3
- `external_weather` - Weather information
- `external_news` - News headlines
- `external_quotes` - Inspirational quotes
- `external_facts` - Random facts
- `general` - General knowledge (Bedrock AI)

### 3. Students List
```http
GET /api/students
```
**Description**: Get list of all students from attendance data  
**Authentication**: Required  
**Response**:
```json
{
  "students": [
    {
      "name": "John Smith",
      "grade": "10th",
      "attendance": "85%",
      "present": "Yes"
    }
  ],
  "total_count": 150,
  "user": "Test User",
  "timestamp": 1703123456.789
}
```

### 4. Weather Information
```http
GET /api/weather?city=London
```
**Description**: Get weather information for specified city  
**Authentication**: Required  
**Parameters**:
- `city` (optional): City name (default: London)

**Response**:
```json
{
  "weather": {
    "city": "London",
    "temperature": "22°C",
    "description": "Partly Cloudy",
    "humidity": "65%",
    "feels_like": "24°C"
  },
  "user": "Test User",
  "timestamp": 1703123456.789
}
```

### 5. News Headlines
```http
GET /api/news
```
**Description**: Get latest news headlines  
**Authentication**: Required  
**Response**:
```json
{
  "news": [
    {
      "title": "Technology Advances in Education",
      "source": "News Source",
      "description": "Latest developments in educational technology..."
    }
  ],
  "user": "Test User",
  "timestamp": 1703123456.789
}
```

### 6. Inspirational Quote
```http
GET /api/quote
```
**Description**: Get random inspirational quote  
**Authentication**: Required  
**Response**:
```json
{
  "quote": {
    "text": "Education is the most powerful weapon which you can use to change the world.",
    "author": "Nelson Mandela",
    "tags": ["education", "inspiration"]
  },
  "user": "Test User",
  "timestamp": 1703123456.789
}
```

### 7. Random Fact
```http
GET /api/fact
```
**Description**: Get random interesting fact  
**Authentication**: Required  
**Response**:
```json
{
  "fact": {
    "text": "The human brain contains approximately 86 billion neurons.",
    "source": "Scientific Studies"
  },
  "user": "Test User",
  "timestamp": 1703123456.789
}
```

### 8. Update Attendance
```http
PUT /api/attendance
```
**Description**: Update attendance records (demo endpoint)  
**Authentication**: Required (write permission)  
**Request Body**:
```json
{
  "student_name": "John Smith",
  "date": "2024-01-15",
  "status": "present"
}
```
**Response**:
```json
{
  "message": "Attendance update received (demo mode)",
  "data": {
    "student_name": "John Smith",
    "date": "2024-01-15",
    "status": "present"
  },
  "user": "Test User",
  "timestamp": 1703123456.789,
  "note": "This is a demo endpoint."
}
```

## Error Responses

### 401 Unauthorized
```json
{
  "error": "API key is required",
  "code": "MISSING_API_KEY"
}
```

### 403 Forbidden
```json
{
  "error": "Insufficient permissions",
  "code": "PERMISSION_DENIED"
}
```

### 400 Bad Request
```json
{
  "error": "Request must include 'message' field",
  "code": "MISSING_MESSAGE"
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal server error: detailed message",
  "code": "INTERNAL_ERROR"
}
```

## Example Usage

### cURL Examples

#### 1. Chat with S3 Data Query
```bash
curl -X POST "http://schoolchatbot-213277610.us-east-1.elb.amazonaws.com/api/chat" \
  -H "Authorization: Bearer sk-test-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is John'\''s attendance rate?"
  }'
```

#### 2. Get Weather
```bash
curl "http://schoolchatbot-213277610.us-east-1.elb.amazonaws.com/api/weather?city=New York" \
  -H "Authorization: Bearer sk-test-12345"
```

#### 3. Get Students List
```bash
curl "http://schoolchatbot-213277610.us-east-1.elb.amazonaws.com/api/students" \
  -H "Authorization: Bearer sk-test-12345"
```

### Python Example
```python
import requests

# Configuration
BASE_URL = "http://schoolchatbot-213277610.us-east-1.elb.amazonaws.com"
API_KEY = "sk-test-12345"
headers = {"Authorization": f"Bearer {API_KEY}"}

# Chat with hybrid intelligence
def chat(message):
    response = requests.post(
        f"{BASE_URL}/api/chat",
        headers=headers,
        json={"message": message}
    )
    return response.json()

# Example queries
print(chat("What is John's attendance?"))  # S3 data
print(chat("What's the weather in London?"))  # External API
print(chat("Tell me a joke"))  # General knowledge
```

### JavaScript Example
```javascript
const BASE_URL = "http://schoolchatbot-213277610.us-east-1.elb.amazonaws.com";
const API_KEY = "sk-test-12345";

async function chatAPI(message) {
  const response = await fetch(`${BASE_URL}/api/chat`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ message })
  });
  
  return await response.json();
}

// Usage
chatAPI("Show me student attendance data").then(console.log);
chatAPI("What's the weather today?").then(console.log);
```

## Intelligent Query Routing

The API automatically determines the best data source for each query:

### S3 Attendance Queries
Keywords: attendance, student, school, absent, present, class, roll, register, grade
- "What is John's attendance?"
- "List all students in grade 10"
- "Who was absent yesterday?"

### External Weather Queries  
Keywords: weather, temperature, rain, sunny, cloudy, forecast
- "What's the weather in London?"
- "Is it raining today?"
- "What's the temperature?"

### External News Queries
Keywords: news, headlines, current events, breaking news
- "What's in the news today?"
- "Show me latest headlines"
- "Any breaking news?"

### External Quote Queries
Keywords: quote, inspiration, motivational, wisdom
- "Give me an inspirational quote"
- "Share some wisdom"
- "Motivational saying"

### External Fact Queries
Keywords: fact, random fact, interesting, did you know, trivia
- "Tell me a random fact"
- "Something interesting"
- "Did you know trivia"

### General Knowledge
Everything else goes to Bedrock AI for general knowledge responses.

## Environment Variables

For enhanced functionality, set these environment variables:

```bash
# Required for real weather data
export OPENWEATHER_API_KEY="your_openweather_api_key"

# Required for real news data  
export NEWS_API_KEY="your_newsapi_key"

# Optional: Custom secret key
export SECRET_KEY="your_flask_secret_key"
```

## Rate Limits
- No specific rate limits currently implemented
- External APIs may have their own rate limits
- Consider implementing rate limiting for production use

## Support
For questions or issues, contact the development team or check the application logs.