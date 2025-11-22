/**
 * Timeout reference for the notification toast to allow resetting timer.
 * @type {number|undefined}
 */
let toastTimeout;

/**
 * Displays a floating notification toast.
 *
 * @param {string} message - The text to display in the toast.
 */
function showNotification(message) {
    const toast = document.getElementById('notificationToast');
    const msgEl = document.getElementById('toastMessage');

    msgEl.innerText = message;
    toast.classList.remove('translate-y-20', 'opacity-0');

    if (toastTimeout) clearTimeout(toastTimeout);

    toastTimeout = setTimeout(() => {
        toast.classList.add('translate-y-20', 'opacity-0');
    }, 3000);
}

/**
 * Fetches the current server status and updates the Dashboard UI.
 * Updates toggles (checkboxes) and the visual status indicator.
 */
function fetchState() {
    fetch('/admin/api/status')
        .then(response => response.json())
        .then(data => {
            const config = data.config;

            // Update Checkboxes
            document.getElementById('toggleRunning').checked = config.is_running;
            document.getElementById('togglePause').checked = config.is_paused;
            document.getElementById('toggleApproval').checked = config.require_approval;

            // Update Visual Indicator
            const indicator = document.getElementById('status-indicator');
            if (config.is_running) {
                indicator.className = "px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
                indicator.innerHTML = '<i class="fas fa-circle text-[8px] mr-2"></i>Active';
            } else {
                indicator.className = "px-3 py-1 rounded-full text-xs font-bold bg-red-500/20 text-red-400 border border-red-500/30";
                indicator.innerHTML = '<i class="fas fa-circle text-[8px] mr-2"></i>Offline';
            }
        });
}

/**
 * Toggles a server configuration boolean via API.
 *
 * @param {string} key - The configuration key (is_running, is_paused, require_approval).
 */
function toggleState(key) {
    let checkboxId;
    if (key === 'is_running') checkboxId = 'toggleRunning';
    else if (key === 'is_paused') checkboxId = 'togglePause';
    else checkboxId = 'toggleApproval';

    const value = document.getElementById(checkboxId).checked;

    fetch('/admin/api/status', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({[key]: value})
    }).then(() => {
        fetchState(); // Refresh UI to confirm sync
    });
}

/**
 * Updates text configuration (Password or Folder Path).
 *
 * @param {string} type - 'folder' or 'password'.
 */
function updateConfig(type) {
    const inputId = type === 'folder' ? 'folderPath' : 'clientPass';
    const configKey = type === 'folder' ? 'folder_path' : 'password';
    const value = document.getElementById(inputId).value;

    fetch('/admin/api/status', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({[configKey]: value})
    }).then(() => {
        const msg = type === 'folder' ? 'Shared folder path updated.' : 'Access password updated.';
        showNotification(msg);
    });
}

/**
 * Fetches pending download requests and populates the table.
 */
function fetchRequests() {
    fetch('/admin/api/requests')
        .then(response => response.json())
        .then(data => {
            const tbody = document.getElementById('requestsTable');
            const reqIds = Object.keys(data);

            // Update Badge Count
            document.getElementById('pendingCount').innerText = reqIds.length;

            if (reqIds.length === 0) {
                tbody.innerHTML = '<tr><td colspan="3" class="px-4 py-4 text-center italic text-slate-600">No pending requests</td></tr>';
                return;
            }

            // Render Table Rows
            tbody.innerHTML = reqIds.map(id => {
                const req = data[id];
                const timeStr = new Date(req.timestamp * 1000).toLocaleTimeString();
                return `
                    <tr class="bg-slate-900/20 hover:bg-slate-800/50 transition">
                        <td class="px-4 py-3 font-mono text-xs">${timeStr}</td>
                        <td class="px-4 py-3 text-white font-medium">${req.file}</td>
                        <td class="px-4 py-3 flex gap-2">
                            <button onclick="decide('${id}', 'approved')" class="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs transition">Approve</button>
                            <button onclick="decide('${id}', 'rejected')" class="px-3 py-1 bg-red-600 hover:bg-red-500 text-white rounded text-xs transition">Reject</button>
                        </td>
                    </tr>
                `;
            }).join('');
        });
}

/**
 * Sends an approval or rejection decision to the server.
 *
 * @param {string} reqId - The request UUID.
 * @param {string} decision - 'approved' or 'rejected'.
 */
function decide(reqId, decision) {
    fetch('/admin/api/decision', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({req_id: reqId, decision: decision})
    }).then(() => {
        fetchRequests(); // Refresh table immediately
        showNotification(`Request ${decision}.`);
    });
}

// Initial Loops
setInterval(fetchState, 2000);
setInterval(fetchRequests, 2000);
fetchState();
fetchRequests();