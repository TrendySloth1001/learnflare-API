from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import logging
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Extended User model with additional fields
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    surname = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    mobile = db.Column(db.String(15), nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # Role: 'Student' or 'Teacher'

# Ensure database tables are created
def init_db():
    with app.app_context():
        try:
            # Delete existing database file
            db_path = 'users.db'
            if os.path.exists(db_path):
                os.remove(db_path)
                print("Removed existing database")

            # Create new database
            db.create_all()
            print("Database initialized successfully")
        except Exception as e:
            print(f"Database initialization error: {str(e)}")
            raise e

# Registration route
@app.route('/register', methods=['POST'])
def register():
    try:
        print("Received registration request")  # Debug print
        if not request.is_json:
            return jsonify({"message": "Request must be JSON"}), 400

        data = request.get_json()
        print(f"Received data: {data}")  # Debug print
        
        if not data:
            return jsonify({"message": "No data provided"}), 400

        # Validate all required fields
        required_fields = ['name', 'surname', 'email', 'mobile', 'password', 'role']
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return jsonify({"message": f"Missing fields: {', '.join(missing_fields)}"}), 400

        # Validate email format (basic check)
        if '@' not in data['email']:
            return jsonify({"message": "Invalid email format"}), 400

        # Validate role
        if data['role'] not in ['Learner', 'Mentor']:
            return jsonify({"message": "Role must be either 'Learner' or 'Mentor'"}), 400

        try:
            # Check for existing user
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
            
            print(f"Creating user: {new_user.email}")  # Debug print
            db.session.add(new_user)
            db.session.commit()
            print("User created successfully")  # Debug print
            
            return jsonify({
                "message": f"{data['role']} registered successfully",
                "user_id": new_user.id
            }), 201
            
        except Exception as db_error:
            print(f"Database error: {str(db_error)}")  # Debug print
            db.session.rollback()
            return jsonify({"message": f"Database error: {str(db_error)}"}), 500
    
    except Exception as e:
        print(f"Registration error: {str(e)}")  # Debug print
        return jsonify({"message": f"Registration error: {str(e)}"}), 500

# Login route
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
        requested_role = data.get('role')  # Role they want to access

        if not email or not password or not requested_role:
            return jsonify({"message": "Email, password, and role are required"}), 400

        # Validate role
        if requested_role not in ['Learner', 'Mentor']:
            return jsonify({"message": "Invalid role. Must be either 'Learner' or 'Mentor'"}), 400

        user = User.query.filter_by(email=email).first()
        
        # Check if user exists and credentials match
        if not user or user.password != password:
            return jsonify({"message": "Invalid email or password"}), 401

        # Role-based access control logic
        if user.role == 'Learner' and requested_role != 'Learner':
            # Students can only access Student role
            return jsonify({
                "message": "Access denied. Students can only access student features"
            }), 403
        elif user.role == 'Mentor':
            # Teachers can access both roles
            pass  # Allow access to continue
        elif user.role != requested_role:
            # For any other case where roles don't match
            return jsonify({
                "message": f"Access denied for {requested_role} role"
            }), 403

        return jsonify({
            "message": "Login successful",
            "actual_role": user.role,  # User's actual role
            "accessing_as": requested_role,  # Role they're accessing as
            "user_id": user.id,
            "name": user.name,
            "email": user.email,
            "has_teacher_access": user.role == 'Mentor'  # Flag to indicate if user has teacher privileges
        }), 200

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({"message": "An error occurred during login"}), 500

if __name__ == '__main__':
    init_db()  # This will recreate the database
    app.run(host='0.0.0.0', port=5000, debug=True)