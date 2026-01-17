import os
import uuid
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
        flash('Invalid Password')
    return render_template('client/login.html')

@client_app.route('/files')
@login_required
def client_files():
    root = SERVER_CONFIG["folder_path"]
    req_path = request.args.get('path', '')
    abs_path = os.path.normpath(os.path.join(root, req_path))

    if not abs_path.startswith(os.path.normpath(root)) or not os.path.exists(abs_path):
        return redirect(url_for('client_files'))

    folders, files = [], []
    for item in os.listdir(abs_path):
        full = os.path.join(abs_path, item)
        rel = os.path.join(req_path, item).replace("\\", "/")
        if os.path.isdir(full):
            folders.append({'name': item, 'path': rel})
        else:
            files.append({'name': item, 'size': format_file_size(os.path.getsize(full)), 'path': rel})

    return render_template('client/files.html', files=files, folders=folders, current_path=req_path, parent=os.path.dirname(req_path) if req_path else None)

# ... (Hier die restlichen Client-API-Routen /api/client/... und /download_final einfügen)
