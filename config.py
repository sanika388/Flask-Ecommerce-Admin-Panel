import os

class Config:
    # --- Database Settings (assuming your existing MySQL setup) ---
    MYSQL_HOST = 'localhost'
    MYSQL_USER = 'root'
    MYSQL_PASSWORD = 'sanika'
    MYSQL_DB = 'ecom_admin_db'
    MYSQL_CURSORCLASS = 'DictCursor' # Important for fetching results as dictionaries

    # --- Flask App Settings ---
    SECRET_KEY = os.urandom(24) # Ensure this is set for session security

    # --- Flask-Mail Settings (if you configured email alerts) ---
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'admin@ecom.com'
    MAIL_PASSWORD = 'finalpassword123'
    MAIL_DEFAULT_SENDER = 'your_email@gmail.com'

    # --- FILE UPLOAD SETTINGS (FIXING THE KEY ERROR) ---
    # Define the folder where product images will be stored (relative to app.py)
    UPLOAD_FOLDER = 'static/images/products' 
    
    # Define allowed extensions for security
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'} 
    
    # Define max file size (16 MB limit enforced by Flask)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    PER_PAGE = 10
    LOW_STOCK_THRESHOLD = 5