/**
 * Global state for the View Mode (Grid vs List).
 * True indicates Grid View, False indicates List View.
 */
let isGridView = true;

/**
 * Global state to track if the UI is currently paused/blurred.
 * Used to prevent unnecessary DOM updates if the state hasn't changed.
 */
let pausedState = false;

/**
 * Stores the current server configuration ID.
 * This ID is updated by the server whenever the shared folder path changes.
 * The client checks this ID; if it differs from the stored one, the page is reloaded.
 */
let currentConfigId = null;

/**
 * Interval ID for polling the status of a specific download request.
 */
let pollInterval = null;

/**
 * Toggles the file browser layout between Grid and List view.
 * Updates CSS classes and icon visibility accordingly.
 */
function toggleView() {
    isGridView = !isGridView;
    const container = document.getElementById('fileContainer');
    const icon = document.getElementById('viewIcon');
    const cards = document.querySelectorAll('.file-card');

    if (isGridView) {
        // Switch to Grid View
        container.classList.remove('flex', 'flex-col');
        container.classList.add('grid', 'grid-cols-1', 'sm:grid-cols-2', 'md:grid-cols-3', 'lg:grid-cols-4');
        icon.className = "fas fa-list-ul";

        cards.forEach(el => {
            el.classList.remove('flex-row', 'items-center', 'min-h-[60px]');
            el.classList.add('flex-col', 'min-h-[180px]');
            // Show large icons in grid view
            const iconBg = el.querySelector('.fa-file, .fa-folder').closest('.absolute');
            if(iconBg) iconBg.classList.remove('hidden');
        });
    } else {
        // Switch to List View
        container.classList.remove('grid', 'grid-cols-1', 'sm:grid-cols-2', 'md:grid-cols-3', 'lg:grid-cols-4');
        container.classList.add('flex', 'flex-col');
        icon.className = "fas fa-th-large";

        cards.forEach(el => {
            el.classList.remove('flex-col', 'min-h-[180px]');
            el.classList.add('flex-row', 'items-center', 'min-h-[60px]', 'gap-4');
            // Hide large background icons in list view
            const iconBg = el.querySelector('.fa-file, .fa-folder').closest('.absolute');
            if(iconBg) iconBg.classList.add('hidden');
        });
    }
}

/**
 * Periodically polls the server status endpoint.
 * Handles:
 * 1. Forced logout (if session is invalid).
 * 2. Server offline state (redirects to logout).
 * 3. Configuration changes (reloads page if root folder changes).
 * 4. Pause state (toggles blur overlay).
 */
function checkStatus() {
    fetch('/api/client/status')
        .then(response => response.json())
        .then(data => {
            // Case 1: Admin forced a logout via 'Logout All'
            if (data.force_logout) {
                window.location.href = '/login?reason=logout';
                return;
            }

            // Case 2: Server is explicitly set to Offline
            if (!data.running) {
                window.location.href = '/logout';
                return;
            }

            // Case 3: Detect if the Admin changed the root folder
            if (currentConfigId === null) {
                currentConfigId = data.config_id;
            } else if (currentConfigId !== data.config_id) {
                // Config ID changed, redirect to base files path to refresh content
                window.location.href = '/files';
                return;
            }

            // Case 4: Handle UI Pause/Blur
            const overlay = document.getElementById('pauseOverlay');
            const mainContent = document.getElementById('main-content');

            if (data.paused && !pausedState) {
                pausedState = true;
                overlay.classList.remove('opacity-0', 'pointer-events-none');
                mainContent.classList.add('blur-sm');
            }
            else if (!data.paused && pausedState) {
                pausedState = false;
                overlay.classList.add('opacity-0', 'pointer-events-none');
                mainContent.classList.remove('blur-sm');
            }
        });
}

/**
 * Initiates the download process for a specific file.
 * Opens the approval modal and sends a request to the server.
 *
 * @param {string} filename - The name of the file to download.
 * @param {string} path - The relative path to the file.
 */
function initiateDownload(filename, path) {
    const modal = document.getElementById('approvalModal');
    const content = document.getElementById('approvalContent');

    // Show the modal
    modal.classList.remove('opacity-0', 'pointer-events-none');
    content.classList.remove('scale-95');
    content.classList.add('scale-100');

    // Reset modal state to 'Waiting'
    document.getElementById('statusWaiting').classList.remove('hidden');
    document.getElementById('statusRejected').classList.add('hidden');
    document.getElementById('statusApproved').classList.add('hidden');
    document.getElementById('reqIdDisplay').innerText = "ID: ...";

    // Send request to server
    fetch('/api/client/request_download', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({filename: filename, path: path})
    })
        .then(response => {
            // If the server returns 404 (e.g., file moved), throw error
            if (!response.ok) throw new Error("File not found or server error");
            return response.json();
        })
        .then(data => {
            if (data.status === 'approved') {
                // Approval not required, download immediately
                closeModal();
                window.location.href = data.direct_link;
            } else if (data.status === 'pending') {
                // Approval required, start polling
                document.getElementById('reqIdDisplay').innerText = "ID: " + data.req_id.substring(0, 8);
                pollRequest(data.req_id);
            }
        })
        .catch(err => {
            console.error("Download Request Failed:", err);
            closeModal();
            // Refresh page if the file structure is out of sync
            alert("Could not request file. The shared folder might have changed.");
            window.location.reload();
        });
}

/**
 * Polls the server to check the status of a pending download request.
 * Stops polling once the request is approved or rejected.
 *
 * @param {string} reqId - The unique ID of the download request.
 */
function pollRequest(reqId) {
    pollInterval = setInterval(() => {
        fetch('/api/client/check_request/' + reqId)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'approved') {
                    clearInterval(pollInterval);
                    showApproved();
                    // Short delay before download starts
                    setTimeout(() => {
                        window.location.href = data.link;
                        closeModal();
                    }, 1500);
                } else if (data.status === 'rejected') {
                    clearInterval(pollInterval);
                    showRejected();
                }
            });
    }, 1000);
}

/**
 * Updates the modal UI to show the Approved state.
 */
function showApproved() {
    document.getElementById('statusWaiting').classList.add('hidden');
    document.getElementById('statusApproved').classList.remove('hidden');
}

/**
 * Updates the modal UI to show the Rejected state.
 */
function showRejected() {
    document.getElementById('statusWaiting').classList.add('hidden');
    document.getElementById('statusRejected').classList.remove('hidden');
}

/**
 * Closes the approval modal and stops any active polling.
 */
function closeModal() {
    const modal = document.getElementById('approvalModal');
    const content = document.getElementById('approvalContent');

    modal.classList.add('opacity-0', 'pointer-events-none');
    content.classList.add('scale-95');
    content.classList.remove('scale-100');

    if (pollInterval) clearInterval(pollInterval);
}

// Start the status polling loop
setInterval(checkStatus, 1000);