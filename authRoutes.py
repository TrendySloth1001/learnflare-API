from datetime import datetime
from flask import Response, request, jsonify
from authApp import app, db, User
import logging
import google.generativeai as genai
import time
from flask_cors import CORS
import re

#--------------------------------------------logging config------------------------------------------------------#

# Configure logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

#--------------------------------------------------------------------------------------------------#


#--------------------------------------------AI config-----------------------------------------------------#
#for AI

CORS(app)  # Allow cross-origin requests for Flutter

# Configure Gemini AI API
genai.configure(api_key="AIzaSyDHaAUL1NItnTzzEHmkfgUU-GD9Pwel9I0")
#--------------------------------------------------------------------------------------------------#

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

#------------------------------------------AI config method--------------------------------------------------------#

def clean_text(text):
    """Removes unwanted formatting like *bold*, **bold**, and converts to bullet points"""
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Remove bold
    text = re.sub(r'\*(.*?)\*', r'\1', text)  # Remove italics
    text = re.sub(r'(\n-|\n•|\n\*)', '\n🔹 ', text)  # Ensure bullet points
    text = text.replace("\n", "\n\n")  # Ensure proper paragraph spacing
    return text.strip()

def format_response(raw_text):
    """Splits AI response into text and code blocks"""
    if "```" in raw_text:
        code_blocks = raw_text.split("```")
        formatted_blocks = []

        for i, block in enumerate(code_blocks):
            block = block.strip()
            if i % 2 == 1:  # Code Block
                lines = block.split("\n")
                language = lines[0] if lines else "plaintext"
                code_content = "\n".join(lines[1:]) if len(lines) > 1 else ""
                formatted_blocks.append({
                    "type": "code",
                    "language": language.strip(),
                    "content": code_content.strip()
                })
            else:  # Text Block
                if block:
                    formatted_blocks.append({"type": "text", "content": clean_text(block)})

        return formatted_blocks

    return [{"type": "text", "content": clean_text(raw_text)}]

def stream_response(prompt):
    """Streams AI response word by word"""
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)

    if response is None or not hasattr(response, 'text'):
        yield "❌ No response from AI\n"
        return

    words = response.text.strip().split()

    for word in words:
        yield word + " "
        time.sleep(0.2)

@app.route('/generate', methods=['POST'])
def generate_response():
    """Returns full response (formatted text and code blocks)"""
    data = request.get_json()
    prompt = data.get("prompt", "").strip()

    if not prompt:
        return jsonify({"error": "⚠️ Prompt is required"}), 400

    # Generate AI Response
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)

    if response is None or not hasattr(response, 'text'):
        return jsonify({"error": "❌ No response from AI"}), 500

    formatted_response = format_response(response.text)

    return jsonify({
        "response": formatted_response,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/generate/stream', methods=['POST'])
def generate_stream_response():
    """Streams AI response in real-time for Flutter"""
    data = request.get_json()
    prompt = data.get("prompt", "").strip()

    if not prompt:
        return jsonify({"error": "⚠️ Prompt is required"}), 400

    return Response(stream_response(prompt), content_type="text/plain")


#--------------------------------------------------------------------------------------------------#
