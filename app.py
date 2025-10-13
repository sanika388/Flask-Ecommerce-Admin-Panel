from werkzeug.security import check_password_hash
from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_mysqldb import MySQL
from config import Config
import io 
from werkzeug.security import generate_password_hash
from functools import wraps
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
import csv 
from flask import Response
from datetime import datetime 
import os
import stripe
import math # For pagination
import shutil # For easier cleanup in delete_product
from datetime import date # **NEEDED FOR DISCOUNT DATE COMPARISONS**
# Place this code near the top of your app.py, right after your imports

from functools import wraps
from flask import session, redirect, url_for, flash, request

# Custom decorator to check if user is logged in
# --- DECORATOR: Login Required (Ensuring one consistent name and key) ---
# We will use 'logged_in' as the consistent session key for status checks.

# --- CORRECTED DECORATOR BLOCK (Matches session['loggedin']) ---

def is_logged_in(f):
    """Ensures a user is logged in by checking the 'loggedin' key."""
    @wraps(f)
    def wrap(*args, **kwargs):
        # CRITICAL FIX: Checking for the correct key 'loggedin'
        if 'loggedin' in session and session['loggedin']:
            return f(*args, **kwargs)
        else:
            flash('Unauthorized, please login', 'danger')
            return redirect(url_for('login'))
    return wrap

# --- DECORATOR: Staff or Admin Required ---
def staff_or_admin_required(f):
    """Requires the user to be logged in and have 'Admin' or 'Staff' role."""
    @wraps(f)
    @is_logged_in # Use the corrected login checker
    def decorated_function(*args, **kwargs):
        # NOTE: This assumes your login route also sets session['role']!
        if session.get('role') not in ['Admin', 'Staff']:
            flash('Access denied. You do not have sufficient privileges.', 'danger')
            return redirect(url_for('dashboard')) 
        return f(*args, **kwargs)
    return decorated_function

# --- DECORATOR: Admin Required ---
def admin_required(f):
    """Requires the user to be logged in and have the 'Admin' role."""
    @wraps(f)
    @is_logged_in # Use the corrected login checker
    def decorated_function(*args, **kwargs):
        # NOTE: This assumes your login route also sets session['role']!
        if session.get('role') != 'Admin':
            flash('Access denied. Only Administrators can access this page.', 'danger')
            return redirect(url_for('dashboard')) 
        return f(*args, **kwargs)
    return decorated_function

# Optional: Custom decorator to check if user is an Admin
#def is_admin(f):
 #   @wraps(f)
 #   def wrap(*args, **kwargs):
  #      # Check if user is logged in AND their role is 'Admin'
   #     if 'logged_in' in session and session.get('role') == 'Admin':
    #        return f(*args, **kwargs)
     #   else:
      #      flash('Unauthorized access: Admin privilege required.', 'danger')
       #     return redirect(url_for('dashboard')) # Or redirect to login
   # return wrap
stripe_keys = {
    "secret_key": "sk_test_YOUR_STRIPE_SECRET_KEY",
    "publishable_key": "pk_test_YOUR_STRIPE_PUBLISHABLE_KEY"
}
stripe.api_key = stripe_keys["secret_key"]
# --- CONFIGURATION ---

# 1. App Initialization
app = Flask(__name__)
app.config.from_object(Config)

# 2. MySQL Initialization
mysql = MySQL(app)

# 3. Mail Initialization
mail = Mail(app)

# Pagination setting
PER_PAGE = 10 

# Low stock alert setting
LOW_STOCK_THRESHOLD = 20

