from functools import wraps
from flask import Blueprint, jsonify, request, session
from models import User, db

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Authentication required."}), 401
        return f(*args, **kwargs)
    return decorated_function


def require_role(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get("user_id"):
                return jsonify({"error": "Authentication required."}), 401
            if session.get("role") != role:
                return jsonify({"error": f"{role.capitalize()} access required."}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    role = data.get("role", "citizen").strip().lower()

    if not username or not email or not password:
        return jsonify({"error": "Username, email, and password are required."}), 400

    # Restrict registration to citizen role only via API endpoint (admin must be pre-created or initialized)
    if role != "citizen":
        role = "citizen"

    if User.query.filter((User.username == username) | (User.email == email)).first():
        return jsonify({"error": "User with this username or email already exists."}), 400

    user = User(username=username, email=email, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    session["user_id"] = user.id
    session["role"] = user.role

    return jsonify({"message": "Registration successful", "user": user.to_dict()}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    identifier = data.get("identifier", "").strip()  # username or email
    password = data.get("password", "")
    expected_role = data.get("role")  # optional role filter from frontend tab

    if not identifier or not password:
        return jsonify({"error": "Username/email and password are required."}), 400

    user = User.query.filter(
        (User.username == identifier) | (User.email == identifier.lower())
    ).first()

    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid credentials. Please check your username/email and password."}), 401

    if expected_role and user.role != expected_role:
        return jsonify({"error": f"Account exists but is not an {expected_role} account."}), 403

    session["user_id"] = user.id
    session["role"] = user.role

    return jsonify({"message": "Login successful", "user": user.to_dict()})


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"})


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

