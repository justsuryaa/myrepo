#!/usr/bin/env python3
"""
SIMPLE FEEDBACK APP - Guaranteed to show feedback button
Just the basics: chat + visible feedback button
"""
import os
from flask import Flask, request, render_template_string, jsonify
from ultra_simple_bedrock import SimpleBedrock

app = Flask(__name__)
app.secret_key = "simple_secret_key_123"

# Initialize feedback system
feedback_system = SimpleBedrock("school_feedback.db")

# Simple HTML template with GUARANTEED visible feedback button
SIMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>School Chatbot - Simple Test</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f0f0f0; }
        .container { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .feedback-button { 
            background: #4CAF50; 
            color: white; 
            border: none; 
            padding: 15px 30px; 
            font-size: 18px; 
            border-radius: 8px; 
            cursor: pointer; 
            margin: 20px 0;
            display: block;
            width: 100%;
        }
        .feedback-button:hover { background: #45a049; }
        input[type="text"] { width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #ddd; border-radius: 5px; }
        input[type="submit"] { background: #2196F3; color: white; padding: 12px 24px; border: none; border-radius: 5px; cursor: pointer; }
        .chat-area { background: #f9f9f9; padding: 20px; margin: 20px 0; border-radius: 5px; min-height: 200px; }
        
        /* Modal styles */
        .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.5); }
        .modal-content { background-color: white; margin: 15% auto; padding: 20px; border-radius: 10px; width: 80%; max-width: 500px; }
        .close { color: #aaa; float: right; font-size: 28px; font-weight: bold; cursor: pointer; }
        .close:hover { color: black; }
        .stars { font-size: 30px; text-align: center; margin: 20px 0; }
        .star { color: #ddd; cursor: pointer; margin: 0 5px; }
        .star:hover, .star.selected { color: gold; }
        textarea { width: 100%; height: 80px; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
        .submit-btn { background: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎓 SCHOOL CHATBOT - FEEDBACK TEST</h1>
        
        <!-- GUARANTEED VISIBLE FEEDBACK BUTTON -->
        <button class="feedback-button" onclick="openFeedbackModal()">
            ⭐ RATE MY RESPONSE (ALWAYS VISIBLE)
        </button>
        
        <div style="background: #e7f3ff; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <strong>🧪 Testing Status:</strong><br>
            • This is a simplified version to test feedback<br>
            • The blue button above should ALWAYS be visible<br>
            • Click it to test the feedback modal<br>
        </div>
        
        <form method="post">
            <input type="text" name="user_input" placeholder="Type your question here..." required>
            <input type="submit" value="Submit Question">
        </form>
        
        <div class="chat-area">
            <strong>Chat Area:</strong><br>
            {{ response_text }}
        </div>
    </div>
    
    <!-- Feedback Modal -->
    <div id="feedbackModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeFeedbackModal()">&times;</span>
            <h3>📝 Rate the Response</h3>
            <div class="stars" id="starContainer">
                <span class="star" data-rating="1">★</span>
                <span class="star" data-rating="2">★</span>
                <span class="star" data-rating="3">★</span>
                <span class="star" data-rating="4">★</span>
                <span class="star" data-rating="5">★</span>
            </div>
            <textarea id="feedbackText" placeholder="Optional: How can I improve?"></textarea>
            <br><br>
            <button class="submit-btn" onclick="submitFeedback()">Submit Feedback</button>
        </div>
    </div>
    
    <script>
        let selectedRating = 0;
        
        function openFeedbackModal() {
            document.getElementById('feedbackModal').style.display = 'block';
        }
        
        function closeFeedbackModal() {
            document.getElementById('feedbackModal').style.display = 'none';
            selectedRating = 0;
            updateStars();
            document.getElementById('feedbackText').value = '';
        }
        
        // Star rating functionality
        document.querySelectorAll('.star').forEach(star => {
            star.addEventListener('click', function() {
                selectedRating = parseInt(this.getAttribute('data-rating'));
                updateStars();
            });
        });
        
        function updateStars() {
            document.querySelectorAll('.star').forEach((star, index) => {
                if (index < selectedRating) {
                    star.classList.add('selected');
                } else {
                    star.classList.remove('selected');
                }
            });
        }
        
        async function submitFeedback() {
            if (selectedRating === 0) {
                alert('Please select a rating!');
                return;
            }
            
            const feedbackText = document.getElementById('feedbackText').value;
            
            try {
                const response = await fetch('/submit_feedback', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        rating: selectedRating,
                        feedback_text: feedbackText
                    })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    alert('✅ Feedback submitted successfully!');
                    closeFeedbackModal();
                } else {
                    alert('❌ Error: ' + result.error);
                }
            } catch (error) {
                alert('❌ Network error: ' + error.message);
            }
        }
        
        // Close modal when clicking outside
        window.onclick = function(event) {
            const modal = document.getElementById('feedbackModal');
            if (event.target === modal) {
                closeFeedbackModal();
            }
        }
    </script>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    response_text = "Welcome to the chatbot! Ask me anything."
    
    if request.method == "POST":
        user_input = request.form.get("user_input", "").strip()
        if user_input:
            response_text = f"You asked: '{user_input}' - This is a simple test response. The feedback button should be visible above!"
    
    return render_template_string(SIMPLE_HTML, response_text=response_text)

@app.route("/submit_feedback", methods=["POST"])
def submit_feedback():
    try:
        data = request.get_json()
        rating = data.get('rating')
        feedback_text = data.get('feedback_text', '')
        
        if not rating or rating < 1 or rating > 5:
            return jsonify({"success": False, "error": "Invalid rating"})
        
        # Add feedback to database
        interaction_id = feedback_system.add_feedback(
            user_question="Simple test question",
            ai_response="Simple test response",
            rating=int(rating),
            feedback_text=feedback_text
        )
        
        return jsonify({
            "success": True, 
            "message": f"Feedback saved! Rating: {rating}/5",
            "interaction_id": interaction_id
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    print("🚀 SIMPLE FEEDBACK TEST APP")
    print("📊 Feedback button is GUARANTEED to be visible")
    print("🔗 Running on http://localhost:9000")
    
    port = int(os.environ.get("PORT", 9000))
    app.run(host="0.0.0.0", port=port, debug=True)