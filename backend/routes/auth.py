import re
from functools import wraps
from flask import Blueprint, jsonify, request, session
from models import User, db

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_.-]{3,80}$")


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Authentication required.", "status_code": 401}), 401
        return f(*args, **kwargs)
    return decorated_function


def require_role(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get("user_id"):
                return jsonify({"error": "Authentication required.", "status_code": 401}), 401
            if session.get("role") != role:
                return jsonify({"error": f"{role.capitalize()} access required.", "status_code": 403}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not username or not email or not password:
        return jsonify({"error": "Username, email, and password are required.", "status_code": 400}), 400

    if not USERNAME_REGEX.match(username):
        return jsonify({
            "error": "Username must be 3-80 characters long and contain only letters, numbers, underscores, dashes, or dots.",
            "status_code": 400
        }), 400

    if not EMAIL_REGEX.match(email) or len(email) > 120:
        return jsonify({"error": "Invalid email address format.", "status_code": 400}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters long.", "status_code": 400}), 400

    if User.query.filter((User.username == username) | (User.email == email)).first():
        return jsonify({"error": "User with this username or email already exists.", "status_code": 400}), 400

    user = User(username=username, email=email, role="citizen")
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    session["user_id"] = user.id
    session["role"] = user.role

    return jsonify({
        "message": "Registration successful",
        "user": user.to_dict(),
        "status_code": 201
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    identifier = str(data.get("identifier", "")).strip()
    password = str(data.get("password", ""))
    expected_role = data.get("role")

    if not identifier or not password:
        return jsonify({"error": "Username/email and password are required.", "status_code": 400}), 400

    user = User.query.filter(
        (User.username == identifier) | (User.email == identifier.lower())
    ).first()

    if not user or not user.check_password(password):
        return jsonify({
            "error": "Invalid credentials. Please check your username/email and password.",
            "status_code": 401
        }), 401

    if expected_role and user.role != expected_role:
        return jsonify({
            "error": f"Account exists but is not an {expected_role} account.",
            "status_code": 403
        }), 403

    session["user_id"] = user.id
    session["role"] = user.role

    return jsonify({
        "message": "Login successful",
        "user": user.to_dict(),
        "status_code": 200
    })


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully", "status_code": 200})


@auth_bp.route("/me", methods=["GET"])
def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"user": None})

    user = db.session.get(User, user_id)
    if not user:
        session.clear()
        return jsonify({"user": None})

    return jsonify({"user": user.to_dict()})
