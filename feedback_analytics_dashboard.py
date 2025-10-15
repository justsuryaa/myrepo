#!/usr/bin/env python3
"""
Feedback Analytics Dashboard and API Endpoints
Provides comprehensive feedback analytics, visualizations, and admin interface
"""

from flask import Flask, jsonify, request, render_template_string
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
from enhanced_feedback_system import EnhancedFeedbackSystem
from model_improvement_pipeline import ModelImprovementPipeline
from dataset_manager import DatasetManager

class FeedbackAnalyticsDashboard:
    """Analytics dashboard for feedback system"""
    
    def __init__(self, feedback_system: EnhancedFeedbackSystem, 
                 improvement_pipeline: ModelImprovementPipeline):
        self.feedback_system = feedback_system
        self.improvement_pipeline = improvement_pipeline
    
    def add_routes_to_app(self, app: Flask):
        """Add analytics routes to existing Flask app"""
        
        @app.route("/api/admin/analytics/overview", methods=["GET"])
        def get_analytics_overview():
            """Get comprehensive analytics overview"""
            try:
                analytics = self.feedback_system.get_feedback_analytics()
                recommendations = self.feedback_system.generate_improvement_recommendations()
                
                return jsonify({
                    "success": True,
                    "data": {
                        "analytics": analytics,
                        "recommendations": recommendations,
                        "timestamp": datetime.now().isoformat()
                    }
                })
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 500
        
        @app.route("/api/admin/analytics/categories", methods=["GET"])
        def get_category_analytics():
            """Get detailed category performance analytics"""
            try:
                conn = sqlite3.connect(self.feedback_system.db_path)
                cursor = conn.cursor()
                
                # Category performance with trends
                cursor.execute('''
                    SELECT 
                        i.query_type,
                        COUNT(*) as total_interactions,
                        COUNT(f.id) as total_feedback,
                        AVG(f.overall_rating) as avg_rating,
                        AVG(f.accuracy_rating) as avg_accuracy,
                        AVG(f.helpfulness_rating) as avg_helpfulness,
                        AVG(f.clarity_rating) as avg_clarity,
                        AVG(i.response_time_ms) as avg_response_time,
                        AVG(i.confidence_score) as avg_confidence
                    FROM interactions i
                    LEFT JOIN feedback f ON i.id = f.interaction_id
                    GROUP BY i.query_type
                    ORDER BY avg_rating DESC
                ''')
                
                categories = []
                for row in cursor.fetchall():
                    categories.append({
                        "category": row[0],
                        "total_interactions": row[1],
                        "total_feedback": row[2],
                        "avg_rating": round(row[3] or 0, 2),
                        "avg_accuracy": round(row[4] or 0, 2), 
                        "avg_helpfulness": round(row[5] or 0, 2),
                        "avg_clarity": round(row[6] or 0, 2),
                        "avg_response_time": round(row[7] or 0, 2),
                        "avg_confidence": round(row[8] or 0, 2),
                        "feedback_rate": round((row[2] / max(row[1], 1)) * 100, 2)
                    })
                
                conn.close()
                
                return jsonify({
                    "success": True,
                    "data": {
                        "categories": categories,
                        "total_categories": len(categories)
                    }
                })
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 500
        
        @app.route("/api/admin/analytics/trends", methods=["GET"])
        def get_trends_analytics():
            """Get time-based trend analytics"""
            try:
                days = int(request.args.get('days', 30))
                
                conn = sqlite3.connect(self.feedback_system.db_path)
                cursor = conn.cursor()
                
                # Daily trends
                cursor.execute('''
                    SELECT 
                        DATE(i.timestamp) as date,
                        COUNT(i.id) as interactions,
                        COUNT(f.id) as feedback_count,
                        AVG(f.overall_rating) as avg_rating,
                        AVG(i.response_time_ms) as avg_response_time
                    FROM interactions i
                    LEFT JOIN feedback f ON i.id = f.interaction_id
                    WHERE DATE(i.timestamp) >= DATE('now', '-{} days')
                    GROUP BY DATE(i.timestamp)
                    ORDER BY date DESC
                '''.format(days))
                
                daily_trends = []
                for row in cursor.fetchall():
                    daily_trends.append({
                        "date": row[0],
                        "interactions": row[1],
                        "feedback_count": row[2],
                        "avg_rating": round(row[3] or 0, 2),
                        "avg_response_time": round(row[4] or 0, 2)
                    })
                
                # Category trends over time
                cursor.execute('''
                    SELECT 
                        i.query_type,
                        DATE(i.timestamp) as date,
                        COUNT(*) as interactions,
                        AVG(f.overall_rating) as avg_rating
                    FROM interactions i
                    LEFT JOIN feedback f ON i.id = f.interaction_id
                    WHERE DATE(i.timestamp) >= DATE('now', '-{} days')
                    GROUP BY i.query_type, DATE(i.timestamp)
                    ORDER BY date DESC, i.query_type
                '''.format(days))
                
                category_trends = {}
                for row in cursor.fetchall():
                    category = row[0]
                    if category not in category_trends:
                        category_trends[category] = []
                    
                    category_trends[category].append({
                        "date": row[1],
                        "interactions": row[2],
                        "avg_rating": round(row[3] or 0, 2)
                    })
                
                conn.close()
                
                return jsonify({
                    "success": True,
                    "data": {
                        "daily_trends": daily_trends,
                        "category_trends": category_trends,
                        "period_days": days
                    }
                })
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 500
        
        @app.route("/api/admin/training/export", methods=["POST"])
        def export_training_data():
            """Export training data in specified format"""
            try:
                data = request.get_json()
                format_type = data.get('format', 'json')
                quality_threshold = float(data.get('quality_threshold', 0.3))
                approved_only = data.get('approved_only', False)
                
                filename, count = self.feedback_system.export_training_data(
                    format_type=format_type,
                    quality_threshold=quality_threshold,
                    approved_only=approved_only
                )
                
                return jsonify({
                    "success": True,
                    "data": {
                        "filename": filename,
                        "training_examples": count,
                        "format": format_type,
                        "quality_threshold": quality_threshold
                    }
                })
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 500
        
        @app.route("/api/admin/improvement/run", methods=["POST"])
        def run_improvement_cycle():
            """Trigger model improvement cycle"""
            try:
                data = request.get_json() or {}
                days_back = data.get('days_back', 7)
                
                results = self.improvement_pipeline.run_improvement_cycle(days_back)
                
                return jsonify({
                    "success": True,
                    "data": results
                })
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 500
        
        @app.route("/api/admin/feedback/approve", methods=["POST"])
        def approve_training_data():
            """Approve training data items for model training"""
            try:
                data = request.get_json()
                training_ids = data.get('training_ids', [])
                
                for training_id in training_ids:
                    self.feedback_system.approve_training_data(training_id)
                
                return jsonify({
                    "success": True,
                    "data": {
                        "approved_count": len(training_ids)
                    }
                })
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 500
        
        @app.route("/admin/dashboard")
        def admin_dashboard():
            """Admin dashboard web interface"""
            return render_template_string(DASHBOARD_HTML)
        
        @app.route("/api/admin/feedback/recent", methods=["GET"])
        def get_recent_feedback():
            """Get recent feedback for review"""
            try:
                limit = int(request.args.get('limit', 20))
                
                conn = sqlite3.connect(self.feedback_system.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT 
                        f.id,
                        f.timestamp,
                        f.overall_rating,
                        f.feedback_text,
                        f.suggested_improvement,
                        i.user_question,
                        i.ai_response,
                        i.query_type
                    FROM feedback f
                    JOIN interactions i ON f.interaction_id = i.id
                    ORDER BY f.timestamp DESC
                    LIMIT ?
                ''', (limit,))
                
                recent_feedback = []
                for row in cursor.fetchall():
                    recent_feedback.append({
                        "id": row[0],
                        "timestamp": row[1],
                        "rating": row[2],
                        "feedback_text": row[3],
                        "suggested_improvement": row[4],
                        "question": row[5],
                        "response": row[6],
                        "category": row[7]
                    })
                
                conn.close()
                
                return jsonify({
                    "success": True,
                    "data": {
                        "feedback": recent_feedback,
                        "total": len(recent_feedback)
                    }
                })
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 500

# HTML template for admin dashboard
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Feedback Analytics Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { background: #2c3e50; color: white; padding: 20px; margin-bottom: 30px; border-radius: 8px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .stat-value { font-size: 2em; font-weight: bold; color: #3498db; }
        .stat-label { color: #7f8c8d; margin-top: 5px; }
        .chart-container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 30px; }
        .chart-container h3 { margin-bottom: 20px; color: #2c3e50; }
        .actions { display: flex; gap: 10px; margin-bottom: 30px; flex-wrap: wrap; }
        .btn { padding: 12px 20px; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; text-decoration: none; }
        .btn-primary { background: #3498db; color: white; }
        .btn-success { background: #27ae60; color: white; }
        .btn-warning { background: #f39c12; color: white; }
        .btn:hover { opacity: 0.9; }
        .feedback-list { background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .feedback-item { padding: 15px; border-bottom: 1px solid #ecf0f1; }
        .feedback-item:last-child { border-bottom: none; }
        .rating { color: #f39c12; font-weight: bold; }
        .category-tag { background: #ecf0f1; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; }
        .loading { text-align: center; padding: 40px; color: #7f8c8d; }
        .error { background: #e74c3c; color: white; padding: 15px; border-radius: 6px; margin: 20px 0; }
        .success { background: #27ae60; color: white; padding: 15px; border-radius: 6px; margin: 20px 0; }
        @media (max-width: 768px) {
            .container { padding: 10px; }
            .stats-grid { grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
            .actions { flex-direction: column; }
            .btn { text-align: center; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 AI Feedback Analytics Dashboard</h1>
            <p>Monitor model performance, analyze user feedback, and track improvements</p>
        </div>
        
        <div id="stats-container" class="stats-grid">
            <div class="loading">Loading analytics...</div>
        </div>
        
        <div class="actions">
            <button class="btn btn-primary" onclick="runImprovementCycle()">🔄 Run Improvement Cycle</button>
            <button class="btn btn-success" onclick="exportTrainingData()">📤 Export Training Data</button>
            <button class="btn btn-warning" onclick="refreshData()">🔄 Refresh Data</button>
        </div>
        
        <div class="chart-container">
            <h3>📊 Rating Distribution</h3>
            <canvas id="ratingChart" width="400" height="200"></canvas>
        </div>
        
        <div class="chart-container">
            <h3>📈 Daily Trends (Last 7 Days)</h3>
            <canvas id="trendChart" width="400" height="200"></canvas>
        </div>
        
        <div class="chart-container">
            <h3>📝 Recent Feedback</h3>
            <div id="feedback-container" class="feedback-list">
                <div class="loading">Loading feedback...</div>
            </div>
        </div>
        
        <div id="messages"></div>
    </div>
    
    <script>
        let ratingChart, trendChart;
        
        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', function() {
            loadAnalytics();
            loadRecentFeedback();
        });
        
        async function loadAnalytics() {
            try {
                const response = await fetch('/api/admin/analytics/overview');
                const data = await response.json();
                
                if (data.success) {
                    displayStats(data.data.analytics);
                    displayRatingChart(data.data.analytics.rating_distribution);
                    loadTrends();
                } else {
                    showError('Failed to load analytics: ' + data.error);
                }
            } catch (error) {
                showError('Error loading analytics: ' + error.message);
            }
        }
        
        async function loadTrends() {
            try {
                const response = await fetch('/api/admin/analytics/trends?days=7');
                const data = await response.json();
                
                if (data.success) {
                    displayTrendChart(data.data.daily_trends);
                }
            } catch (error) {
                console.error('Error loading trends:', error);
            }
        }
        
        async function loadRecentFeedback() {
            try {
                const response = await fetch('/api/admin/feedback/recent?limit=10');
                const data = await response.json();
                
                if (data.success) {
                    displayRecentFeedback(data.data.feedback);
                } else {
                    showError('Failed to load feedback: ' + data.error);
                }
            } catch (error) {
                showError('Error loading feedback: ' + error.message);
            }
        }
        
        function displayStats(analytics) {
            const statsContainer = document.getElementById('stats-container');
            const overview = analytics.overview;
            
            statsContainer.innerHTML = `
                <div class="stat-card">
                    <div class="stat-value">${overview.total_interactions}</div>
                    <div class="stat-label">Total Interactions</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${overview.total_feedback}</div>
                    <div class="stat-label">Total Feedback</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${overview.average_rating}/5</div>
                    <div class="stat-label">Average Rating</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${overview.feedback_rate}%</div>
                    <div class="stat-label">Feedback Rate</div>
                </div>
            `;
        }
        
        function displayRatingChart(ratingDistribution) {
            const ctx = document.getElementById('ratingChart').getContext('2d');
            
            if (ratingChart) ratingChart.destroy();
            
            ratingChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: ['1 Star', '2 Stars', '3 Stars', '4 Stars', '5 Stars'],
                    datasets: [{
                        label: 'Number of Ratings',
                        data: [
                            ratingDistribution[1] || 0,
                            ratingDistribution[2] || 0,
                            ratingDistribution[3] || 0,
                            ratingDistribution[4] || 0,
                            ratingDistribution[5] || 0
                        ],
                        backgroundColor: ['#e74c3c', '#f39c12', '#f1c40f', '#2ecc71', '#27ae60']
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        }
        
        function displayTrendChart(dailyTrends) {
            const ctx = document.getElementById('trendChart').getContext('2d');
            
            if (trendChart) trendChart.destroy();
            
            const dates = dailyTrends.map(d => d.date).reverse();
            const interactions = dailyTrends.map(d => d.interactions).reverse();
            const ratings = dailyTrends.map(d => d.avg_rating).reverse();
            
            trendChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: dates,
                    datasets: [
                        {
                            label: 'Interactions',
                            data: interactions,
                            borderColor: '#3498db',
                            yAxisID: 'y'
                        },
                        {
                            label: 'Avg Rating',
                            data: ratings,
                            borderColor: '#27ae60',
                            yAxisID: 'y1'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                        },
                        y1: {
                            type: 'linear',
                            display: true,
                            position: 'right',
                            min: 0,
                            max: 5,
                            grid: {
                                drawOnChartArea: false,
                            },
                        }
                    }
                }
            });
        }
        
        function displayRecentFeedback(feedback) {
            const container = document.getElementById('feedback-container');
            
            if (feedback.length === 0) {
                container.innerHTML = '<div class="loading">No recent feedback found</div>';
                return;
            }
            
            container.innerHTML = feedback.map(item => `
                <div class="feedback-item">
                    <div style="display: flex; justify-content: between; align-items: center; margin-bottom: 10px;">
                        <span class="rating">★ ${item.rating}/5</span>
                        <span class="category-tag">${item.category}</span>
                        <small style="color: #7f8c8d;">${new Date(item.timestamp).toLocaleDateString()}</small>
                    </div>
                    <div style="margin-bottom: 8px;">
                        <strong>Q:</strong> ${item.question.substring(0, 100)}${item.question.length > 100 ? '...' : ''}
                    </div>
                    ${item.feedback_text ? `<div style="color: #2c3e50;"><strong>Feedback:</strong> ${item.feedback_text}</div>` : ''}
                    ${item.suggested_improvement ? `<div style="color: #e67e22;"><strong>Suggestion:</strong> ${item.suggested_improvement}</div>` : ''}
                </div>
            `).join('');
        }
        
        async function runImprovementCycle() {
            showMessage('Running improvement cycle...', 'info');
            
            try {
                const response = await fetch('/api/admin/improvement/run', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ days_back: 7 })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showMessage(`Improvement cycle completed! Found ${data.data.improvements_identified.length} areas for improvement, created ${data.data.training_data_created} training examples.`, 'success');
                    refreshData();
                } else {
                    showError('Improvement cycle failed: ' + data.error);
                }
            } catch (error) {
                showError('Error running improvement cycle: ' + error.message);
            }
        }
        
        async function exportTrainingData() {
            showMessage('Exporting training data...', 'info');
            
            try {
                const response = await fetch('/api/admin/training/export', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        format: 'bedrock_jsonl',
                        quality_threshold: 0.3,
                        approved_only: true
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showMessage(`Training data exported! File: ${data.data.filename}, Examples: ${data.data.training_examples}`, 'success');
                } else {
                    showError('Export failed: ' + data.error);
                }
            } catch (error) {
                showError('Error exporting data: ' + error.message);
            }
        }
        
        function refreshData() {
            loadAnalytics();
            loadRecentFeedback();
        }
        
        function showMessage(message, type = 'info') {
            const messagesContainer = document.getElementById('messages');
            const messageDiv = document.createElement('div');
            messageDiv.className = type === 'success' ? 'success' : type === 'error' ? 'error' : 'info';
            messageDiv.textContent = message;
            
            messagesContainer.appendChild(messageDiv);
            
            setTimeout(() => {
                messageDiv.remove();
            }, 5000);
        }
        
        function showError(message) {
            showMessage(message, 'error');
        }
    </script>
</body>
</html>
"""

# Example integration with existing Flask app
def add_analytics_to_app(app: Flask, feedback_system: EnhancedFeedbackSystem):
    """Add analytics dashboard to existing Flask app"""
    
    # Initialize components
    dataset_manager = DatasetManager("./analytics_datasets")
    improvement_pipeline = ModelImprovementPipeline(feedback_system, dataset_manager)
    dashboard = FeedbackAnalyticsDashboard(feedback_system, improvement_pipeline)
    
    # Add routes to app
    dashboard.add_routes_to_app(app)
    
    return dashboard

if __name__ == "__main__":
    print("📊 Feedback Analytics Dashboard Demo")
    
    # This would typically be integrated with your main Flask app
    # For demo purposes, create a standalone app
    
    from flask import Flask
    
    app = Flask(__name__)
    app.secret_key = "demo_analytics_key"
    
    # Initialize feedback system
    feedback_system = EnhancedFeedbackSystem("demo_analytics.db")
    
    # Add analytics to app
    dashboard = add_analytics_to_app(app, feedback_system)
    
    # Add some demo data
    interaction1 = feedback_system.log_interaction(
        "What's the weather?", "I can't get weather data", "weather", confidence_score=0.2
    )
    feedback_system.collect_feedback(interaction1, 2, 1, 2, 2, "Doesn't work", "Should connect to weather API")
    
    interaction2 = feedback_system.log_interaction(
        "John's attendance?", "John has 85% attendance", "attendance", confidence_score=0.9
    )
    feedback_system.collect_feedback(interaction2, 5, 5, 5, 5, "Perfect!")
    
    print("✅ Demo setup complete!")
    print("🌐 Visit http://localhost:5000/admin/dashboard to see the analytics dashboard")
    print("📡 API endpoints available at /api/admin/*")
    
    app.run(debug=True, port=5000)