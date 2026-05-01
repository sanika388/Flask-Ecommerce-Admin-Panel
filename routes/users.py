# backend/routes/users.py

from flask import Blueprint

users_bp = Blueprint('users', __name__)

# Route placeholder for listing users (Hour 2)
@users_bp.route('/users', methods=['GET'])
def list_users():
    # Will return mock data until Hour 3
    return "User List Placeholder", 200 

# Route placeholder for status toggle (Hour 3)
@users_bp.route('/users/<int:user_id>/toggle-active', methods=['PUT'])
def toggle_user_status(user_id):
    # Will contain MySQL logic later
    return f"Toggle User {user_id} Status Placeholder", 200