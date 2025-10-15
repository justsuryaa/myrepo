#!/usr/bin/env python3
"""
ULTRA BASIC TEST - Just HTML with feedback button
"""
from flask import Flask

app = Flask(__name__)

@app.route("/")
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>FEEDBACK TEST</title>
        <style>
            body { font-family: Arial; padding: 50px; text-align: center; }
            .big-button { 
                background: red; 
                color: white; 
                padding: 30px; 
                font-size: 24px; 
                border: none; 
                border-radius: 10px; 
                cursor: pointer;
                width: 80%;
                margin: 20px;
            }
            .status { background: yellow; padding: 20px; margin: 20px; font-size: 18px; }
        </style>
    </head>
    <body>
        <h1>🚨 FEEDBACK BUTTON TEST 🚨</h1>
        
        <div class="status">
            <strong>STATUS: If you can see this page, Flask is working!</strong><br>
            The red button below should be IMPOSSIBLE to miss.
        </div>
        
        <button class="big-button" onclick="alert('FEEDBACK BUTTON WORKS!')">
            🔴 GIANT RED FEEDBACK BUTTON - CLICK ME! 🔴
        </button>
        
        <div style="margin: 30px; font-size: 16px;">
            <p><strong>What this tests:</strong></p>
            <p>✅ Flask app is running</p>
            <p>✅ HTML is rendering</p>
            <p>✅ JavaScript works</p>
            <p>✅ Button is visible</p>
        </div>
        
        <div style="background: #f0f0f0; padding: 20px; margin: 20px;">
            <strong>Next Steps:</strong><br>
            1. Click the red button to test JavaScript<br>
            2. If this works, we can add the real feedback system<br>
            3. This proves your EC2 setup is correct
        </div>
    </body>
    </html>
    """

@app.route("/health")
def health():
    return "BASIC TEST APP IS WORKING", 200

if __name__ == "__main__":
    print("🚨 ULTRA BASIC TEST APP")
    print("🔴 Should show GIANT RED BUTTON")
    print("🌐 http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)