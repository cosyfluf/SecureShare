import os
import uuid
import time
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash, jsonify
from config import SERVER_CONFIG, DOWNLOAD_REQUESTS, TEMPLATE_DIR, STATIC_DIR
from utils import login_required, format_file_size

client_app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
client_app.secret_key = os.urandom(24)

@client_app.route('/')
def index():
    return redirect(url_for('client_login'))

@client_app.route('/login', methods=['GET', 'POST'])
def client_login():
    if request.args.get('reason') == 'logout':
        flash('You have been logged out by the administrator.')

    if not SERVER_CONFIG["is_running"]:
        return render_template('client/login.html', error="Server is currently offline.")

    if request.method == 'POST':
        if request.form.get('password') == SERVER_CONFIG["password"]:
            session['logged_in'] = True
            session['token'] = SERVER_CONFIG['session_token']
            return redirect(url_for('client_files'))
        else:
            flash('Invalid Password')

    return render_template('client/login.html')

@client_app.route('/logout')
def client_logout():
    session.clear()
    return redirect(url_for('client_login'))

@client_app.route('/files')
@login_required
def client_files():
    root = SERVER_CONFIG["folder_path"]
    req_path = request.args.get('path', '')
    abs_path = os.path.join(root, req_path)

    try:
        if os.path.commonpath([root, abs_path]) != os.path.normpath(root):
            return "Invalid Path", 403
    except Exception:
        return "Invalid Path", 403

    if not os.path.exists(abs_path):
        return redirect(url_for('client_files'))

    files_list, folders_list = [], []
    try:
        for item in os.listdir(abs_path):
            full = os.path.join(abs_path, item)
            rel = os.path.join(req_path, item).replace("\\", "/")
            if os.path.isdir(full):
                folders_list.append({'name': item, 'path': rel})
            else:
                files_list.append({
                    'name': item, 
                    'size': format_file_size(os.path.getsize(full)), 
                    'path': rel
                })
    except Exception as e:
        return f"Error: {e}", 500

    return render_template('client/files.html', 
                           files=files_list, 
                           folders=folders_list, 
                           current_path=req_path, 
                           parent=os.path.dirname(req_path) if req_path else None)

@client_app.route('/api/client/status')
def client_status():
    token_valid = session.get('token') == SERVER_CONFIG['session_token']
    force_logout = session.get('logged_in') and not token_valid
    return jsonify({
        "paused": SERVER_CONFIG["is_paused"],
        "running": SERVER_CONFIG["is_running"],
        "force_logout": force_logout,
        "config_id": SERVER_CONFIG["config_id"]
    })

@client_app.route('/api/client/request_download', methods=['POST'])
@login_required
def request_download():
    data = request.json
    filename, rel_path = data.get('filename'), data.get('path', data.get('filename'))
    full_path = os.path.join(SERVER_CONFIG["folder_path"], rel_path)

    if not os.path.exists(full_path):
        return jsonify({"error": "File not found"}), 404

    file_rel_path = rel_path.replace("\\", "/")

    if not SERVER_CONFIG["require_approval"]:
        return jsonify({
            "status": "approved",
            "direct_link": url_for('download_content', filepath=file_rel_path)
        })

    req_id = str(uuid.uuid4())
    DOWNLOAD_REQUESTS[req_id] = {
        'file': filename, 'filepath': file_rel_path, 'status': 'pending', 'timestamp': time.time()
    }
    return jsonify({"status": "pending", "req_id": req_id})

@client_app.route('/api/client/check_request/<req_id>')
@login_required
def check_request(req_id):
    if req_id not in DOWNLOAD_REQUESTS:
        return jsonify({"status": "error"})
    req = DOWNLOAD_REQUESTS[req_id]
    res = {"status": req['status']}
    if req['status'] == 'approved':
        res['link'] = url_for('download_content', filepath=req['filepath'], token=req_id)
    return jsonify(res)

@client_app.route('/download_final')
@login_required
def download_content():
    filepath, token = request.args.get('filepath'), request.args.get('token')
    if SERVER_CONFIG["is_paused"]: return "Server Paused", 403

    if SERVER_CONFIG["require_approval"]:
        if not token or token not in DOWNLOAD_REQUESTS or DOWNLOAD_REQUESTS[token]['status'] != 'approved':
            return "Access Denied", 403
        del DOWNLOAD_REQUESTS[token]

    full_path = os.path.join(SERVER_CONFIG["folder_path"], filepath)
    return send_from_directory(os.path.dirname(full_path), os.path.basename(full_path), as_attachment=True)