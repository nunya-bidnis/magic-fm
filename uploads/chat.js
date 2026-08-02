/**
 * Magic.fm - Discord Chat Widget Module
 * Loads and displays chat messages from Discord webhook
 */

const CHAT_MESSAGES_EL = document.getElementById('chat-messages');
const MAX_DISPLAYED_MESSAGES = 50;
const CHAT_REFRESH_INTERVAL = 5000; // 5 seconds

let lastMessageTime = 0;

/**
 * Load chat messages from API
 */
async function loadChatMessages() {
    try {
        const response = await fetch(`/api/chat/messages?limit=50`);
        if (!response.ok) throw new Error('Failed to load messages');

        const messages = await response.json();
        displayChatMessages(messages);

    } catch (error) {
        console.error('Error loading chat messages:', error);
        if (CHAT_MESSAGES_EL.children.length === 0) {
            CHAT_MESSAGES_EL.innerHTML =
                '<p class="chat-placeholder">Chat unavailable</p>';
        }
    }
}

/**
 * Display chat messages in the widget
 */
function displayChatMessages(messages) {
    if (!messages || messages.length === 0) {
        if (CHAT_MESSAGES_EL.children.length === 0) {
            CHAT_MESSAGES_EL.innerHTML =
                '<p class="chat-placeholder">No messages yet. Join our Discord!</p>';
        }
        return;
    }

    // Limit to MAX_DISPLAYED_MESSAGES
    const displayMessages = messages.slice(-MAX_DISPLAYED_MESSAGES);

    CHAT_MESSAGES_EL.innerHTML = displayMessages
        .map(msg => createMessageElement(msg))
        .join('');

    // Auto-scroll to bottom
    CHAT_MESSAGES_EL.scrollTop = CHAT_MESSAGES_EL.scrollHeight;
}

/**
 * Create HTML element for a chat message
 */
function createMessageElement(msg) {
    const username = escapeHtml(msg.discord_username || 'Anonymous');
    const messageText = escapeHtml(msg.message || '');
    const timestamp = formatChatTime(msg.timestamp);

    return `
        <div class="chat-message">
            <div class="chat-username">${username}</div>
            <div class="chat-text">${messageText}</div>
            <div class="chat-time">${timestamp}</div>
        </div>
    `;
}

/**
 * Format timestamp for chat display
 */
function formatChatTime(timestamp) {
    try {
        const date = new Date(timestamp);
        const now = new Date();

        // If message is today, show time only
        if (date.toDateString() === now.toDateString()) {
            return date.toLocaleTimeString('en-US', {
                hour: '2-digit',
                minute: '2-digit'
            });
        }

        // Otherwise show date and time
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch {
        return timestamp;
    }
}

/**
 * Escape HTML to prevent XSS attacks
 * Critical security measure for user-generated content
 */
function escapeHtml(text) {
    if (!text) return '';

    // Create a div element to leverage browser's HTML escaping
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Validate message content before display
 */
function validateMessage(msg) {
    if (!msg) return false;
    if (!msg.discord_username || !msg.message) return false;
    if (msg.message.length === 0 || msg.message.length > 2000) return false;
    if (msg.discord_username.length > 32) return false;

    return true;
}

/**
 * Sanitize message for display
 */
function sanitizeMessage(msg) {
    return {
        discord_user_id: String(msg.discord_user_id || '').substring(0, 32),
        discord_username: String(msg.discord_username || 'Anonymous').substring(0, 32),
        message: String(msg.message || '').substring(0, 2000),
        timestamp: msg.timestamp || new Date().toISOString()
    };
}

/**
 * Add event listeners for chat updates
 */
function setupChatUpdates() {
    // Optional: Setup real-time updates via WebSocket or Server-Sent Events
    // For now, using polling interval set in main HTML file
}

/**
 * Disconnect chat (cleanup)
 */
function disconnectChat() {
    // Cleanup code if needed
}

// Initialize chat on load
setupChatUpdates();
