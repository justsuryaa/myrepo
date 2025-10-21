#!/usr/bin/env python3
"""
ADMIN DASHBOARD - View all user interactions, prompts, and analytics
Shows real-time user activity with timestamps, IP addresses, and response metrics
"""

import sqlite3
import json
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify
import os

class AdminDashboard:
    def __init__(self, db_path="school_feedback.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database with interactions table if it doesn't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create interactions table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interactions (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                user_question TEXT NOT NULL,
                ai_response TEXT NOT NULL,
                query_type TEXT,
                response_time_ms INTEGER,
                session_id TEXT,
                user_ip TEXT,
                user_agent TEXT
            )
        ''')
        
        # Create feedback table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                interaction_id TEXT,
                timestamp TEXT NOT NULL,
                rating INTEGER NOT NULL,
                feedback_text TEXT,
                is_helpful BOOLEAN,
                user_ip TEXT,
                FOREIGN KEY (interaction_id) REFERENCES interactions (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_all_interactions(self, limit=100, offset=0):
        """Get all user interactions with pagination"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT i.*, f.rating, f.feedback_text
            FROM interactions i
            LEFT JOIN feedback f ON i.id = f.interaction_id
            ORDER BY i.timestamp DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        
        interactions = []
        for row in cursor.fetchall():
            interactions.append({
                'id': row[0],
                'timestamp': row[1],
                'user_question': row[2],
                'ai_response': row[3],
                'query_type': row[4],
                'response_time_ms': row[5],
                'session_id': row[6],
                'user_ip': row[7],
                'user_agent': row[8],
                'rating': row[9],
                'feedback_text': row[10]
            })
        
        conn.close()
        return interactions
    
    def get_analytics_summary(self):
        """Get overall analytics summary"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total interactions
        cursor.execute('SELECT COUNT(*) FROM interactions')
        total_interactions = cursor.fetchone()[0]
        
        # Today's interactions
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('SELECT COUNT(*) FROM interactions WHERE date(timestamp) = ?', (today,))
        today_interactions = cursor.fetchone()[0]
        
        # Average response time
        cursor.execute('SELECT AVG(response_time_ms) FROM interactions WHERE response_time_ms > 0')
        avg_response_time = cursor.fetchone()[0] or 0
        
        # Total feedback
        cursor.execute('SELECT COUNT(*) FROM feedback')
        total_feedback = cursor.fetchone()[0]
        
        # Average rating
        cursor.execute('SELECT AVG(rating) FROM feedback')
        avg_rating = cursor.fetchone()[0] or 0
        
        # Top query types
        cursor.execute('''
            SELECT query_type, COUNT(*) as count 
            FROM interactions 
            GROUP BY query_type 
            ORDER BY count DESC 
            LIMIT 5
        ''')
        top_query_types = cursor.fetchall()
        
        # Recent activity (last 7 days)
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT date(timestamp) as day, COUNT(*) as count
            FROM interactions 
            WHERE date(timestamp) >= ?
            GROUP BY date(timestamp)
            ORDER BY day DESC
        ''', (week_ago,))
        daily_activity = cursor.fetchall()
        
        conn.close()
        
        return {
            'total_interactions': total_interactions,
            'today_interactions': today_interactions,
            'avg_response_time': round(avg_response_time, 2),
            'total_feedback': total_feedback,
            'avg_rating': round(avg_rating, 2),
            'top_query_types': top_query_types,
            'daily_activity': daily_activity
        }
    
    def search_interactions(self, query, query_type=None, date_from=None, date_to=None):
        """Search interactions with filters"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        sql = '''
            SELECT i.*, f.rating, f.feedback_text
            FROM interactions i
            LEFT JOIN feedback f ON i.id = f.interaction_id
            WHERE (i.user_question LIKE ? OR i.ai_response LIKE ?)
        '''
        params = [f'%{query}%', f'%{query}%']
        
        if query_type:
            sql += ' AND i.query_type = ?'
            params.append(query_type)
        
        if date_from:
            sql += ' AND date(i.timestamp) >= ?'
            params.append(date_from)
        
        if date_to:
            sql += ' AND date(i.timestamp) <= ?'
            params.append(date_to)
        
        sql += ' ORDER BY i.timestamp DESC LIMIT 50'
        
        cursor.execute(sql, params)
        
        interactions = []
        for row in cursor.fetchall():
            interactions.append({
                'id': row[0],
                'timestamp': row[1],
                'user_question': row[2],
                'ai_response': row[3],
                'query_type': row[4],
                'response_time_ms': row[5],
                'session_id': row[6],
                'user_ip': row[7],
                'user_agent': row[8],
                'rating': row[9],
                'feedback_text': row[10]
            })
        
        conn.close()
        return interactions

def create_admin_app():
    """Create Flask app with admin dashboard"""
    app = Flask(__name__)
    dashboard = AdminDashboard()
    
    @app.route('/admin')
    @app.route('/admin/')
    def admin_home():
        """Main admin dashboard"""
        analytics = dashboard.get_analytics_summary()
        recent_interactions = dashboard.get_all_interactions(limit=20)
        
        return render_template_string(ADMIN_TEMPLATE, 
                                    analytics=analytics, 
                                    interactions=recent_interactions,
                                    page_title="Admin Dashboard")
    
    @app.route('/admin/interactions')
    def admin_interactions():
        """View all interactions with pagination"""
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        offset = (page - 1) * limit
        
        interactions = dashboard.get_all_interactions(limit=limit, offset=offset)
        analytics = dashboard.get_analytics_summary()
        
        return render_template_string(INTERACTIONS_TEMPLATE, 
                                    interactions=interactions,
                                    analytics=analytics,
                                    page=page,
                                    limit=limit,
                                    page_title="All Interactions")
    
    @app.route('/admin/search')
    def admin_search():
        """Search interactions"""
        query = request.args.get('q', '')
        query_type = request.args.get('type', '')
        date_from = request.args.get('from', '')
        date_to = request.args.get('to', '')
        
        if query:
            interactions = dashboard.search_interactions(query, query_type, date_from, date_to)
        else:
            interactions = []
        
        return render_template_string(SEARCH_TEMPLATE,
                                    interactions=interactions,
                                    query=query,
                                    query_type=query_type,
                                    date_from=date_from,
                                    date_to=date_to,
                                    page_title="Search Interactions")
    
    @app.route('/admin/api/stats')
    def api_stats():
        """API endpoint for real-time stats"""
        analytics = dashboard.get_analytics_summary()
        return jsonify(analytics)
    
    @app.route('/admin/api/interactions')
    def api_interactions():
        """API endpoint for interactions"""
        limit = int(request.args.get('limit', 10))
        interactions = dashboard.get_all_interactions(limit=limit)
        return jsonify(interactions)
    
    return app

# HTML Templates
ADMIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>{{page_title}} - School Chatbot Admin</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; }
        .header { background: #2c3e50; color: white; padding: 1rem 2rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header h1 { font-size: 1.5rem; margin-bottom: 0.5rem; }
        .header nav a { color: #ecf0f1; text-decoration: none; margin-right: 1rem; padding: 0.5rem; border-radius: 4px; }
        .header nav a:hover { background: #34495e; }
        .container { max-width: 1200px; margin: 2rem auto; padding: 0 1rem; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
        .stat-card { background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }
        .stat-card h3 { font-size: 2rem; color: #3498db; margin-bottom: 0.5rem; }
        .stat-card p { color: #7f8c8d; font-weight: 500; }
        .card { background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 2rem; }
        .card-header { padding: 1rem 1.5rem; border-bottom: 1px solid #ecf0f1; background: #34495e; color: white; border-radius: 8px 8px 0 0; }
        .card-body { padding: 1.5rem; }
        .interaction { border-bottom: 1px solid #ecf0f1; padding: 1rem 0; }
        .interaction:last-child { border-bottom: none; }
        .interaction-header { display: flex; justify-content: between; align-items: start; margin-bottom: 0.5rem; }
        .timestamp { color: #7f8c8d; font-size: 0.9rem; }
        .query-type { background: #3498db; color: white; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.8rem; }
        .user-question { background: #ecf0f1; padding: 0.75rem; border-radius: 4px; margin: 0.5rem 0; font-family: monospace; }
        .ai-response { background: #e8f5e9; padding: 0.75rem; border-radius: 4px; margin: 0.5rem 0; }
        .interaction-meta { display: flex; gap: 1rem; font-size: 0.85rem; color: #7f8c8d; margin-top: 0.5rem; }
        .rating { color: #f39c12; font-weight: bold; }
        .btn { background: #3498db; color: white; padding: 0.5rem 1rem; border: none; border-radius: 4px; text-decoration: none; display: inline-block; cursor: pointer; }
        .btn:hover { background: #2980b9; }
        .refresh-btn { position: fixed; bottom: 2rem; right: 2rem; background: #27ae60; border-radius: 50px; padding: 1rem; box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
        @media (max-width: 768px) { .container { padding: 0 0.5rem; } .stats-grid { grid-template-columns: 1fr 1fr; } }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎓 School Chatbot Admin Dashboard</h1>
        <nav>
            <a href="/admin">Dashboard</a>
            <a href="/admin/interactions">All Interactions</a>
            <a href="/admin/search">Search</a>
            <a href="/">← Back to Chat</a>
        </nav>
    </div>
    
    <div class="container">
        <!-- Analytics Summary -->
        <div class="stats-grid">
            <div class="stat-card">
                <h3>{{analytics.total_interactions}}</h3>
                <p>Total Interactions</p>
            </div>
            <div class="stat-card">
                <h3>{{analytics.today_interactions}}</h3>
                <p>Today's Interactions</p>
            </div>
            <div class="stat-card">
                <h3>{{analytics.avg_response_time}}ms</h3>
                <p>Avg Response Time</p>
            </div>
            <div class="stat-card">
                <h3>{{analytics.total_feedback}}</h3>
                <p>Total Feedback</p>
            </div>
            <div class="stat-card">
                <h3>{{analytics.avg_rating}}/5</h3>
                <p>Average Rating</p>
            </div>
        </div>
        
        <!-- Recent Interactions -->
        <div class="card">
            <div class="card-header">
                <h2>Recent User Interactions (Last 20)</h2>
            </div>
            <div class="card-body">
                {% for interaction in interactions %}
                <div class="interaction">
                    <div class="interaction-header">
                        <span class="timestamp">{{interaction.timestamp}}</span>
                        <span class="query-type">{{interaction.query_type or 'general'}}</span>
                    </div>
                    <div class="user-question">
                        <strong>User:</strong> {{interaction.user_question}}
                    </div>
                    <div class="ai-response">
                        <strong>AI:</strong> {{interaction.ai_response[:200]}}{% if interaction.ai_response|length > 200 %}...{% endif %}
                    </div>
                    <div class="interaction-meta">
                        <span>IP: {{interaction.user_ip or 'Unknown'}}</span>
                        <span>Response: {{interaction.response_time_ms or 0}}ms</span>
                        {% if interaction.rating %}
                        <span class="rating">Rating: {{interaction.rating}}/5 ⭐</span>
                        {% endif %}
                        <span>ID: {{interaction.id[:8]}}</span>
                    </div>
                </div>
                {% endfor %}
                
                <div style="text-align: center; margin-top: 1rem;">
                    <a href="/admin/interactions" class="btn">View All Interactions</a>
                </div>
            </div>
        </div>
        
        <!-- Quick Actions -->
        <div class="card">
            <div class="card-header">
                <h2>Quick Actions</h2>
            </div>
            <div class="card-body" style="text-align: center;">
                <a href="/admin/search" class="btn" style="margin: 0.5rem;">🔍 Search Interactions</a>
                <a href="/admin/interactions" class="btn" style="margin: 0.5rem;">📋 View All Data</a>
                <button onclick="refreshData()" class="btn" style="margin: 0.5rem;">🔄 Refresh Data</button>
            </div>
        </div>
    </div>
    
    <button class="refresh-btn" onclick="refreshData()" title="Refresh Data">🔄</button>
    
    <script>
        function refreshData() {
            location.reload();
        }
        
        // Auto-refresh every 30 seconds
        setInterval(refreshData, 30000);
        
        // Add timestamp to show last refresh
        document.addEventListener('DOMContentLoaded', function() {
            const now = new Date().toLocaleTimeString();
            document.title = '{{page_title}} - Last Updated: ' + now;
        });
    </script>
</body>
</html>
'''

INTERACTIONS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>{{page_title}} - School Chatbot Admin</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; line-height: 1.6; }
        .header { background: #2c3e50; color: white; padding: 1rem 2rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header h1 { font-size: 1.5rem; margin-bottom: 0.5rem; }
        .header nav a { color: #ecf0f1; text-decoration: none; margin-right: 1rem; padding: 0.5rem; border-radius: 4px; }
        .header nav a:hover { background: #34495e; }
        .container { max-width: 1200px; margin: 2rem auto; padding: 0 1rem; }
        .interaction { background: white; margin-bottom: 1rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); padding: 1.5rem; }
        .interaction-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 2px solid #ecf0f1; }
        .timestamp { color: #7f8c8d; font-weight: bold; }
        .query-type { background: #3498db; color: white; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.85rem; font-weight: bold; }
        .user-question { background: #e74c3c; color: white; padding: 1rem; border-radius: 8px; margin: 0.75rem 0; }
        .ai-response { background: #27ae60; color: white; padding: 1rem; border-radius: 8px; margin: 0.75rem 0; }
        .interaction-meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.5rem; font-size: 0.9rem; color: #7f8c8d; margin-top: 1rem; padding-top: 0.5rem; border-top: 1px solid #ecf0f1; }
        .meta-item { background: #f8f9fa; padding: 0.5rem; border-radius: 4px; }
        .rating { color: #f39c12; font-weight: bold; }
        .pagination { text-align: center; margin: 2rem 0; }
        .pagination a { background: #3498db; color: white; padding: 0.5rem 1rem; margin: 0 0.25rem; border-radius: 4px; text-decoration: none; }
        .pagination a:hover { background: #2980b9; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📋 All User Interactions</h1>
        <nav>
            <a href="/admin">Dashboard</a>
            <a href="/admin/interactions">All Interactions</a>
            <a href="/admin/search">Search</a>
            <a href="/">← Back to Chat</a>
        </nav>
    </div>
    
    <div class="container">
        <div style="text-align: center; margin-bottom: 2rem; background: white; padding: 1rem; border-radius: 8px;">
            <h2>Showing {{interactions|length}} interactions (Page {{page}})</h2>
            <p>Total in database: {{analytics.total_interactions}} | Today: {{analytics.today_interactions}}</p>
        </div>
        
        {% for interaction in interactions %}
        <div class="interaction">
            <div class="interaction-header">
                <span class="timestamp">{{interaction.timestamp}}</span>
                <span class="query-type">{{interaction.query_type or 'general'}}</span>
            </div>
            
            <div class="user-question">
                <strong>👤 USER QUESTION:</strong><br>
                {{interaction.user_question}}
            </div>
            
            <div class="ai-response">
                <strong>🤖 AI RESPONSE:</strong><br>
                {{interaction.ai_response}}
            </div>
            
            {% if interaction.feedback_text %}
            <div style="background: #f39c12; color: white; padding: 1rem; border-radius: 8px; margin: 0.75rem 0;">
                <strong>💭 USER FEEDBACK:</strong><br>
                {{interaction.feedback_text}}
            </div>
            {% endif %}
            
            <div class="interaction-meta">
                <div class="meta-item"><strong>IP Address:</strong> {{interaction.user_ip or 'Unknown'}}</div>
                <div class="meta-item"><strong>Response Time:</strong> {{interaction.response_time_ms or 0}}ms</div>
                <div class="meta-item"><strong>Session ID:</strong> {{interaction.session_id or 'N/A'}}</div>
                {% if interaction.rating %}
                <div class="meta-item rating"><strong>Rating:</strong> {{interaction.rating}}/5 ⭐</div>
                {% endif %}
                <div class="meta-item"><strong>Interaction ID:</strong> {{interaction.id[:12]}}</div>
            </div>
        </div>
        {% endfor %}
        
        <div class="pagination">
            {% if page > 1 %}
            <a href="?page={{page-1}}&limit={{limit}}">← Previous</a>
            {% endif %}
            <span style="margin: 0 1rem;">Page {{page}}</span>
            <a href="?page={{page+1}}&limit={{limit}}">Next →</a>
        </div>
    </div>
</body>
</html>
'''

SEARCH_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>{{page_title}} - School Chatbot Admin</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; }
        .header { background: #2c3e50; color: white; padding: 1rem 2rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header h1 { font-size: 1.5rem; margin-bottom: 0.5rem; }
        .header nav a { color: #ecf0f1; text-decoration: none; margin-right: 1rem; padding: 0.5rem; border-radius: 4px; }
        .header nav a:hover { background: #34495e; }
        .container { max-width: 1200px; margin: 2rem auto; padding: 0 1rem; }
        .search-form { background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 2rem; }
        .form-group { margin-bottom: 1rem; }
        .form-group label { display: block; margin-bottom: 0.5rem; font-weight: bold; }
        .form-group input, .form-group select { width: 100%; padding: 0.75rem; border: 1px solid #ddd; border-radius: 4px; font-size: 1rem; }
        .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
        .btn { background: #3498db; color: white; padding: 0.75rem 1.5rem; border: none; border-radius: 4px; cursor: pointer; font-size: 1rem; }
        .btn:hover { background: #2980b9; }
        .interaction { background: white; margin-bottom: 1rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); padding: 1.5rem; }
        .interaction-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
        .timestamp { color: #7f8c8d; font-weight: bold; }
        .query-type { background: #e74c3c; color: white; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.85rem; }
        .user-question { background: #3498db; color: white; padding: 1rem; border-radius: 8px; margin: 0.75rem 0; }
        .ai-response { background: #27ae60; color: white; padding: 1rem; border-radius: 8px; margin: 0.75rem 0; }
        .highlight { background: yellow; padding: 0.2rem; border-radius: 2px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 Search User Interactions</h1>
        <nav>
            <a href="/admin">Dashboard</a>
            <a href="/admin/interactions">All Interactions</a>
            <a href="/admin/search">Search</a>
            <a href="/">← Back to Chat</a>
        </nav>
    </div>
    
    <div class="container">
        <div class="search-form">
            <h2>Search Filters</h2>
            <form method="GET">
                <div class="form-group">
                    <label>Search Query (searches in questions and responses)</label>
                    <input type="text" name="q" value="{{query}}" placeholder="Enter search terms..." autofocus>
                </div>
                
                <div class="form-row">
                    <div class="form-group">
                        <label>Query Type</label>
                        <select name="type">
                            <option value="">All Types</option>
                            <option value="general" {{'selected' if query_type == 'general'}}>General</option>
                            <option value="s3_attendance" {{'selected' if query_type == 's3_attendance'}}>Attendance</option>
                            <option value="external_news" {{'selected' if query_type == 'external_news'}}>News</option>
                            <option value="feedback" {{'selected' if query_type == 'feedback'}}>Feedback</option>
                            <option value="error" {{'selected' if query_type == 'error'}}>Error</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Date Range</label>
                        <div style="display: flex; gap: 0.5rem;">
                            <input type="date" name="from" value="{{date_from}}" placeholder="From">
                            <input type="date" name="to" value="{{date_to}}" placeholder="To">
                        </div>
                    </div>
                </div>
                
                <button type="submit" class="btn">🔍 Search Interactions</button>
            </form>
        </div>
        
        {% if query %}
        <div style="background: white; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; text-align: center;">
            <h3>Search Results for: "{{query}}"</h3>
            <p>Found {{interactions|length}} matching interactions</p>
        </div>
        
        {% for interaction in interactions %}
        <div class="interaction">
            <div class="interaction-header">
                <span class="timestamp">{{interaction.timestamp}}</span>
                <span class="query-type">{{interaction.query_type or 'general'}}</span>
            </div>
            
            <div class="user-question">
                <strong>👤 USER QUESTION:</strong><br>
                {{interaction.user_question}}
            </div>
            
            <div class="ai-response">
                <strong>🤖 AI RESPONSE:</strong><br>
                {{interaction.ai_response}}
            </div>
            
            <div style="display: flex; justify-content: space-between; margin-top: 1rem; font-size: 0.9rem; color: #7f8c8d;">
                <span>IP: {{interaction.user_ip or 'Unknown'}}</span>
                <span>Response: {{interaction.response_time_ms or 0}}ms</span>
                {% if interaction.rating %}
                <span style="color: #f39c12;">Rating: {{interaction.rating}}/5 ⭐</span>
                {% endif %}
            </div>
        </div>
        {% endfor %}
        
        {% if not interactions and query %}
        <div style="background: white; padding: 2rem; text-align: center; border-radius: 8px;">
            <h3>No results found</h3>
            <p>Try different search terms or adjust your filters.</p>
        </div>
        {% endif %}
        
        {% endif %}
    </div>
</body>
</html>
'''

if __name__ == "__main__":
    print("🎯 ADMIN DASHBOARD")
    print("📊 View all user interactions and analytics")
    print("🔗 http://localhost:8080/admin")
    
    app = create_admin_app()
    app.run(host="0.0.0.0", port=8080, debug=True)