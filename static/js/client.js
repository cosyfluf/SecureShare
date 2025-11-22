/**
 * Global state for the View Mode (Grid vs List).
 * @type {boolean}
 */
let isGridView = true;

/**
 * Global state to track if the UI is currently paused/blurred.
 * @type {boolean}
 */
let pausedState = false;

/**
 * Interval ID for polling download request status.
 * @type {number|null}
 */
let pollInterval = null;

/**
 * Toggles the file container between Grid View and List View.
 * Updates the icon and reshapes the file cards using Tailwind classes.
 */
function toggleView() {
    isGridView = !isGridView;
    const container = document.getElementById('fileContainer');
    const icon = document.getElementById('viewIcon');
    const cards = document.querySelectorAll('.file-card');

    if (isGridView) {
        // Switch to Grid
        container.classList.remove('flex', 'flex-col');
        container.classList.add('grid', 'grid-cols-1', 'sm:grid-cols-2', 'md:grid-cols-3', 'lg:grid-cols-4');
        icon.className = "fas fa-list-ul";

        cards.forEach(el => {
            el.classList.remove('flex-row', 'items-center', 'min-h-[60px]');
            el.classList.add('flex-col', 'min-h-[180px]');
            // Show the large icon background
            const iconBg = el.querySelector('.fa-file, .fa-folder').closest('.absolute');
            if(iconBg) iconBg.classList.remove('hidden');
        });
    } else {
        // Switch to List
        container.classList.remove('grid', 'grid-cols-1', 'sm:grid-cols-2', 'md:grid-cols-3', 'lg:grid-cols-4');
        container.classList.add('flex', 'flex-col');
        icon.className = "fas fa-th-large";

        cards.forEach(el => {
            el.classList.remove('flex-col', 'min-h-[180px]');
            el.classList.add('flex-row', 'items-center', 'min-h-[60px]', 'gap-4');
            // Hide the large icon background for cleaner list view
            const iconBg = el.querySelector('.fa-file, .fa-folder').closest('.absolute');
            if(iconBg) iconBg.classList.add('hidden');
        });
    }
}

/**
 * Polls the server status every second.
 * Handles forcing reload if server stops, or blurring the UI if paused.
 */
function checkStatus() {
    fetch('/api/client/status')
        .then(response => response.json())
        .then(data => {
            // Reload if server goes offline
            if (!data.running) window.location.reload();

            const overlay = document.getElementById('pauseOverlay');
            const mainContent = document.getElementById('main-content');

            // Apply Pause State
            if (data.paused && !pausedState) {
                pausedState = true;
                overlay.classList.remove('opacity-0', 'pointer-events-none');
                mainContent.classList.add('blur-sm');
            }
            // Remove Pause State
            else if (!data.paused && pausedState) {
                pausedState = false;
                overlay.classList.add('opacity-0', 'pointer-events-none');
                mainContent.classList.remove('blur-sm');
            }
        });
}

/**
 * Initiates the download process for a specific file.
 * Opens the modal and sends a request to the server.
 *
 * @param {string} filename - The name of the file to download.
 * @param {string} path - The relative path (currently unused in logic but passed for context).
 */
function initiateDownload(filename, path) {
    const modal = document.getElementById('approvalModal');
    const content = document.getElementById('approvalContent');

    // Show Modal
    modal.classList.remove('opacity-0', 'pointer-events-none');
    content.classList.remove('scale-95');
    content.classList.add('scale-100');

    // Reset UI states inside modal
    document.getElementById('statusWaiting').classList.remove('hidden');
    document.getElementById('statusRejected').classList.add('hidden');
    document.getElementById('statusApproved').classList.add('hidden');

    // API Request
    fetch('/api/client/request_download', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({filename: filename})
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'approved') {
                // Direct download allowed
                closeModal();
                window.location.href = data.direct_link;
            } else if (data.status === 'pending') {
                // Approval required, start polling
                document.getElementById('reqIdDisplay').innerText = "ID: " + data.req_id.substring(0, 8);
                pollRequest(data.req_id);
            }
        });
}

/**
 * Polls the status of a specific download request ID.
 *
 * @param {string} reqId - The unique UUID of the request.
 */
function pollRequest(reqId) {
    pollInterval = setInterval(() => {
        fetch('/api/client/check_request/' + reqId)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'approved') {
                    clearInterval(pollInterval);
                    showApproved();
                    // Delay slightly for visual feedback before downloading
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
 * Closes the modal and stops any active polling.
 */
function closeModal() {
    const modal = document.getElementById('approvalModal');
    const content = document.getElementById('approvalContent');

    modal.classList.add('opacity-0', 'pointer-events-none');
    content.classList.add('scale-95');
    content.classList.remove('scale-100');

    if (pollInterval) clearInterval(pollInterval);
}

// Start the global status polling
setInterval(checkStatus, 1000);