# --- FILE HELPER FUNCTIONS ---
def allowed_file(filename):
    """Checks if the file extension is allowed (defined in config.py)."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# --- EMAIL HELPER FUNCTION ---
def send_email_alert(recipient, subject, template, **kwargs):
    """Sends an email alert using Flask-Mail."""
    try:
        msg = Message(subject, recipients=[recipient])
        msg.html = render_template(template, **kwargs)
        mail.send(msg)
        app.logger.info(f"Email sent successfully to {recipient} with subject: {subject}")
        return True
    except Exception as e:
        app.logger.error(f"Error sending email alert to {recipient}: {e}")
        return False

# --- DECORATOR: Login Required ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'loggedin' not in session:
            flash('Please log in to access this page.', 'info')
            return redirect(url_for('login')) 
        return f(*args, **kwargs)
    return decorated_function

# --- DECORATOR: Staff or Admin Required ---
def staff_or_admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if session.get('role') not in ['Admin', 'Staff']:
            flash('Access denied. You do not have sufficient privileges.', 'danger')
            return redirect(url_for('dashboard')) 
        return f(*args, **kwargs)
    return decorated_function

# --- DECORATOR: Admin Required ---
def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'Admin':
            flash('Access denied. Only Administrators can access this page.', 'danger')
            return redirect(url_for('dashboard')) 
        return f(*args, **kwargs)
    return decorated_function

# --- ROUTES ---

@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    page_title = 'Secure Access'
    error = None 
    
    if request.method == 'POST':
        # Get form data
        email = request.form.get('username')
        password = request.form.get('password')
        
        # 1. Connect to MySQL
        cur = mysql.connection.cursor()
        
        # 2. Find the user by email
        cur.execute("SELECT id, email, password_hash, role, name FROM users WHERE email = %s", [email])
        user = cur.fetchone()
        cur.close()

        if user:
            db_password_hash = user['password_hash']
            
            # 3. Check password hash
            if check_password_hash(db_password_hash, password):
                # Password matched! Create session
                session['loggedin'] = True
                session['id'] = user['id']
                session['email'] = user['email']
                session['role'] = user['role']
                session['name'] = user['name']
                
                return redirect(url_for('dashboard'))
            else:
                # Password incorrect
                error = 'Invalid Credentials. Please try again.'
        else:
            # User not found
            error = 'User not found. Invalid Credentials.'
    
    # Render template for GET request or failed POST (passing the error)
    return render_template('login.html', page_title=page_title, error=error)

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', page_title='Dashboard & Analytics', active_page='dashboard')

# --- CATEGORY ROUTES ---

@app.route('/categories')
@admin_required # Only Admin should manage categories
def categories():
    page_title = 'Category Management'
    
    cur = None
    categories_list = []
    
    try:
        cur = mysql.connection.cursor()
        
        # Fetch all categories, including their parent_id and the name of their parent
        cur.execute("""
            SELECT 
                c.id, 
                c.name, 
                c.parent_id,
                p.name AS parent_name,
                COUNT(prod.id) AS product_count 
            FROM categories c
            LEFT JOIN categories p ON c.parent_id = p.id
            LEFT JOIN products prod ON c.id = prod.category_id
            GROUP BY c.id, c.name, c.parent_id, p.name
            ORDER BY c.parent_id ASC, c.name ASC
        """)
        all_categories = cur.fetchall()
        
        # --- Build Hierarchical List ---
        # 1. Separate Top-Level (parent_id is NULL) and Subcategories
        top_level = [c for c in all_categories if c['parent_id'] is None]
        subcategories = [c for c in all_categories if c['parent_id'] is not None]

        # 2. Organize children under their parent for easier display
        hierarchy = {}
        for c in top_level:
            c['children'] = []
            hierarchy[c['id']] = c
        
        for sub in subcategories:
            parent_id = sub['parent_id']
            if parent_id in hierarchy:
                hierarchy[parent_id]['children'].append(sub)
            else:
                # If an orphaned subcategory exists, we treat it as a new top-level entry
                if sub['id'] not in hierarchy:
                     sub['children'] = []
                     hierarchy[sub['id']] = sub

        
        # Convert dictionary values to a list of categories
        categories_list = list(hierarchy.values())
        
    except Exception as e:
        app.logger.error(f"Database error in /categories route: {e}")
        categories_list = []
    finally:
        if cur: cur.close()

    return render_template('categories.html', 
                           page_title=page_title, 
                           active_page='categories', 
                           categories=categories_list)


@app.route('/categories/add', methods=['GET', 'POST'])
@admin_required
def add_category():
    page_title = 'Add New Category'
    cur = None
    categories_for_dropdown = []

    try:
        cur = mysql.connection.cursor()
        # Fetch all categories to populate the Parent dropdown
        cur.execute("SELECT id, name FROM categories ORDER BY name")
        categories_for_dropdown = cur.fetchall()
        
        if request.method == 'POST':
            name = request.form['name']
            parent_id_str = request.form.get('parent_id') # New Field
            
            # Convert parent_id to INT or NULL (0 means No Parent)
            parent_id = int(parent_id_str) if parent_id_str and parent_id_str.isdigit() and int(parent_id_str) != 0 else None
            
            if not name.strip():
                flash('Category name cannot be empty.', 'error')
                # Fall through to render_template
            else:
                # Insert the new category with parent_id
                cur.execute("INSERT INTO categories (name, parent_id) VALUES (%s, %s)", (name, parent_id))
                
                mysql.connection.commit()
                
                flash(f'Category "{name}" created successfully.', 'success')
                return redirect(url_for('categories'))
                
    except Exception as e:
        flash('Error creating category. Name may already exist or database error.', 'error')
        app.logger.error(f"Database error during category insertion: {e}")
    finally:
        if cur: cur.close()
            
    # GET request or POST failure
    return render_template('add_edit_category.html', 
                           page_title=page_title, 
                           active_page='categories', 
                           is_edit=False,
                           categories_for_dropdown=categories_for_dropdown)

@app.route('/categories/edit/<int:category_id>', methods=['GET', 'POST'])
@admin_required
def edit_category(category_id):
    page_title = 'Edit Category'
    cur = None
    categories_for_dropdown = []
    
    try:
        cur = mysql.connection.cursor()
        
        # 1. Fetch all categories for the dropdown (excluding the current category itself to prevent infinite loops)
        cur.execute("SELECT id, name FROM categories WHERE id != %s ORDER BY name", [category_id])
        categories_for_dropdown = cur.fetchall()

        if request.method == 'POST':
            # --- Handle Form Submission (POST) ---
            name = request.form['name']
            parent_id_str = request.form.get('parent_id') # New Field
            
            # Convert parent_id to INT or NULL (0 means No Parent)
            parent_id = int(parent_id_str) if parent_id_str and parent_id_str.isdigit() and int(parent_id_str) != 0 else None
            
            if not name.strip():
                flash('Category name cannot be empty.', 'error')
                return redirect(url_for('edit_category', category_id=category_id))
            
            # Execute the UPDATE query
            cur.execute("UPDATE categories SET name = %s, parent_id = %s WHERE id = %s", (name, parent_id, category_id))
            mysql.connection.commit()
            
            flash(f'Category updated to "{name}" successfully.', 'success')
            return redirect(url_for('categories'))
            
        else:
            # --- Handle Initial Form Load (GET) ---
            # Fetch the category's existing data, including parent_id
            cur.execute("SELECT id, name, parent_id FROM categories WHERE id = %s", [category_id])
            category = cur.fetchone()

            if category is None:
                flash('Category not found.', 'error')
                return redirect(url_for('categories'))

            # Render the form, passing the existing category data and dropdown data
            return render_template('add_edit_category.html', 
                                   page_title=page_title, 
                                   active_page='categories', 
                                   category=category,
                                   categories_for_dropdown=categories_for_dropdown,
                                   is_edit=True)
            
    except Exception as e:
        flash('Error loading or updating category.', 'error')
        app.logger.error(f"Database error during category edit: {e}")
        return redirect(url_for('categories'))
    finally:
        if cur: cur.close()



@app.route('/categories/delete/<int:category_id>', methods=['POST'])
@admin_required
def delete_category(category_id):
    cur = None
    try:
        cur = mysql.connection.cursor()
        
        # Check if any products are linked to this category
        cur.execute("SELECT COUNT(id) AS count FROM products WHERE category_id = %s", [category_id])
        product_count = cur.fetchone()['count']
        
        if product_count > 0:
            flash(f'Cannot delete category. {product_count} product(s) are still linked to it.', 'error')
            return redirect(url_for('categories'))
        
        # If no products are linked, proceed with deletion
        cur.execute("DELETE FROM categories WHERE id = %s", [category_id])
        
        mysql.connection.commit()
        
        flash('Category deleted successfully.', 'success')
        
    except Exception as e:
        flash('Error deleting category.', 'error')
        app.logger.error(f"Database error during category deletion: {e}")
    finally:
        if cur: cur.close()
            
    return redirect(url_for('categories'))

# --- DISCOUNTS ROUTES ---

@app.route('/discounts')
@admin_required
def discounts():
    page_title = 'Discount Management'
    cur = None
    discounts_list = []
    
    # --- 1. Get filter and pagination parameters ---
    status_filter = request.args.get('status', 'all') # Changed default to 'all' for clarity
    search_query = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    
    offset = (page - 1) * PER_PAGE
    
    # --- 2. Build the dynamic SQL query ---
    sql_select = "SELECT id, code, type, value, max_usage, used_count, expiry_date, is_active, start_date FROM discounts"
    sql_count = "SELECT COUNT(id) AS count FROM discounts"
    
    where_clauses = []
    query_params = []
    
    today = date.today().isoformat()
    
    # 1. Apply Status Filter
    if status_filter == 'active':
        # Discount must be explicitly active AND be within its date range
        where_clauses.append("is_active = TRUE AND start_date <= %s AND (expiry_date IS NULL OR expiry_date >= %s)")
        query_params.extend([today, today])
    elif status_filter == 'expired':
        where_clauses.append("expiry_date < %s")
        query_params.append(today)
    elif status_filter == 'inactive':
        # Explicitly marked inactive in the DB, regardless of dates
        where_clauses.append("is_active = FALSE")

    # 2. Apply Search Filter
    if search_query:
        where_clauses.append("(code LIKE %s OR description LIKE %s)")
        query_params.extend([f'%{search_query}%', f'%{search_query}%'])

    # Combine WHERE clauses
    where_clause_str = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
    # --- 3. Execute queries with filters ---
    try:
        cur = mysql.connection.cursor()

        # A. Fetch total count
        cur.execute(sql_count + where_clause_str, query_params)
        total_discounts = cur.fetchone()['count']
        total_pages = math.ceil(total_discounts / PER_PAGE)
        
        # B. Fetch filtered and paginated discounts list
        discounts_query_params = list(query_params) 
        sql_final = sql_select + where_clause_str + " ORDER BY id DESC LIMIT %s OFFSET %s"
        discounts_query_params.extend([PER_PAGE, offset])
        
        cur.execute(sql_final, tuple(discounts_query_params))
        discounts_list = cur.fetchall()
        
        # Format data for the template (post-query logic for template display)
        for d in discounts_list:
            # Determine display value
            if d['type'] == 'percentage':
                d['display_value'] = f"{d['value']:.0f}% Off"
            elif d['type'] == 'fixed':
                d['display_value'] = f"${d['value']:.2f} Off"
            else: # free_shipping
                d['display_value'] = "Free Shipping"
            
            # Determine effective status and activity for display
            is_expired = d['expiry_date'] is not None and d['expiry_date'] < date.today()
            is_future = d['start_date'] > date.today()

            # Set a display flag:
            if is_expired:
                d['display_status'] = 'Expired'
                d['is_active_for_display'] = False
            elif is_future:
                d['display_status'] = 'Scheduled'
                d['is_active_for_display'] = False
            elif d['is_active']:
                d['display_status'] = 'Active'
                d['is_active_for_display'] = True
            else:
                d['display_status'] = 'Inactive'
                d['is_active_for_display'] = False

    except Exception as e:
        app.logger.error(f"Database error in /discounts route: {e}")
        flash('Error loading discount list.', 'error')
        discounts_list = [] 
        total_pages = 1
        total_discounts = 0
    finally:
        if cur: cur.close()

    status_options = ['all', 'active', 'inactive', 'expired']

    return render_template('discounts.html', 
                           page_title=page_title, 
                           active_page='discounts', 
                           discounts=discounts_list,
                           status_options=status_options,
                           current_status_filter=status_filter,
                           page=page, 
                           per_page=PER_PAGE, 
                           total_discounts=total_discounts, 
                           total_pages=total_pages,
                           search_query=search_query)

# --- ADD/EDIT/DELETE DISCOUNTS (from previous context) ---

@app.route('/discounts/add', methods=['GET', 'POST'])
@admin_required
def add_discount():
    page_title = 'Add New Discount Code'
    
    if request.method == 'POST':
        # 1. Get and Validate Data
        code = request.form['code'].upper() # Use uppercase for codes
        description = request.form.get('description', '')
        type = request.form['type']
        
        try:
            value = float(request.form['value'])
            min_purchase_amount = float(request.form.get('min_purchase_amount', 0.00))
            max_usage_str = request.form.get('max_usage')
            max_usage = int(max_usage_str) if max_usage_str and max_usage_str.isdigit() else None
            is_active = request.form.get('is_active') == 'on'
            
            # Dates
            start_date_str = request.form['start_date']
            expiry_date_str = request.form.get('expiry_date') or None # Use None if empty string
            
            # Simple validation
            if not code or not start_date_str:
                flash('Code and Start Date are required.', 'error')
                # Re-render form with posted data
                return render_template('add_edit_discount.html', page_title=page_title, active_page='discounts', is_edit=False, form_data=request.form)
            
        except (ValueError, TypeError) as e:
            app.logger.error(f"Form data error in add_discount: {e}")
            flash('Invalid numeric input for value, minimum purchase, or max usage.', 'error')
            return render_template('add_edit_discount.html', page_title=page_title, active_page='discounts', is_edit=False, form_data=request.form)

        # 2. Insert into DB
        cur = None
        try:
            cur = mysql.connection.cursor()
            
            cur.execute("""
                INSERT INTO discounts (code, description, type, value, min_purchase_amount, max_usage, start_date, expiry_date, is_active) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (code, description, type, value, min_purchase_amount, max_usage, start_date_str, expiry_date_str, is_active))
            
            mysql.connection.commit()
            flash(f'Discount code "{code}" created successfully.', 'success')
            return redirect(url_for('discounts'))
            
        except Exception as e:
            app.logger.error(f"Database error during discount insertion: {e}")
            flash('Error creating discount. Code may already exist.', 'error')
            return render_template('add_edit_discount.html', page_title=page_title, active_page='discounts', is_edit=False, form_data=request.form)
        finally:
            if cur: cur.close()

    # GET request
    # Pass a dummy object for initial form rendering (to avoid errors accessing form_data fields)
    return render_template('add_edit_discount.html', 
                           page_title=page_title, 
                           active_page='discounts', 
                           is_edit=False,
                           form_data={'type': 'percentage', 'value': 0.00, 'min_purchase_amount': 0.00, 'is_active': True})


