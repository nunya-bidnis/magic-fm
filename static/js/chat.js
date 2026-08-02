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

/**
 * Nickname-only chat identity - no account, no password. Just remembered in
 * this browser via localStorage so returning visitors aren't re-prompted.
 */
const CHAT_NICKNAME_KEY = 'chat_nickname';

const CHAT_NICKNAME_ROW = document.getElementById('chat-nickname-row');
const CHAT_NICKNAME_INPUT = document.getElementById('chat-nickname-input');
const CHAT_NICKNAME_SAVE = document.getElementById('chat-nickname-save');
const CHAT_SEND_FORM = document.getElementById('chat-send-form');
const CHAT_CURRENT_NICKNAME = document.getElementById('chat-current-nickname');
const CHAT_NICKNAME_CHANGE = document.getElementById('chat-nickname-change');
const CHAT_MESSAGE_INPUT = document.getElementById('chat-message-input');
const CHAT_SEND_ERROR = document.getElementById('chat-send-error');

function getChatNickname() {
    return localStorage.getItem(CHAT_NICKNAME_KEY);
}

function setChatNickname(name) {
    localStorage.setItem(CHAT_NICKNAME_KEY, name);
    refreshChatIdentityUI();
}

function refreshChatIdentityUI() {
    const nickname = getChatNickname();
    if (nickname) {
        CHAT_NICKNAME_ROW.style.display = 'none';
        CHAT_SEND_FORM.style.display = 'block';
        CHAT_CURRENT_NICKNAME.textContent = nickname;
    } else {
        CHAT_NICKNAME_ROW.style.display = 'flex';
        CHAT_SEND_FORM.style.display = 'none';
    }
}

function showChatSendError(message) {
    CHAT_SEND_ERROR.textContent = message;
    CHAT_SEND_ERROR.classList.add('show');
    setTimeout(() => CHAT_SEND_ERROR.classList.remove('show'), 4000);
}

if (CHAT_NICKNAME_SAVE) {
    CHAT_NICKNAME_SAVE.addEventListener('click', () => {
        const name = CHAT_NICKNAME_INPUT.value.trim();
        if (!name) return;
        setChatNickname(name);
    });

    CHAT_NICKNAME_INPUT.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') CHAT_NICKNAME_SAVE.click();
    });

    CHAT_NICKNAME_CHANGE.addEventListener('click', () => {
        localStorage.removeItem(CHAT_NICKNAME_KEY);
        CHAT_NICKNAME_INPUT.value = '';
        refreshChatIdentityUI();
    });

    CHAT_SEND_FORM.addEventListener('submit', async (e) => {
        e.preventDefault();

        const nickname = getChatNickname();
        const message = CHAT_MESSAGE_INPUT.value.trim();
        if (!nickname || !message) return;

        try {
            const res = await fetch('/api/chat/messages', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ nickname, message })
            });

            if (!res.ok) {
                const data = await res.json().catch(() => ({}));
                showChatSendError(data.detail || 'Could not send message');
                return;
            }

            CHAT_MESSAGE_INPUT.value = '';
            loadChatMessages();
        } catch {
            showChatSendError('Could not send message. Check your connection.');
        }
    });

    refreshChatIdentityUI();
}

// Initialize chat on load
setupChatUpdates();
