from flask import request, jsonify
from authApp import app, db, User
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@app.route('/register', methods=['POST'])
def register():
    try:
        if not request.is_json:
            return jsonify({"message": "Request must be JSON"}), 400

        data = request.get_json()
        if not data:
            return jsonify({"message": "No data provided"}), 400

        # Validate required fields
        required_fields = ['name', 'surname', 'email', 'mobile', 'password', 'role']
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return jsonify({"message": f"Missing fields: {', '.join(missing_fields)}"}), 400

        # Validate email format
        if '@' not in data['email']:
            return jsonify({"message": "Invalid email format"}), 400

        # Validate role
        if data['role'] not in ['Learner', 'Mentor']:
            return jsonify({"message": "Role must be either 'Learner' or 'Mentor'"}), 400

        # Check if user already exists
        existing_user = User.query.filter_by(email=data['email']).first()
        if existing_user:
            return jsonify({"message": "Email already registered"}), 400

        # Create new user
        new_user = User(
            name=data['name'].strip(),
            surname=data['surname'].strip(),
            email=data['email'].strip().lower(),
            mobile=data['mobile'].strip(),
            password=data['password'],
            role=data['role']
        )
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": f"{data['role']} registered successfully", "user_id": new_user.id}), 201

    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({"message": f"Registration error: {str(e)}"}), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        if not request.is_json:
            return jsonify({"message": "Request must be JSON"}), 400

        data = request.get_json()
        if not data:
            return jsonify({"message": "No data provided"}), 400

        email = data.get('email')
        password = data.get('password')
        requested_role = data.get('role')

        if not email or not password or not requested_role:
            return jsonify({"message": "Email, password, and role are required"}), 400

        if requested_role not in ['Learner', 'Mentor']:
            return jsonify({"message": "Invalid role. Must be either 'Learner' or 'Mentor'"}), 400

        user = User.query.filter_by(email=email).first()
        if not user or user.password != password:
            return jsonify({"message": "Invalid email or password"}), 401

        if user.role == 'Learner' and requested_role != 'Learner':
            return jsonify({"message": "Access denied for Learner role"}), 403

        return jsonify({
            "message": "Login successful",
            "actual_role": user.role,
            "accessing_as": requested_role,
            "user_id": user.id,
            "name": user.name,
            "email": user.email
        }), 200

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({"message": "An error occurred during login"}), 500