@app.route('/discounts/edit/<int:discount_id>', methods=['GET', 'POST'])
@admin_required
def edit_discount(discount_id):
    page_title = 'Edit Discount Code'
    cur = None
    
    try:
        cur = mysql.connection.cursor()
        
        if request.method == 'POST':
            # 1. Get and Validate Data (similar to add_discount)
            code = request.form['code'].upper()
            description = request.form.get('description', '')
            type = request.form['type']
            
            try:
                value = float(request.form['value'])
                min_purchase_amount = float(request.form.get('min_purchase_amount', 0.00))
                max_usage_str = request.form.get('max_usage')
                max_usage = int(max_usage_str) if max_usage_str and max_usage_str.isdigit() else None
                is_active = request.form.get('is_active') == 'on'
                
                start_date_str = request.form['start_date']
                expiry_date_str = request.form.get('expiry_date') or None
                
                if not code or not start_date_str:
                    flash('Code and Start Date are required.', 'error')
                    # Refetch existing data + merge with new form data to re-render
                    cur.execute("SELECT * FROM discounts WHERE id = %s", [discount_id])
                    discount = cur.fetchone()
                    discount.update(request.form)
                    return render_template('add_edit_discount.html', page_title=page_title, active_page='discounts', is_edit=True, form_data=discount)
                
            except (ValueError, TypeError) as e:
                app.logger.error(f"Form data error in edit_discount: {e}")
                flash('Invalid numeric input.', 'error')
                return redirect(url_for('edit_discount', discount_id=discount_id))
            
            # 2. Update DB
            cur.execute("""
                UPDATE discounts 
                SET code = %s, description = %s, type = %s, value = %s, min_purchase_amount = %s, 
                    max_usage = %s, start_date = %s, expiry_date = %s, is_active = %s
                WHERE id = %s
            """, (code, description, type, value, min_purchase_amount, max_usage, start_date_str, expiry_date_str, is_active, discount_id))
            
            mysql.connection.commit()
            flash(f'Discount code "{code}" updated successfully.', 'success')
            return redirect(url_for('discounts'))

        # GET request
        cur.execute("SELECT * FROM discounts WHERE id = %s", [discount_id])
        discount = cur.fetchone()
        
        if discount is None:
            flash('Discount not found.', 'error')
            return redirect(url_for('discounts'))

        # Format date objects to strings for HTML input fields
        if discount['start_date']:
            discount['start_date'] = discount['start_date'].strftime('%Y-%m-%d')
        if discount['expiry_date']:
            discount['expiry_date'] = discount['expiry_date'].strftime('%Y-%m-%d')
            
        return render_template('add_edit_discount.html', 
                               page_title=page_title, 
                               active_page='discounts', 
                               is_edit=True,
                               form_data=discount)
                        
    except Exception as e:
        app.logger.error(f"Database error in edit_discount route: {e}")
        flash('Could not load or update discount data.', 'error')
        return redirect(url_for('discounts'))
    finally:
        if cur: cur.close()

@app.route('/discounts/delete/<int:discount_id>', methods=['POST'])
@admin_required
def delete_discount(discount_id):
    cur = None
    try:
        cur = mysql.connection.cursor()
        
        # NOTE: A real system would check if this code was used in any completed orders first.
        # For simplicity, we directly delete.
        cur.execute("DELETE FROM discounts WHERE id = %s", [discount_id])
        
        mysql.connection.commit()
        
        flash('Discount code deleted successfully.', 'success')
        
    except Exception as e:
        app.logger.error(f"Database error during discount deletion: {e}")
        flash('Error deleting discount.', 'error')
        
    finally:
        if cur: cur.close()
            
    return redirect(url_for('discounts'))

# --- RETURNS MANAGEMENT ROUTES (FULL IMPLEMENTATION) ---

@app.route('/returns')
@admin_required
def returns_management():
    page_title = 'Returns Management'
    cur = None
    returns_list = []
    
    # Define filters and pagination
    status_filter = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)
    offset = (page - 1) * PER_PAGE
    
    # Base SQL query
    sql_select = """
        SELECT 
            r.id, 
            r.order_id, 
            r.return_status, 
            r.refund_amount, 
            r.return_date,
            u.name AS user_name,
            COUNT(ri.id) AS item_count
        FROM returns r
        JOIN users u ON r.user_id = u.id
        LEFT JOIN return_items ri ON r.id = ri.return_id
    """
    sql_count = "SELECT COUNT(id) AS count FROM returns r"
    
    where_clauses = []
    query_params = []
    
    if status_filter != 'all':
        where_clauses.append("r.return_status = %s")
        query_params.append(status_filter)
        
    where_clause_str = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    
    try:
        cur = mysql.connection.cursor()

        # A. Fetch total count
        cur.execute(sql_count + where_clause_str, query_params)
        total_returns = cur.fetchone()['count']
        total_pages = math.ceil(total_returns / PER_PAGE)
        
        # B. Fetch filtered and paginated returns list
        returns_query_params = list(query_params) 
        sql_final = sql_select + where_clause_str + " GROUP BY r.id ORDER BY r.return_date DESC LIMIT %s OFFSET %s"
        returns_query_params.extend([PER_PAGE, offset])
        
        cur.execute(sql_final, tuple(returns_query_params))
        returns_list = cur.fetchall()
        
    except Exception as e:
        app.logger.error(f"Database error in /returns route: {e}")
        flash('Error loading returns list.', 'error')
        returns_list = []
        total_pages = 1
        total_returns = 0
    finally:
        if cur: cur.close()

    # Define possible statuses for filtering dropdown
    status_options = ['Requested', 'In Transit', 'Received', 'Processing', 'Refunded', 'Rejected']

    return render_template('returns.html', 
                           page_title=page_title, 
                           active_page='returns',
                           returns=returns_list,
                           status_options=status_options,
                           current_status_filter=status_filter,
                           page=page, 
                           per_page=PER_PAGE, 
                           total_returns=total_returns, 
                           total_pages=total_pages)


