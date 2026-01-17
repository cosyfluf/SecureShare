import threading
import time
import webbrowser
from config import ADMIN_PORT
from client_routes import client_app
from admin_routes import admin_app

def open_browser():
    """Öffnet das Admin-Panel nach dem Start."""
    time.sleep(1.5)
    admin_url = f"http://127.0.0.1:{ADMIN_PORT}/admin"
    print(f"\n[INFO] Admin Panel: {admin_url}")
    print(f"[INFO] Client Server running on port 5000\n")
    webbrowser.open(admin_url)

def run_client():
    client_app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def run_admin():
    admin_app.run(host='127.0.0.1', port=ADMIN_PORT, debug=False, use_reloader=False)

if __name__ == "__main__":
    # Browser Launcher Thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Client Server Thread
    client_thread = threading.Thread(target=run_client, daemon=True)
    client_thread.start()

    # Admin Server (Hauptthread)
    run_admin()