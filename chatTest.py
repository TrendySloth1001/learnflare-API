from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config["SECRET_KEY"] = "your_secret_key"
socketio = SocketIO(app, cors_allowed_origins="*")  # Allow CORS for testing

users = {}  # Store user connections

@socketio.on("connect")
def handle_connect():
    print("User connected:", request.sid)

@socketio.on("disconnect")
def handle_disconnect():
    print("User disconnected:", request.sid)

@socketio.on("join")
def handle_join(data):
    username = data["username"]
    room = data["room"]
    join_room(room)
    users[request.sid] = {"username": username, "room": room}
    emit("message", {"msg": f"{username} joined {room}"}, room=room)

@socketio.on("send_message")
def handle_message(data):
    room = data["room"]
    message = data["message"]
    username = users[request.sid]["username"]
    emit("message", {"username": username, "msg": message}, room=room)

if __name__ == "__main__":
    socketio.run(app, debug=True)