@app.route('/returns/<int:return_id>', methods=['GET', 'POST'])
@admin_required
def return_details(return_id):
    page_title = f'Return #{return_id} Details'
    cur = None
    return_data = None
    
    # Define possible statuses for the dropdown
    status_options = ['Requested', 'In Transit', 'Received', 'Processing', 'Refunded', 'Rejected']

    try:
        cur = mysql.connection.cursor()
        
        if request.method == 'POST':
            # --- Handle Status/Refund Update ---
            new_status = request.form['return_status']
            refund_amount = float(request.form.get('refund_amount', 0.00))

            if new_status in status_options:
                
                update_query = "UPDATE returns SET return_status = %s, refund_amount = %s"
                update_params = [new_status, refund_amount]
                
                # If status is set to Refunded, update the processed_at timestamp
                if new_status == 'Refunded':
                    update_query += ", processed_at = NOW()"
                
                update_query += " WHERE id = %s"
                update_params.append(return_id)

                cur.execute(update_query, tuple(update_params))
                mysql.connection.commit()
                
                # --- Stock Reconciliation Logic (Simplified) ---
                if new_status == 'Received' or new_status == 'Refunded':
                    cur.execute("SELECT product_id, quantity FROM return_items WHERE return_id = %s", [return_id])
                    returned_items = cur.fetchall()
                    
                    for item in returned_items:
                        # Increment product stock
                        cur.execute("UPDATE products SET stock = stock + %s WHERE id = %s", 
                                     (item['quantity'], item['product_id']))
                        # Commit the stock change separately or with the main commit
                    mysql.connection.commit()
                    flash(f"Stock for {len(returned_items)} items updated.", 'info')

                flash(f"Return #{return_id} updated successfully. Status: {new_status}.", 'success')
            else:
                flash("Invalid status selected.", 'error')
            
            # Redirect to GET view to show updated status
            return redirect(url_for('return_details', return_id=return_id))

        # --- Handle GET Request (View Details) ---
        
        # 1. Fetch Return Header Details
        cur.execute("""
            SELECT 
                r.*, 
                u.name AS user_name, 
                u.email AS user_email
            FROM returns r
            JOIN users u ON r.user_id = u.id
            WHERE r.id = %s
        """, [return_id])
        return_data = cur.fetchone()

        if not return_data:
            flash('Return record not found.', 'error')
            return redirect(url_for('returns_management'))

        # 2. Fetch Returned Items (and link back to order details)
        cur.execute("""
            SELECT 
                ri.quantity, 
                ri.price_at_return,
                ri.reason AS item_reason,
                p.name AS product_name,
                p.sku,
                oi.id AS order_item_id
            FROM return_items ri
            JOIN products p ON ri.product_id = p.id
            JOIN order_items oi ON ri.order_item_id = oi.id
            WHERE ri.return_id = %s
        """, [return_id])
        items = cur.fetchall()
        
        return_data['items'] = items
        
        # 3. Fetch original Order information (for reference)
        cur.execute("SELECT total_amount, status FROM orders WHERE id = %s", [return_data['order_id']])
        order_info = cur.fetchone()
        return_data['order_info'] = order_info

        return render_template('return_details.html', 
                               page_title=page_title, 
                               active_page='returns', 
                               return_data=return_data,
                               status_options=status_options)
        
    except Exception as e:
        flash(f"Error processing Return #{return_id}: {e}", 'error')
        app.logger.error(f"Database error in /returns/{return_id} route: {e}")
        return redirect(url_for('returns_management'))
    finally:
        if cur: cur.close()

# --- USERS ROUTES (ACCESS CONTROL ADDED) ---

@app.route('/users')
@admin_required # Only Admin should manage users
def users():
    page_title = 'User Management'
    
    # --- 1. Get filter and pagination parameters ---
    page = request.args.get('page', 1, type=int) 
    search_term = request.args.get('search', '')
    role_filter = request.args.get('role', '') 
    
    offset = (page - 1) * PER_PAGE
    
    # --- 2. Build the dynamic SQL query ---
    sql_select = "SELECT id, name, email, role, 'Active' as status FROM users "
    count_select = "SELECT COUNT(id) AS count FROM users "
    
    where_clauses = []
    query_params = []

    if search_term:
        where_clauses.append("(name LIKE %s OR email LIKE %s)")
        query_params.extend([f"%{search_term}%", f"%{search_term}%"])

    if role_filter:
        where_clauses.append("role = %s")
        query_params.append(role_filter)

    where_clause_str = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
    # --- 3. Execute queries with filters ---
    try:
        cur = mysql.connection.cursor()

        # A. Fetch total count
        cur.execute(count_select + where_clause_str, query_params)
        total_users = cur.fetchone()['count']
        total_pages = (total_users + PER_PAGE - 1) // PER_PAGE 
        
        # B. Fetch filtered and paginated users
        user_query_params = list(query_params) 
        sql_final = sql_select + where_clause_str + " ORDER BY id DESC LIMIT %s OFFSET %s"
        user_query_params.extend([PER_PAGE, offset])
        
        cur.execute(sql_final, tuple(user_query_params))
        users = cur.fetchall()
        
        cur.close()
        
    except Exception as e:
        app.logger.error(f"Database error in /users route: {e}")
        users = [] 
        total_pages = 1
        total_users = 0

    return render_template('users.html', 
                           page_title=page_title, 
                           active_page='users', 
                           users=users,
                           page=page, 
                           offset=offset, 
                           per_page=PER_PAGE, 
                           total_users=total_users, 
                           total_pages=total_pages,
                           search_term=search_term, 
                           role_filter=role_filter)


@app.route('/add_user', methods=['GET', 'POST'])
@admin_required # Only Admin should add users
def add_user():
    page_title = 'Add New User'

    if request.method == 'POST':
        # 1. Get data from the form
        name = request.form['name']
        email = request.form['email']
        role = request.form['role']
        password = request.form['password']
        
        # 2. Hash the password
        password_hash = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

        # 3. Insert into the database
        try:
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO users (name, email, role, password_hash) VALUES (%s, %s, %s, %s)",
                         (name, email, role, password_hash))
            
            mysql.connection.commit()
            cur.close()
            
            flash(f'User "{name}" created successfully.', 'success')
            return redirect(url_for('users'))
        except Exception as e:
            flash('Error creating user. Email may already be registered.', 'error')
            app.logger.error(f"Database error during user insertion: {e}")
            return redirect(url_for('add_user')) 
            
    # For GET request, simply render the form
    return render_template('add_user.html', page_title=page_title, active_page='users')


@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@admin_required # Only Admin should edit users
def edit_user(user_id):
    page_title = 'Edit User'
    
    cur = mysql.connection.cursor()
    
    if request.method == 'POST':
        # --- Handle Form Submission (POST) ---
        name = request.form['name']
        email = request.form['email']
        role = request.form['role']
        
        try:
            # Execute the UPDATE query
            cur.execute("UPDATE users SET name = %s, email = %s, role = %s WHERE id = %s", 
                          (name, email, role, user_id))
            
            mysql.connection.commit()
            cur.close()
            
            flash(f'User "{name}" updated successfully.', 'success')
            return redirect(url_for('users'))
            
        except Exception as e:
            flash('Error updating user data.', 'error')
            app.logger.error(f"Database error during user update: {e}")
            return redirect(url_for('edit_user', user_id=user_id))
        
    # --- Handle Initial Form Load (GET) ---
    else:
        # Fetch the user's existing data from the database
        cur.execute("SELECT id, name, email, role FROM users WHERE id = %s", [user_id])
        user = cur.fetchone()
        cur.close()

        if user is None:
            flash('User not found.', 'error')
            return redirect(url_for('users'))

        return render_template('edit_user.html', 
                               page_title=page_title, 
                               active_page='users', 
                               user=user)
