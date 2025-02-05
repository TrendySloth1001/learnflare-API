from datetime import datetime
import os
from flask import Response, request, jsonify
from authApp import app, db, User
import logging
import google.generativeai as genai
import time
from flask_cors import CORS
import re
from flask_socketio import SocketIO, join_room, leave_room, emit
import json
import datetime

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
        #"timestamp": datetime.now().isoformat()        -----------------------------------Need to review *
    })

@app.route('/generate/stream', methods=['POST'])
def generate_stream_response():
    """Streams AI response in real-time for Flutter"""
    data = request.get_json()
    prompt = data.get("prompt", "").strip()

    if not prompt:
        return jsonify({"error": "⚠️ Prompt is required"}), 400

    return Response(stream_response(prompt), content_type="text/plain")


#------------------------------------------chat routes--------------------------------------------------------#


socketio = SocketIO(app, cors_allowed_origins="*")

GROUPS_FILE = "groups.json"

# Load or create JSON database
def load_groups():
    if not os.path.exists(GROUPS_FILE):
        with open(GROUPS_FILE, "w") as f:
            json.dump({"groups": {}}, f)
    with open(GROUPS_FILE, "r") as f:
        return json.load(f)

def save_groups(data):
    with open(GROUPS_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Reset JSON file (Clear Groups & Chats)
@app.route("/reset_groups", methods=["POST"])
def reset_groups():
    save_groups({"groups": {}})
    return jsonify({"message": "All groups and messages have been reset"}), 200


# Create a new group
@app.route("/create_group", methods=["POST"])
def create_group():
    data = request.get_json()
    group_name = data.get("group_name")
    user_email = data.get("email")

    if not group_name or not user_email:
        return jsonify({"message": "Group name and user email required"}), 400

    groups = load_groups()
    if group_name in groups["groups"]:
        return jsonify({"message": "Group already exists"}), 400

    groups["groups"][group_name] = {
        "name": group_name,
        "members": [user_email],
        "messages": []
    }
    save_groups(groups)

    return jsonify({"message": "Group created successfully", "group_name": group_name}), 201

# Join a group
@app.route("/join_group", methods=["POST"])
def join_group():
    data = request.get_json()
    group_name = data.get("group_name")
    user_email = data.get("email")

    if not group_name or not user_email:
        return jsonify({"message": "Group name and user email required"}), 400

    groups = load_groups()
    if group_name not in groups["groups"]:
        return jsonify({"message": "Group does not exist"}), 404

    if user_email not in groups["groups"][group_name]["members"]:
        groups["groups"][group_name]["members"].append(user_email)
        save_groups(groups)

    return jsonify({"message": f"Joined {group_name} successfully"}), 200

# Fetch all groups
@app.route("/get_groups", methods=["GET"])
def get_groups():
    groups = load_groups()
    return jsonify(groups["groups"]), 200

# Fetch chat history of a group
@app.route("/get_group_chats", methods=["GET"])
def get_group_chats():
    group_name = request.args.get("group_name")

    if not group_name:
        return jsonify({"message": "Group name required"}), 400

    groups = load_groups()
    if group_name not in groups["groups"]:
        return jsonify({"message": "Group does not exist"}), 404

    return jsonify(groups["groups"][group_name]["messages"]), 200

# Handle messaging
@socketio.on("send_message")
def handle_send_message(data):
    group_name = data.get("group_name")
    user_email = data.get("email")
    message = data.get("message")

    if not group_name or not user_email or not message:
        return

    groups = load_groups()
    if group_name not in groups["groups"]:
        return

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg_data = {"from": user_email, "message": message, "timestamp": timestamp}

    groups["groups"][group_name]["messages"].append(msg_data)
    save_groups(groups)

    emit("receive_message", msg_data, room=group_name, broadcast=True)

# Join a SocketIO room
@socketio.on("join")
def on_join(data):
    group_name = data.get("group_name")
    user_email = data.get("email")

    if group_name and user_email:
        join_room(group_name)
        emit("user_joined", {"message": f"{user_email} joined {group_name}"}, room=group_name)
        print(f"{user_email} joined {group_name}")

# Leave a group
@socketio.on("leave")
def on_leave(data):
    group_name = data.get("group_name")
    user_email = data.get("email")

    if group_name and user_email:
        leave_room(group_name)
        emit("user_left", {"message": f"{user_email} left {group_name}"}, room=group_name)
        print(f"{user_email} left {group_name}")

# Handle message deletion in SocketIO

@app.route("/delete_message", methods=["POST"])
def delete_message():
    data = request.json
    group_id = data.get("group_id")
    message_id = data.get("message_id")  # Assuming each message has a unique ID

    groups = load_groups()  # Load existing groups
    if group_id in groups["groups"]:
        group_messages = groups["groups"][group_id]["messages"]
        # Filter out the message with the given message_id
        updated_messages = [msg for msg in group_messages if msg["id"] != message_id]
        groups["groups"][group_id]["messages"] = updated_messages
        save_groups(groups)  # Save updated groups

        return jsonify({"message": "Message deleted successfully"}), 200
    else:
        return jsonify({"error": "Group not found"}), 404
