from flask import Flask, request, jsonify
from flask_socketio import SocketIO, join_room, leave_room, emit
import json
import datetime
import os

app = Flask(__name__)
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



if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