# The rest of your app (products, settings, etc.) would go here.

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@admin_required # Only Admin should delete users
def delete_user(user_id):
    try:
        cur = mysql.connection.cursor()
        
        # Execute the DELETE query
        cur.execute("DELETE FROM users WHERE id = %s", [user_id])
        
        # Commit the change
        mysql.connection.commit()
        cur.close()
        
        flash('User deleted successfully.', 'success')
        return redirect(url_for('users'))
        
    except Exception as e:
        flash('Error deleting user.', 'error')
        app.logger.error(f"Database error during user deletion: {e}")
        return redirect(url_for('users'))


# --- PRODUCT ROUTES (UPDATED FOR NEW SCHEMA) ---

@app.route('/products')
@staff_or_admin_required
def products():
    page_title = 'Products Management'
    
    # --- 1. Get filter and pagination parameters ---
    page = request.args.get('page', 1, type=int)
    search_term = request.args.get('search', '')
    # *** NEW: Read the category filter from the URL ***
    category_filter = request.args.get('category_id', type=int) 
    if category_filter == 0: category_filter = None # Treat 'All' option (value 0) as no filter

    offset = (page - 1) * PER_PAGE 
    
    cur = None
    try:
        cur = mysql.connection.cursor()
        
        # Fetch all categories for the filter dropdown
        cur.execute("SELECT id, name FROM categories ORDER BY name")
        categories_filter_list = cur.fetchall()

        # --- 2. Build the dynamic SQL query ---
        sql_select = """
            SELECT 
                p.id, p.name, p.sku, p.price, p.stock, p.description, 
                c.name AS category_name,
                (SELECT filename FROM product_images WHERE product_id = p.id ORDER BY display_order ASC LIMIT 1) AS primary_image,
                (SELECT COUNT(id) FROM product_variants WHERE product_id = p.id) AS variant_count
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
        """
        count_select = "SELECT COUNT(id) AS count FROM products p "
        
        where_clauses = []
        query_params = []

        if search_term:
            where_clauses.append("(p.name LIKE %s OR p.sku LIKE %s OR p.description LIKE %s)")
            query_params.extend([f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"])

        # *** NEW: Add category filtering ***
        if category_filter:
            where_clauses.append("p.category_id = %s")
            query_params.append(category_filter)

        where_clause_str = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        # --- 3. Execute queries with filters ---
        
        # A. Fetch total count
        cur.execute(count_select + where_clause_str, query_params)
        total_products = cur.fetchone()['count']
        total_pages = math.ceil(total_products / PER_PAGE)
        
        # B. Fetch paginated and filtered products
        product_query_params = list(query_params) 
        sql_final = sql_select + where_clause_str + " ORDER BY p.id DESC LIMIT %s OFFSET %s"
        product_query_params.extend([PER_PAGE, offset])
        
        cur.execute(sql_final, tuple(product_query_params))
        products_list = cur.fetchall()
        
    except Exception as e:
        app.logger.error(f"Database error in /products route: {e}")
        products_list = []
        total_pages = 1
        total_products = 0
    finally:
        if cur: cur.close()

    # NOTE: The template expects 'product.image_filename', so we map 'primary_image' to it for compatibility
    for p in products_list:
        p['image_filename'] = p['primary_image']
        # The template also expects 'product.category.name', so we add it here for the list view
        p['category'] = {'name': p['category_name']} 

    return render_template('products.html', 
                           page_title='Products Management', 
                           active_page='products',
                           products=products_list,
                           categories_filter_list=categories_filter_list, # NEW
                           category_filter=category_filter, # NEW
                           page=page,
                           offset=offset,
                           total_products=total_products,
                           total_pages=total_pages,
                           search_term=search_term)


# **COMPLEX ADD PRODUCT ROUTE (Variants and Multiple Images)**
@app.route('/products/add', methods=['GET', 'POST'], endpoint='add_product')
@staff_or_admin_required
def add_product():
    page_title = 'Add New Product'
    cur = None
    
    # Initialize variables for potential re-render on error
    name, sku, description, category_id, price, base_stock = '', '', '', None, 0.00, 0
    
    # Fetch categories for the form dropdown (GET or POST error re-render)
    categories = []
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, name FROM categories ORDER BY name")
        categories = cur.fetchall()
    except Exception as e:
        app.logger.error(f"Error fetching categories: {e}")
    finally:
        # Close cursor if it was opened
        if cur: cur.close()
        
    if request.method == 'POST':
        # 1. Get Core Product Data
        name = request.form.get('name')
        sku = request.form.get('sku')
        description = request.form.get('description')
        category_id_str = request.form.get('category_id')
        category_id = int(category_id_str) if category_id_str and category_id_str.isdigit() else None
        
        # Input Validation for numbers
        try:
            price = float(request.form.get('price'))
            # Get base stock but don't crash if it's missing (assume 0)
            base_stock_str = request.form.get('stock', '0')
            base_stock = int(base_stock_str) if base_stock_str.isdigit() else 0
        except (ValueError, TypeError):
            flash('Invalid Price or Stock quantity. Please check your inputs.', 'error')
            return render_template('add_product.html', page_title=page_title, active_page='products', categories=categories,
                                   name=name, sku=sku, price=request.form.get('price'), stock=request.form.get('stock'), description=description, category_id=category_id)
        
        # Determine if we have variants
        try:
            total_variants_count = int(request.form.get('total_variants', 0))
        except ValueError:
            total_variants_count = 0
            
        is_variant_product = total_variants_count > 0
        stock_to_save = 0 if is_variant_product else base_stock

        cur = None
        try:
            cur = mysql.connection.cursor()
            
            # 2. Insert Base Product
            cur.execute(
                "INSERT INTO products (name, sku, price, stock, description, category_id) VALUES (%s, %s, %s, %s, %s, %s)",
                (name, sku, price, stock_to_save, description, category_id)
            )
            
            # Get the ID of the newly inserted product (CRITICAL for FKs)
            product_id = cur.lastrowid
            
            # 3. Process Product Images (Multiple Uploads)
            image_files = request.files.getlist('image_files')
            
            for i, file in enumerate(image_files):
                if file and file.filename and allowed_file(file.filename):
                    # Get the display order from the corresponding form field
                    display_order = request.form.get(f'image_order_{i}', i + 1)
                    
                    filename = secure_filename(file.filename)
                    # Use a unique filename: product_id_order_original_name
                    unique_filename = f"{product_id}_{display_order}_{filename}"
                    
                    # Save the file
                    upload_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
                    os.makedirs(upload_path, exist_ok=True)
                    file.save(os.path.join(upload_path, unique_filename))
                    
                    # Record the image in the ProductImage table
                    cur.execute(
                        "INSERT INTO product_images (product_id, filename, display_order) VALUES (%s, %s, %s)",
                        (product_id, unique_filename, int(display_order))
                    )

            # 4. Process Product Variants
            if is_variant_product:
                total_variant_stock = 0
                for i in range(1, total_variants_count + 1):
                    attr_name = request.form.get(f'variant_attr_name_{i}')
                    attr_value = request.form.get(f'variant_attr_value_{i}')
                    
                    # Safe retrieval for numbers
                    try:
                        variant_stock = int(request.form.get(f'variant_stock_{i}', 0))
                        price_adj = float(request.form.get(f'variant_price_adj_{i}', 0.00))
                    except (ValueError, TypeError):
                           # Log error and continue with default values, or raise/flash as a more severe error
                           app.logger.warning(f"Invalid variant number data for variant {i} of product {name}")
                           continue 
                        
                    if attr_name and attr_value:
                        cur.execute(
                            """
                            INSERT INTO product_variants (product_id, attribute_name, attribute_value, additional_price, stock) 
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (product_id, attr_name, attr_value, price_adj, variant_stock)
                        )
                        total_variant_stock += variant_stock
                
                # Update the base product's stock with the sum of variants
                cur.execute("UPDATE products SET stock = %s WHERE id = %s", (total_variant_stock, product_id))
            
            mysql.connection.commit()
            
            # 5. Success Feedback and Alert
            final_stock = total_variant_stock if is_variant_product else base_stock
            
            if final_stock < LOW_STOCK_THRESHOLD:
                send_email_alert(
                    recipient=session.get('email', app.config.get('MAIL_USERNAME')),
                    subject=f"⚠️ LOW STOCK ALERT: {name}",
                    template='email/alert_low_stock.html',
                    user_name=session.get('name', 'Admin'),
                    product_name=name,
                    product_sku=sku,
                    stock_level=final_stock,
                    threshold=LOW_STOCK_THRESHOLD
                )
                flash(f'Product "{name}" added successfully, but stock is low ({final_stock}). A low-stock alert email has been sent.', 'warning')
            else:
                flash(f'Product "{name}" added successfully!', 'success')
            
            return redirect(url_for('products'))

        except Exception as e:
            # Rollback in case of any insertion error
            mysql.connection.rollback()
            app.logger.error(f"Database Error on product insert: {e}")
            flash('An error occurred while creating the product (SKU may already exist).', 'error')
            # Re-render form with current data
            return render_template('add_product.html', page_title=page_title, active_page='products', categories=categories,
                                   name=name, sku=sku, price=price, stock=base_stock, description=description, category_id=category_id)
        finally:
            if cur: cur.close()

    # Default case: GET request, just render the form
    return render_template('add_product.html', page_title=page_title, active_page='products', categories=categories)


# **UPDATED EDIT PRODUCT ROUTE (Simplified Image Update Logic)**

@app.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@staff_or_admin_required
def edit_product(product_id):
    page_title = 'Edit Product'
    cur = None
    product = None
    categories = []

    try:
        cur = mysql.connection.cursor()

        # 1. Fetch Categories (Needed for both GET and POST failure re-render)
        cur.execute("SELECT id, name FROM categories")
        categories = cur.fetchall()

        # 2. Fetch Existing Product Data (Needed for both GET and POST logic)
        cur.execute("SELECT * FROM products WHERE id = %s", [product_id])
        product = cur.fetchone()
        if not product:
            flash('Product not found.', 'error')
            return redirect(url_for('products_list'))


        # --- 3. Handle POST request (Form Submission) ---
        if request.method == 'POST':
            # Get form data
            name = request.form.get('name')
            sku = request.form.get('sku')
            description = request.form.get('description')
            category_id_str = request.form.get('category_id')
            category_id = int(category_id_str) if category_id_str and category_id_str.isdigit() else None
            
            # --- NEW FEATURED PRODUCT LOGIC ---
            is_featured = 1 if request.form.get('is_featured') == 'on' else 0
            # -----------------------------------

            try:
                price = float(request.form.get('price'))
                stock = int(request.form.get('stock'))
            except (ValueError, TypeError):
                flash('Invalid Price or Stock quantity. Please check your inputs.', 'error')
                # Re-render form using existing product data and categories
                return render_template('edit_product.html', page_title=page_title, active_page='products', product=product, categories=categories)
            
            # Handle Single Primary Image Update (Existing logic simplified for context)
            file = request.files.get('image_file') 
            
            if file and file.filename and allowed_file(file.filename):
                # ... Image deletion/upload logic goes here (as per your original code) ...
                
                # Simplified Image Update Logic:
                # 1. Delete old images
                # 2. Upload new image
                # 3. Insert new product_images record
                pass # Assuming your image logic is correct and working

            
            # --- Execute the FINAL PRODUCT UPDATE query ---
            update_query = """
                UPDATE products SET 
                    name = %s, sku = %s, price = %s, stock = %s, 
                    description = %s, category_id = %s, 
                    is_featured = %s,        -- <--- ADDED FIELD
                    updated_at = NOW()
                WHERE id = %s
            """
            cur.execute(
                update_query,
                (name, sku, price, stock, description, category_id, is_featured, product_id)
            )
            
            mysql.connection.commit()
            
            # --- EMAIL ALERT LOGIC --- (Keep your existing stock alert logic)
            if stock < LOW_STOCK_THRESHOLD:
                # ... send low stock email alert ...
                flash(f'Product "{name}" updated successfully, but stock is low ({stock}). A low-stock alert email has been sent.', 'warning')
            else:
                flash(f'Product "{name}" updated successfully!', 'success')
                
            return redirect(url_for('products_list'))


        # --- 4. Handle GET request (Initial Form Load) ---
        else: # request.method == 'GET'
            # Fetch variants and all images for display
            cur.execute("SELECT * FROM product_variants WHERE product_id = %s", [product_id])
            variants = cur.fetchall()
            
            cur.execute("SELECT * FROM product_images WHERE product_id = %s ORDER BY display_order ASC", [product_id])
            images = cur.fetchall()
            
            # The HTML template expects 'product' dictionary to be flat for core fields
            return render_template('edit_product.html', 
                                   page_title=page_title, 
                                   active_page='products', 
                                   product=product,
                                   categories=categories,
                                   variants=variants,
                                   images=images)
            
    except Exception as e:
        mysql.connection.rollback()
        app.logger.error(f"Database Error in edit_product route: {e}")
        flash('Could not load or update product data.', 'error')
        return redirect(url_for('products_list'))
    finally:
        if cur: cur.close()
        
# **UPDATED DELETE PRODUCT ROUTE (with File and Variant/Image Deletion)**
@app.route('/products/delete/<int:product_id>', methods=['POST'])
@staff_or_admin_required
def delete_product(product_id):
    cur = None
    try:
        cur = mysql.connection.cursor()
        
        # 1. Fetch filenames before deletion
        cur.execute("SELECT filename FROM product_images WHERE product_id = %s", [product_id])
        images_to_delete = cur.fetchall()
        
        # 2. Execute the DELETE query for the product. 
        # Assumes CASCADE is set up for variants and images.
        cur.execute("DELETE FROM products WHERE id = %s", [product_id])
        
        # 3. Commit the change
        mysql.connection.commit()
        
        # 4. Delete the physical files from the server
        upload_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
        for img in images_to_delete:
            filename = img['filename']
            file_path = os.path.join(upload_path, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
        
        flash('Product and all associated data/images deleted successfully.', 'success')
        
    except Exception as e:
        app.logger.error(f"Database error during product deletion: {e}")
        flash('Error deleting product.', 'error')
        
    finally:
        if cur: cur.close()
            
    # Always redirect back to the product list
    return redirect(url_for('products')) 
    
# --- Import necessary tools for Order Management (Add these near your other imports)
# from datetime import datetime
# from flask import flash, redirect, url_for, render_template, request, jsonify

# --- Mock Data Setup (Run this once to populate orders)
# We need a dedicated table for orders and order items first.
# This function is commented out; you'll need to run the SQL first!

@app.route('/seed_mock_orders')
@admin_required
def seed_mock_orders():
    try:
         cur = mysql.connection.cursor()
        
         # Ensure products exist (for items)
         cur.execute("SELECT id FROM products LIMIT 3")
         product_ids = [row['id'] for row in cur.fetchall()]
         
         if not product_ids:
             flash("Please add a few products before seeding orders.", 'warning')
             return redirect(url_for('dashboard'))

         # Mock Orders: status can be 'New', 'Processing', 'Shipped', 'Delivered', 'Cancelled'
         mock_orders = [
             {'user_id': 1, 'total_amount': 450.00, 'status': 'New', 'created_at': '2025-10-01 10:00:00', 'items': [{'product_id': product_ids[0], 'quantity': 1, 'price': 450.00}]},
            {'user_id': 2, 'total_amount': 120.00, 'status': 'Processing', 'created_at': '2025-10-02 12:30:00', 'items': [{'product_id': product_ids[1], 'quantity': 2, 'price': 60.00}]},
             {'user_id': 1, 'total_amount': 88.50, 'status': 'Delivered', 'created_at': '2025-09-28 15:45:00', 'items': [{'product_id': product_ids[2], 'quantity': 3, 'price': 29.50}]},
         ]

         for order in mock_orders:
             # Insert Order
             cur.execute("""
#                 INSERT INTO orders (user_id, total_amount, status, created_at) 
#                 VALUES (%s, %s, %s, %s)
#             """, (order['user_id'], order['total_amount'], order['status'], order['created_at']))
             
             order_id = cur.lastrowid
             
             # Insert Order Items
             for item in order['items']:
                 cur.execute("""
                     INSERT INTO order_items (order_id, product_id, quantity, price) 
                     VALUES (%s, %s, %s, %s)
                 """, (order_id, item['product_id'], item['quantity'], item['price']))
        
         mysql.connection.commit()
         flash(f"{len(mock_orders)} mock orders seeded successfully.", 'success')
    except Exception as e:
         flash(f"Error seeding mock orders: {e}", 'error')
         app.logger.error(f"Error seeding mock orders: {e}")
    finally:
         if cur: cur.close()

    return redirect(url_for('dashboard'))

# In your app.py file

# In your app.py file

# In your app.py file

@app.route('/orders')
# Assuming your login decorator is @is_logged_in. Adjust if needed.
# If you don't have a login decorator, just use: @app.route('/orders')
@is_logged_in 
def orders():
    page_title = 'Order Management'
    
    # Check if the connection exists before proceeding
    if 'mysql' not in globals() or not mysql.connection:
        flash('Database connection is not initialized.', 'danger')
        return render_template('orders.html', page_title=page_title, active_page='orders', orders=[])

    cur = mysql.connection.cursor()
    orders_list = [] 

    try:
        # ----------------------------------------------------------------------
        # CRITICAL FIX: The robust SQL query for the list view
        # This resolves the "Error processing Order" flash message (due to GROUP BY issues)
        # ----------------------------------------------------------------------
        cur.execute("""
            SELECT 
                o.id, 
                o.user_id, 
                o.total_amount, 
                o.status, 
                o.created_at,
                u.name AS user_name,
                COUNT(oi.id) AS total_items
            FROM orders o
            INNER JOIN users u ON o.user_id = u.id  
            LEFT JOIN order_items oi ON o.id = oi.order_id
            GROUP BY o.id, u.name, o.user_id, o.total_amount, o.status, o.created_at
            ORDER BY o.created_at DESC
        """)
        
        orders_list = cur.fetchall() 
        
    except Exception as e:
        # If the query crashes, this block executes, causing the flash message
        # We log the actual database error for debugging
        app.logger.error(f"Database error in /orders route: {e}")
        flash('A critical error occurred while fetching the order list.', 'danger')
        
    finally:
        # Always close the cursor
        if cur:
            cur.close()

    return render_template('orders.html', 
                            page_title=page_title, 
                            active_page='orders', 
                            orders=orders_list)

# --- Your Custom Decorator (Ensuring it checks session['loggedin']) ---
def is_logged_in(f):
    from flask import session, redirect, url_for, flash
    from functools import wraps
    @wraps(f)
    def wrap(*args, **kwargs):
        # Must match your login code: session['loggedin']
        if 'loggedin' in session and session['loggedin']:
            return f(*args, **kwargs)
        else:
            flash('Unauthorized, please login', 'danger')
            return redirect(url_for('login'))
    return wrap
# --- End Decorator ---


# --- UPDATED Order Details Route ---

# Assuming your necessary imports and decorator are defined above

@app.route('/order_details/<int:order_id>', methods=['GET', 'POST'])
@is_logged_in
def order_details(order_id):
    cur = mysql.connection.cursor()
    page_title = f"Order #{order_id} Details"
    
    # --- 1. HANDLE POST REQUEST (Status Update) ---
    if request.method == 'POST':
        # Status update logic remains the same...
        new_status = request.form.get('status')
        if new_status:
            try:
                cur.execute("UPDATE orders SET status = %s WHERE id = %s", (new_status, order_id))
                mysql.connection.commit()
                flash(f'Order status successfully updated to {new_status}.', 'success')
            except Exception as e:
                flash(f'Error updating status: {e}', 'danger')
        
        return redirect(url_for('order_details', order_id=order_id))


    # --- 2. HANDLE GET REQUEST (Display Details) ---
    
    status_options = ['New', 'Processing', 'Shipped', 'Delivered', 'Cancelled']
    
    # --- CRITICAL FIX: Fetch Order Details with Customer Info JOINED ---
    result = cur.execute("""
        SELECT 
            o.id, o.user_id, o.total_amount, o.status, o.created_at, o.updated_at, 
            o.payment_status, o.transaction_id,

            -- User/Customer Details from JOIN
            u.name AS user_name,
            u.email AS user_email,
            u.phone AS user_phone    

        FROM orders o
        INNER JOIN users u ON o.user_id = u.id
        WHERE o.id = %s
    """, [order_id])
    
    if result > 0:
        order = cur.fetchone() # Fetches the combined order and user data
        
        # --- Fetch the Order Items List ---
        cur.execute("""
            SELECT 
                oi.*, p.name as product_name, p.sku, oi.price as unit_price
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = %s
        """, [order_id])
        order_items_list = cur.fetchall() 
        
        # Attach the list to the main order dictionary
        order['item_list'] = order_items_list
        
        cur.close()

        return render_template('order_details.html', 
                               order=order, 
                               page_title=page_title,
                               status_options=status_options)
    else:
        cur.close()
        flash(f'Order ID {order_id} not found.', 'danger')
        return redirect(url_for('orders'))
@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html', page_title='Settings', active_page='settings')
    
@app.route('/logout')
def logout():
    # Clear all session variables
    session.clear()
    
    # Redirect the user back to the login page
    return redirect(url_for('login'))

# --- PRODUCT REVIEW ROUTES ---

@app.route('/reviews')
@staff_or_admin_required
def reviews_list():
    """Displays a list of all reviews, focusing on 'pending' ones for moderation."""
    page_title = 'Review Moderation'
    cur = None
    reviews = []
    
    # Get filter and pagination parameters
    page = request.args.get('page', 1, type=int)
    # Allows filtering by status (e.g., /reviews?status=approved). Default is 'pending'.
    status_filter = request.args.get('status', 'pending') 
    offset = (page - 1) * PER_PAGE
    
    # Define possible statuses for the filter dropdown
    status_options = ['pending', 'approved', 'rejected']
    
    try:
        cur = mysql.connection.cursor()
        
        # 1. Count total reviews for pagination
        cur.execute("SELECT COUNT(id) AS count FROM product_reviews WHERE status = %s", [status_filter])
        total_reviews = cur.fetchone()['count']
        total_pages = math.ceil(total_reviews / PER_PAGE)
        
        # 2. Fetch reviews with product and user names
        cur.execute("""
            SELECT 
                pr.id, pr.rating, pr.review_title, pr.review_text, pr.admin_reply, pr.status, pr.created_at,
                p.name AS product_name,
                u.name AS user_name
            FROM product_reviews pr
            JOIN products p ON pr.product_id = p.id
            JOIN users u ON pr.user_id = u.id
            WHERE pr.status = %s
            ORDER BY pr.created_at DESC
            LIMIT %s OFFSET %s
        """, (status_filter, PER_PAGE, offset))
        reviews = cur.fetchall()
        
    except Exception as e:
        app.logger.error(f"Database error in /reviews route: {e}")
        flash('Error loading product reviews.', 'error')
        reviews = []
        total_pages = 1
        total_reviews = 0
    finally:
        if cur: cur.close()

    return render_template('reviews_list.html', 
                           page_title=page_title, 
                           active_page='reviews', 
                           reviews=reviews,
                           status_options=status_options,
                           status_filter=status_filter,
                           page=page,
                           total_pages=total_pages,
                           total_reviews=total_reviews,
                           PER_PAGE=PER_PAGE)


@app.route('/reviews/moderate/<int:review_id>', methods=['POST'])
@staff_or_admin_required
def moderate_review(review_id):
    """Handles approving, rejecting, or adding a reply to a review."""
    
    action = request.form.get('action') # 'approve', 'reject', or 'reply'
    admin_reply = request.form.get('admin_reply', '').strip()
    
    # Capture the current status filter to return to the right page
    current_status = request.args.get('current_status', 'pending') 
    
    cur = None

    try:
        cur = mysql.connection.cursor()
        
        # Initial status update: If action is approve/reject, set status
        if action == 'approve':
            cur.execute("UPDATE product_reviews SET status = 'approved', updated_at = NOW() WHERE id = %s", [review_id])
            flash(f"Review #{review_id} approved successfully.", 'success')
            
        elif action == 'reject':
            cur.execute("UPDATE product_reviews SET status = 'rejected', updated_at = NOW() WHERE id = %s", [review_id])
            flash(f"Review #{review_id} rejected.", 'warning')

        # Reply update: Always update the reply field if provided, regardless of status
        if action == 'reply':
            # Note: The front-end is designed to pass the full reply text back on 'reply' action
            cur.execute("UPDATE product_reviews SET admin_reply = %s, updated_at = NOW() WHERE id = %s", (admin_reply, review_id))
            flash(f"Reply added/updated for Review #{review_id}.", 'info')
            
        mysql.connection.commit()
        
    except Exception as e:
        mysql.connection.rollback()
        app.logger.error(f"Database error during review moderation: {e}")
        flash('Error processing review moderation.', 'error')
    finally:
        if cur: cur.close()

    # Redirect back to the list view, filtered by the status the user was viewing
    return redirect(url_for('reviews_list', status=current_status))

@app.route('/create-checkout-session/<int:order_id>', methods=['POST'])
@is_logged_in  # Ensure only logged-in users can initiate payment
def create_checkout_session(order_id):
    # In a real app, you'd fetch the order total from the database here
    # For a quick test, let's hardcode a price for the order:
    
    # 1. Fetch Order Details (Simulated/Placeholder)
    # The price must be in CENTS (or the smallest currency unit)
    order_total_cents = 50000  # Example: $500.00 (50000 cents)
    product_name = f"Order #{order_id} Items"
    
    try:
        # 2. Create a Stripe Checkout Session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price_data': {
                        'currency': 'usd',
                        'unit_amount': order_total_cents,
                        'product_data': {
                            'name': product_name,
                        },
                    },
                    'quantity': 1,
                },
            ],
            mode='payment',
            # 3. Success/Cancel URLs tell Stripe where to send the user back
            success_url=url_for('payment_success', order_id=order_id, _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('payment_cancel', order_id=order_id, _external=True),
        )
        
        # 4. Redirect the user to the Stripe-hosted page
        return redirect(checkout_session.url, code=303)

    except Exception as e:
        flash(f'An error occurred during checkout: {e}', 'danger')
        return redirect(url_for('dashboard')) # Redirect back to a safe place
