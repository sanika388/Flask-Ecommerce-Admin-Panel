E-commerce Admin Panel System
🌟 Project Overview
This is a comprehensive, web-based administrative panel designed for managing the operations of an e-commerce platform. Built with Flask and backed by a MySQL database, it provides robust tools for inventory management, order tracking, and sales reporting in a clean, Tailwind CSS interface.

✨ Features
Role-Based Authentication: Secure login for Admin and Staff users.

Inventory Management: Full CRUD (Create, Read, Update, Delete) functionality for Products, Variants, and Images.

Order Fulfillment: Tracking and updating order statuses (Pending, Shipped, Delivered, etc.).

Data Reporting: Custom module for generating CSV reports of sales and orders.

Security: Uses secure password hashing (pbkdf2:sha256) for all user credentials.

🛠️ Technology Stack
Component	Technology	Role
Backend	Python (Flask)	Core business logic and routing.
Database	MySQL	Persistent storage for all structured data.
ORM	SQLAlchemy	Pythonic interface for database interactions.
Frontend	Tailwind CSS	Utility-first framework for pixel-perfect design.
Security	Werkzeug	Hashing and utility functions.

Export to Sheets
🚀 Quick Start Guide
Follow these steps to get the application running on your local machine.

1. Prerequisites
You must have the following installed:

Python 3.x

MySQL Server (Running locally)

MySQL Workbench or a command-line client

2. Database Setup
The entire database schema and initial data are contained in one script.

Generate Password Hash (CRITICAL):
Before executing the SQL, you must generate the hash for the admin password, finalpassword123. Run the small Python utility from the Project Report (hash_generator.py) and copy the hash string it generates.

Bash

# Example command to run the utility
python path/to/hash_generator.py 
Update SQL: Paste the copied hash string into the database/complete_schema.sql file, replacing the placeholder hash in Section 5a (ADMIN USER INSERTION).

Execute Schema: Open and run the complete database/complete_schema.sql script in MySQL Workbench. This creates the ecom_admin_db and all necessary tables and seed data.

3. Installation & Run
Virtual Environment:

Bash

python -m venv venv
source venv/bin/activate

Install Dependencies:

Bash

pip install -r requirements.txt
Run Application:

Bash

flask run
4. Admin Login Credentials
Access the application in your browser (http://127.0.0.1:5000/) and use the following credentials to log in:

Field	Value
Username (Email)	admin@ecom.com
Password	finalpassword123



This is the key directory structure for the E-commerce Admin Panel:

ecom-admin-panel/
├── .gitignore
├── app.py                      # Main Flask application entry point and routes
├── config.py                   # Application configuration (DB settings, secrets)
├── generate_hash.py            # Utility script to generate admin password hash
├── inventory_management.py     # (Likely) Database/model interaction logic
├── inventory.db                # (Optional) SQLite database file if used for local dev
├── package.json                # Node/NPM package file (for Tailwind/PostCSS)
├── postcss.config.js
├── README.md                   # This documentation file
├── requirements.txt            # Python dependencies
├── tailwind.config.js          # Tailwind CSS configuration
├── venv/                       # Python Virtual Environment (ignored by git)
├── node_modules/               # NPM dependencies (ignored by git)
├── static/
│   ├── css/
│   │   ├── input.css           # Tailwind source file
│   │   └── output.css          # Compiled Tailwind CSS file
│   ├── images/
│   │   └── products/           # Uploaded product images
│   ├── js/
│   │   └── main.js             # Frontend JavaScript logic
│   └── uploads/                # General file uploads
└── templates/
    ├── email/                  # Templates for email notifications (e.g., low stock alerts)
    │   ├── alert_base.html
    │   └── alert_low_stock.html
    ├── includes/               # Reusable UI components (headers, sidebars)
    │   ├── _header.html
    │   └── _sidebar.html
    ├── add_category.html
    ├── add_product.html
    ├── add_user.html
    ├── base.html               # Master layout file
    ├── dashboard.html          # Main admin landing page
    ├── discounts.html
    ├── edit_category.html
    ├── edit_product.html
    ├── login.html              # Authentication view
    ├── orders.html
    ├── order_details.html
    └── # ... (other views like products.html, users.html, returns.html)


 
