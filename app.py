import os
import uuid
import time
import threading
import webbrowser
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash, jsonify
from functools import wraps

# Initialize Flask with specific template folder structure
app = Flask(__name__, template_folder='templates')
app.secret_key = os.urandom(24)

# Global Server State
SERVER_CONFIG = {
    "folder_path": os.getcwd(), # Default to current directory
    "password": "admin",        # Default password
    "is_running": True,         # If False, client login is disabled
    "is_paused": False,         # If True, client sees blur screen
    "require_approval": False   # If True, downloads need admin action
}

# Store download requests: { uuid: { 'file': path, 'status': 'pending'|'approved'|'rejected', 'ts': time } }
DOWNLOAD_REQUESTS = {}

# --- HELPER DECORATORS ---

def login_required(f):
    """Ensures the client is logged in via the session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('client_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- ADMIN ROUTES (Server Dashboard) ---

@app.route('/admin')
def admin_dashboard():
    """Renders the Web-Based Admin Panel."""
    return render_template('server/index.html', config=SERVER_CONFIG)

@app.route('/admin/api/status', methods=['GET', 'POST'])
def admin_api_status():
    """
    GET: Returns current server config and stats.
    POST: Updates server config (password, folder, pause state, toggle).
    """
    if request.method == 'POST':
        data = request.json
        if 'password' in data: SERVER_CONFIG['password'] = data['password']
        if 'folder_path' in data:
            if os.path.exists(data['folder_path']):
                SERVER_CONFIG['folder_path'] = data['folder_path']
        if 'is_running' in data: SERVER_CONFIG['is_running'] = data['is_running']
        if 'is_paused' in data: SERVER_CONFIG['is_paused'] = data['is_paused']
        if 'require_approval' in data: SERVER_CONFIG['require_approval'] = data['require_approval']

        return jsonify({"status": "updated"})

    # GET Response
    return jsonify({
        "config": SERVER_CONFIG,
        "active_users": 1 if session.get('logged_in') else 0, # Simple estimation
        "pending_count": len([r for r in DOWNLOAD_REQUESTS.values() if r['status'] == 'pending'])
    })

@app.route('/admin/api/requests')
def admin_api_requests():
    """Returns list of pending download requests."""
    pending = {k: v for k, v in DOWNLOAD_REQUESTS.items() if v['status'] == 'pending'}
    return jsonify(pending)

@app.route('/admin/api/decision', methods=['POST'])
def admin_api_decision():
    """
    Handles Admin decision (Approve/Reject) for a specific request ID.
    """
    data = request.json
    req_id = data.get('req_id')
    decision = data.get('decision') # 'approved' or 'rejected'

    if req_id in DOWNLOAD_REQUESTS:
        DOWNLOAD_REQUESTS[req_id]['status'] = decision
        return jsonify({"success": True})
    return jsonify({"error": "Request not found"}), 404

# --- CLIENT ROUTES ---

@app.route('/')
def index():
    return redirect(url_for('client_login'))

@app.route('/login', methods=['GET', 'POST'])
def client_login():
    """Handles Client Login."""
    if not SERVER_CONFIG["is_running"]:
        return render_template('client/login.html', error="Server is currently offline.")

    if request.method == 'POST':
        password_input = request.form.get('password')
        if password_input == SERVER_CONFIG["password"]:
            session['logged_in'] = True
            return redirect(url_for('client_files'))
        else:
            flash('Invalid Password')

    return render_template('client/login.html')

@app.route('/logout')
def client_logout():
    session.clear()
    return redirect(url_for('client_login'))

@app.route('/files')
@login_required
def client_files():
    """Renders the File Browser."""
    # Basic validation
    if not SERVER_CONFIG["is_running"]:
        session.clear()
        return redirect(url_for('client_login'))

    # Logic to list files (similar to before)
    root = SERVER_CONFIG["folder_path"]
    req_path = request.args.get('path', '')
    abs_path = os.path.join(root, req_path)

    # Path Traversal Check
    try:
        if os.path.commonpath([root, abs_path]) != os.path.normpath(root):
            return "Invalid Path", 403
    except:
        return "Invalid Path", 403

    if not os.path.exists(abs_path):
        return "Directory not found", 404

    files_list = []
    folders_list = []

    try:
        for item in os.listdir(abs_path):
            full = os.path.join(abs_path, item)
            rel = os.path.join(req_path, item).replace("\\", "/")

            if os.path.isdir(full):
                folders_list.append({'name': item, 'path': rel})
            else:
                size = round(os.path.getsize(full) / (1024*1024), 2)
                files_list.append({'name': item, 'size': size, 'path': rel})
    except Exception as e:
        return f"Error: {e}", 500

    parent = os.path.dirname(req_path) if req_path else None

    return render_template('client/files.html',
                           files=files_list,
                           folders=folders_list,
                           current_path=req_path,
                           parent=parent)

# --- CLIENT API (Polling & Downloads) ---

@app.route('/api/client/status')
def client_status():
    """Used by client JS to check for Pause/Offline state."""
    return jsonify({
        "paused": SERVER_CONFIG["is_paused"],
        "running": SERVER_CONFIG["is_running"]
    })

@app.route('/api/client/request_download', methods=['POST'])
@login_required
def request_download():
    """
    Client asks to download a file.
    If 'require_approval' is False, returns approved immediately.
    If True, creates a pending request.
    """
    filename = request.json.get('filename')

    # Security: Check if file exists
    full_path = os.path.join(SERVER_CONFIG["folder_path"], filename)
    if not os.path.exists(full_path):
        return jsonify({"error": "File not found"}), 404

    if not SERVER_CONFIG["require_approval"]:
        # Direct access
        return jsonify({"status": "approved", "direct_link": url_for('download_content', filename=filename)})

    # Create approval request
    req_id = str(uuid.uuid4())
    DOWNLOAD_REQUESTS[req_id] = {
        'file': filename,
        'status': 'pending',
        'timestamp': time.time()
    }
    return jsonify({"status": "pending", "req_id": req_id})

@app.route('/api/client/check_request/<req_id>')
@login_required
def check_request(req_id):
    """Client polls this to see if Admin approved the download."""
    if req_id not in DOWNLOAD_REQUESTS:
        return jsonify({"status": "error"})

    req = DOWNLOAD_REQUESTS[req_id]
    response = {"status": req['status']}

    if req['status'] == 'approved':
        # Generate the actual download link
        # We sign it with the req_id to verify approval in the final route
        response['link'] = url_for('download_content', filename=req['file'], token=req_id)

    return jsonify(response)

@app.route('/download_final')
@login_required
def download_content():
    """
    The actual file delivery route.
    Checks tokens if approval was required.
    """
    filename = request.args.get('filename')
    token = request.args.get('token')

    if SERVER_CONFIG["is_paused"]:
        return "Server Paused", 403

    # Validation logic
    if SERVER_CONFIG["require_approval"]:
        if not token or token not in DOWNLOAD_REQUESTS or DOWNLOAD_REQUESTS[token]['status'] != 'approved':
            return "Access Denied / Not Approved", 403
        # Clean up request after success (optional)
        del DOWNLOAD_REQUESTS[token]

    return send_from_directory(SERVER_CONFIG["folder_path"], filename, as_attachment=True)

def open_browser():
    """Opens the Admin Dashboard on launch."""
    time.sleep(1)
    webbrowser.open("http://localhost:5000/admin")

if __name__ == "__main__":
    threading.Thread(target=open_browser).start()
    app.run(host='0.0.0.0', port=5000, debug=False)