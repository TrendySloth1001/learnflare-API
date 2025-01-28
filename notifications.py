from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

notificationApp = Flask(__name__)
notificationApp.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///notifications.db'
notificationApp.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(notificationApp)

# Database Model
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Initialize database
def init_db():
    with notificationApp.app_context():
        db.create_all()

# Endpoint to fetch notifications
@notificationApp.route('/notifications', methods=['GET'])
def get_notifications():
    notifications = Notification.query.order_by(Notification.timestamp.desc()).all()
    return jsonify([
        {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "type": n.type,
            "timestamp": n.timestamp.isoformat()
        } for n in notifications
    ])

# Endpoint to add a notification
@notificationApp.route('/notifications', methods=['POST'])
def add_notification():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    # Check for required fields
    required_fields = ['title', 'message', 'type']
    missing_fields = [field for field in required_fields if field not in data]
    
    if missing_fields:
        return jsonify({
            "error": "Missing required fields",
            "missing_fields": missing_fields
        }), 400

    try:
        new_notification = Notification(
            title=data['title'],
            message=data['message'],
            type=data['type']
        )
        db.session.add(new_notification)
        db.session.commit()
        return jsonify({"message": "Notification added successfully!"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to add notification", "details": str(e)}), 500


