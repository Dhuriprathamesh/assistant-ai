// Get DOM elements
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');

// Add event listener for Enter key
userInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

// Function to send message
async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    // Add user message to chat
    addMessage(message, 'user');
    userInput.value = '';

    try {
        // Show loading message
        const loadingId = addMessage('Processing...', 'assistant');
        
        // Send message to backend
        const response = await fetch(`${apiUrl}/api/process_command`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({ command: message })
        });

        // Remove loading message
        document.getElementById(loadingId).remove();

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        
        if (data.error) {
            addMessage('Error: ' + data.error, 'assistant');
        } else {
            addMessage(data.response, 'assistant');
        }
    } catch (error) {
        console.error('Error:', error);
        addMessage('Connection error. Please try again. If the problem persists, check if the backend is running.', 'assistant');
    }
}

// Function to add message to chat
function addMessage(text, sender) {
    const messageDiv = document.createElement('div');
    const messageId = 'msg-' + Date.now();
    messageDiv.id = messageId;
    messageDiv.className = `message ${sender}-message`;
    messageDiv.textContent = text;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return messageId;
}

// Function to check backend health
async function checkBackendHealth() {
    try {
        const response = await fetch(`${apiUrl}/health`);
        const data = await response.json();
        if (data.status === 'healthy') {
            console.log('Backend is healthy');
            return true;
        }
    } catch (error) {
        console.error('Backend health check failed:', error);
        return false;
    }
}

// Check backend health on page load
window.addEventListener('load', async () => {
    const isHealthy = await checkBackendHealth();
    if (!isHealthy) {
        addMessage('Warning: Backend connection issues detected. Some features may not work properly.', 'assistant');
    }
    // Add welcome message
    addMessage('Hello! I\'m your AI assistant. How can I help you today?', 'assistant');
}); 