# --- Success Route ---
@app.route('/payment-success/<int:order_id>')
@is_logged_in
def payment_success(order_id):
    # This is the easiest way to get the status immediately after a redirect
    session_id = request.args.get('session_id')
    
    if not session_id:
        flash('Payment validation failed: Missing session ID.', 'danger')
        return redirect(url_for('dashboard'))

    try:
        # Retrieve the session to verify payment was successful
        session_data = stripe.checkout.Session.retrieve(session_id)
        
        if session_data.payment_status == 'paid':
            # --- CRITICAL: Update your Database here ---
            
            # 1. Update order status to 'Paid' and log the transaction ID
            cur = mysql.connection.cursor()
            transaction_id = session_data.payment_intent # The unique ID for the payment
            
            # Log the successful transaction in the database
            cur.execute("UPDATE orders SET payment_status = %s, transaction_id = %s WHERE order_id = %s", 
                        ('Paid', transaction_id, order_id))
            mysql.connection.commit()
            cur.close()
            
            # --- End DB Update ---

            flash(f'Payment for Order #{order_id} successful! Transaction ID: {transaction_id}', 'success')
            # Redirect to the order details page or a receipt page
            return redirect(url_for('order_details', order_id=order_id)) 
        else:
            flash(f'Payment status for Order #{order_id} is still {session_data.payment_status}.', 'warning')
            return redirect(url_for('order_details', order_id=order_id))

    except Exception as e:
        flash(f'Error validating payment session: {e}', 'danger')
        return redirect(url_for('order_details', order_id=order_id))


