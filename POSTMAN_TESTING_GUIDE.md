# 🚀 School Chatbot API - Postman Testing Guide

## Base URL
```
http://schoolchatbot-213277610.us-east-1.elb.amazonaws.com
```

## Authentication
Your API uses Bearer token authentication with these keys:
- `sk-test-12345` - Test User (read, write)
- `sk-prod-67890` - Admin User (read, write, delete)
- `sk-school-api-key` - School Admin (read, write)

---

## 📋 **1. Health Check (No Auth Required)**

### GET /health
**Method:** `GET`
**URL:** `http://schoolchatbot-213277610.us-east-1.elb.amazonaws.com/health`
**Headers:** None required

**Expected Response:**
```json
{
    "status": "healthy",
    "service": "school-chatbot"
}
```

---

## 📋 **2. API Information (No Auth Required)**

### GET /api/info
**Method:** `GET`
**URL:** `http://schoolchatbot-213277610.us-east-1.elb.amazonaws.com/api/info`
**Headers:** None required

**Expected Response:**
```json
{
    "service": "School Attendance Chatbot API",
    "version": "2.0.0",
    "description": "Simplified hybrid API supporting S3 attendance data and news",
    "capabilities": [
        "Student attendance queries",
        "News headlines",
        "General knowledge questions"
    ],
    "endpoints": {
        "POST /api/chat": "Main chat endpoint with hybrid intelligence",
        "GET /api/students": "List all students from attendance data",
        "GET /api/news": "Get latest news headlines",
        "PUT /api/attendance": "Update attendance records"
    }
}
```

---

## 📋 **3. Hybrid Chat API (Auth Required)**

### POST /api/chat
**Method:** `POST`
**URL:** `http://schoolchatbot-213277610.us-east-1.elb.amazonaws.com/api/chat`

**Headers:**
```
Authorization: Bearer sk-school-api-key
Content-Type: application/json
```

**Body (JSON):**
```json
{
    "message": "What is John's attendance?",
    "history": []
}
```

**Test Cases:**

#### Test 1: S3 Attendance Query
```json
{
    "message": "What is John's attendance rate this month?"
}
```

#### Test 2: News Query (India)
```json
{
    "message": "Latest news in Chennai"
}
```

#### Test 3: News Query (US)
```json
{
    "message": "Tell me the latest news"
}
```

#### Test 4: General Knowledge
```json
{
    "message": "What is the capital of France?"
}
```

**Expected Response:**
```json
{
    "response": "Based on the attendance data, John has been present for 85% of classes...",
    "query_type": "s3_attendance",
    "user": "School Admin",
    "timestamp": 1697123456.789
}
```

---

## 📋 **4. Students List API (Auth Required)**

### GET /api/students
**Method:** `GET`
**URL:** `http://schoolchatbot-213277610.us-east-1.elb.amazonaws.com/api/students`

**Headers:**
```
Authorization: Bearer sk-school-api-key
```

**Expected Response:**
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
    "user": "School Admin",
    "timestamp": 1697123456.789
}
```

---

## 📋 **5. News API (Auth Required)**

### GET /api/news
**Method:** `GET`
**URL:** `http://schoolchatbot-213277610.us-east-1.elb.amazonaws.com/api/news`

**Headers:**
```
Authorization: Bearer sk-school-api-key
```

**Optional Query Parameters:**
- `location=chennai` - For India news
- `location=london` - For UK news
- No parameter - US news (default)

**Examples:**
- `GET /api/news` - US news
- `GET /api/news?location=chennai` - India news
- `GET /api/news?location=london` - UK news

**Expected Response:**
```json
{
    "news": [
        {
            "title": "Breaking: Technology Advances in Education",
            "source": "CNN",
            "description": "Latest developments in educational technology..."
        }
    ],
    "user": "School Admin",
    "timestamp": 1697123456.789
}
```

---

## 📋 **6. Update Attendance API (Auth Required)**

### PUT /api/attendance
**Method:** `PUT`
**URL:** `http://schoolchatbot-213277610.us-east-1.elb.amazonaws.com/api/attendance`

**Headers:**
```
Authorization: Bearer sk-school-api-key
Content-Type: application/json
```

**Body (JSON):**
```json
{
    "student_name": "John Smith",
    "date": "2024-10-12",
    "status": "present",
    "grade": "10th"
}
```

**Expected Response:**
```json
{
    "message": "Attendance update received (demo mode)",
    "data": {
        "student_name": "John Smith",
        "date": "2024-10-12",
        "status": "present"
    },
    "user": "School Admin",
    "timestamp": 1697123456.789,
    "note": "This is a demo endpoint."
}
```

---

## ⚠️ **Error Responses**

### 401 Unauthorized (Missing/Invalid API Key)
```json
{
    "error": "API key is required",
    "code": "MISSING_API_KEY"
}
```

### 400 Bad Request (Missing Required Fields)
```json
{
    "error": "Request must include 'message' field",
    "code": "MISSING_MESSAGE"
}
```

### 403 Forbidden (Insufficient Permissions)
```json
{
    "error": "Insufficient permissions",
    "code": "PERMISSION_DENIED"
}
```

---

## 🧪 **Postman Collection Import**

Create a new collection in Postman and add these requests one by one, or copy this JSON to import:

```json
{
    "info": {
        "name": "School Chatbot API",
        "description": "Complete API collection for School Attendance Chatbot"
    },
    "variable": [
        {
            "key": "baseUrl",
            "value": "http://schoolchatbot-213277610.us-east-1.elb.amazonaws.com"
        },
        {
            "key": "apiKey",
            "value": "sk-school-api-key"
        }
    ]
}
```

---

## 🎯 **Quick Test Checklist**

1. ✅ Health Check: `GET /health`
2. ✅ API Info: `GET /api/info`
3. ✅ Chat - Attendance: `POST /api/chat` with attendance query
4. ✅ Chat - News: `POST /api/chat` with news query
5. ✅ Students List: `GET /api/students`
6. ✅ Direct News: `GET /api/news`
7. ✅ Update Attendance: `PUT /api/attendance`

Each request should return a 200 status code with proper JSON response!