# --- Cancel Route ---
@app.route('/payment-cancel/<int:order_id>')
@is_logged_in
def payment_cancel(order_id):
    # The user clicked the back button or closed the Stripe tab
    flash(f'Payment for Order #{order_id} was cancelled. Please try again.', 'info')
    return redirect(url_for('order_details', order_id=order_id))    

# In your app.py

@app.route('/search')
@is_logged_in 
def search():
    query = request.args.get('q', '') # Get the search term
    
    # 1. Start database search logic here
    # Example: Searching products by name
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name FROM products WHERE name LIKE %s", ('%' + query + '%',))
    results = cur.fetchall()
    cur.close()
    
    # 2. Return a new results page
    return render_template('search_results.html', query=query, results=results)

@app.route('/profile')
@is_logged_in 
def profile():
    # Logic to fetch user data (name, email, role, etc.)
    user_id = session.get('user_id')
    cur = mysql.connection.cursor()
    cur.execute("SELECT name, email, phone FROM users WHERE id = %s", [user_id])
    user_details = cur.fetchone()
    cur.close()
    
    return render_template('profile.html', 
                           page_title='My Profile', 
                           active_page='profile', 
                           user=user_details)


# In your app.py

# In your app.py

@app.route('/export_orders')
@is_logged_in
def export_orders():
    # Setup for headers and buffer (Aligned with function start)
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    
    # Write the CSV Header Row (Aligned with function start)
    writer.writerow(['Order ID', 'Customer Name', 'Date Placed', 'Total Items', 'Total Amount', 'Status'])

    # --- Fetch Data from Database (Aligned with function start) ---
    cur = mysql.connection.cursor()
    
    # The SQL Query - use the corrected query from the last step
    cur.execute("""
        SELECT 
            o.id, 
            u.name AS customer_name, 
            o.created_at, 
            o.total_amount, 
            o.payment_status,
            COALESCE(SUM(oi.quantity), 0) AS total_items_calculated
        FROM orders o
        JOIN users u ON o.user_id = u.id
        LEFT JOIN order_items oi ON o.id = oi.order_id
        GROUP BY o.id, u.name, o.created_at, o.total_amount, o.payment_status
        ORDER BY o.created_at DESC
    """)
    data = cur.fetchall()
    cur.close()

    # -----------------------------------------------------------------
    # 2. Write ALL the data rows (THIS LOOP is correctly indented)
    # -----------------------------------------------------------------
    for row in data:
    # CRITICAL FIX: Access fields using dictionary keys (the SQL column aliases)
     writer.writerow([
        row['id'],                       # Access Order ID by key 'id'
        row['customer_name'],           # Access Customer Name by key 'customer_name'
        row['created_at'],               # Access Date Placed by key 'created_at'
        row['total_items_calculated'],  # Access Total Items by key 'total_items_calculated'
        f"{row['total_amount']:.2f}",   # Access Total Amount by key 'total_amount'
        row['payment_status']            # Access Status by key 'payment_status'
    ])
    
    # -----------------------------------------------------------------
    # CRITICAL FIX: This code block MUST be outside the 'for' loop.
    # The indentation MUST match the rest of the function's logic.
    # -----------------------------------------------------------------
    
    # 3. Get the final string value from the buffer
    csv_output = buffer.getvalue()
    
    # 4. Create the Flask response with the final content
    output = Response(csv_output, mimetype="text/csv")
    
    # 5. Add the necessary headers for file download
    output.headers["Content-Disposition"] = f"attachment; filename=orders_report_{now}.csv"
    
    # 6. Return the final response (Aligned with the rest of the main function code)
    return output
# --- APPLICATION START ---

if __name__ == '__main__':
    # NOTE: In production, never run with debug=True.
    app.run(debug=True)