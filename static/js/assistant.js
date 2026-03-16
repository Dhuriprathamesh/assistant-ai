document.addEventListener('DOMContentLoaded', () => {
    // Initialize variables
    let isListening = false;
    let recognition = null;
    const API_BASE_URL = 'http://localhost:5000/api';
    const aiTips = [
        "Ask me: What's the weather like today?",
        "Try saying: Search Wikipedia for AI",
        "Say: What time is it?"
    ];

    // Initialize Web Speech API
    function initializeSpeechRecognition() {
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            showNotification('Speech recognition is not supported in your browser. Please use Chrome or Edge.', 'error');
            return false;
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        recognition.onstart = () => {
            console.log('Speech recognition started');
            isListening = true;
            updateVoiceStatus();
            showNotification('Listening...', 'info');
        };

        recognition.onresult = (event) => {
            const command = event.results[0][0].transcript.toLowerCase();
            console.log('Recognized command:', command);
            showNotification(`You said: ${command}`, 'info');
            processCommand(command);
        };

        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            showNotification(`Error: ${event.error}`, 'error');
            isListening = false;
            updateVoiceStatus();
        };

        recognition.onend = () => {
            console.log('Speech recognition ended');
            isListening = false;
            updateVoiceStatus();
        };

        return true;
    }

    // Menu Navigation
    const menuItems = document.querySelectorAll('.menu-item');
    const sections = document.querySelectorAll('.dashboard-section, .voice-section, .history-section, .settings-section');

    menuItems.forEach(item => {
        item.addEventListener('click', () => {
            const targetSection = item.dataset.section;
            
            // Update active states
            menuItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            
            sections.forEach(section => {
                section.classList.remove('active');
                if (section.id === targetSection) {
                    section.classList.add('active');
                }
            });
        });
    });

    // Theme Switching
    const themeButtons = document.querySelectorAll('.theme-btn');
    themeButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const theme = btn.dataset.theme;
            document.body.setAttribute('data-theme', theme);
            localStorage.setItem('theme', theme);
        });
    });

    // Load saved theme
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.body.setAttribute('data-theme', savedTheme);

    // Voice Toggle
    const voiceToggle = document.getElementById('voice-toggle');
    voiceToggle.addEventListener('click', async () => {
        if (!recognition) {
            if (!initializeSpeechRecognition()) {
                return;
            }
        }

        try {
            if (isListening) {
                recognition.stop();
            } else {
                // Request microphone permission explicitly
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                stream.getTracks().forEach(track => track.stop()); // Stop the stream after getting permission
                
                recognition.start();
                console.log('Starting speech recognition...');
            }
        } catch (error) {
            console.error('Error accessing microphone:', error);
            showNotification('Please allow microphone access to use voice commands', 'error');
        }
    });

    // Update voice status UI
    function updateVoiceStatus() {
        const statusText = document.getElementById('voice-status-text');
        const voiceWave = document.querySelector('.voice-wave');
        const voiceBtn = document.getElementById('voice-toggle');
        
        if (isListening) {
            statusText.textContent = 'Listening...';
            voiceWave.style.display = 'flex';
            voiceBtn.classList.add('listening');
        } else {
            statusText.textContent = 'Click the microphone to start';
            voiceWave.style.display = 'none';
            voiceBtn.classList.remove('listening');
        }
    }

    // Add message to chat
    function addMessage(message, isUser = false) {
        const chatMessages = document.getElementById('chat-messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user-message' : 'ai-message'}`;
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        const img = document.createElement('img');
        img.src = isUser ? 'user_avatar.jpg' : 'ai_avatar.jpg';
        img.alt = isUser ? 'User' : 'AI';
        avatar.appendChild(img);
        
        const content = document.createElement('div');
        content.className = 'message-content';
        const text = document.createElement('p');
        text.innerHTML = message;
        content.appendChild(text);
        
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(content);
        
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Process voice commands
    async function processCommand(command) {
        console.log('Processing command:', command);
        addToHistory(command);
        addMessage(command, true);
        
        try {
            const response = await fetch(`${API_BASE_URL}/process_command`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ command })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('Command response:', data);
            
            const responseText = data.response.replace(/\n/g, '<br>');
            showNotification(responseText, 'success');
            addMessage(responseText, false);
            
            // Apply voice settings when speaking
            if ('speechSynthesis' in window && voiceEnabled.checked) {
                const utterance = new SpeechSynthesisUtterance(data.response);
                utterance.rate = parseFloat(voiceSpeed.value);
                window.speechSynthesis.speak(utterance);
            }
            
            if (data.history) {
                updateHistory(data.history);
            }
        } catch (error) {
            console.error('Error processing command:', error);
            const errorMessage = 'Failed to process command. Please try again.';
            showNotification(errorMessage, 'error');
            addMessage(errorMessage, false);
        }
    }

    // Add command to history
    function addToHistory(command) {
        const historyList = document.getElementById('history-list');
        const time = new Date().toLocaleTimeString();
        const item = document.createElement('div');
        item.className = 'history-item';
        item.innerHTML = `
            <span class="time">${time}</span>
            <span class="command">${command}</span>
        `;
        historyList.insertBefore(item, historyList.firstChild);
    }

    // Update history from server
    function updateHistory(history) {
        const historyList = document.getElementById('history-list');
        historyList.innerHTML = '';
        
        history.forEach(item => {
            const historyItem = document.createElement('div');
            historyItem.className = 'history-item';
            historyItem.innerHTML = `
                <span class="time">${item.timestamp}</span>
                <span class="command">${item.command}</span>
            `;
            historyList.appendChild(historyItem);
        });
    }

    // Quick Actions
    const actionCards = document.querySelectorAll('.action-card');
    actionCards.forEach(card => {
        card.addEventListener('click', () => {
            const action = card.dataset.action;
            let command = '';
            
            switch (action) {
                case 'weather':
                    const city = prompt('Enter city name:');
                    if (city) command = `weather in ${city}`;
                    break;
                case 'wikipedia':
                    const topic = prompt('Enter topic to search:');
                    if (topic) command = `search wikipedia for ${topic}`;
                    break;
                case 'time':
                    command = 'what time is it';
                    break;
            }
            
            if (command) {
                processCommand(command);
            }
        });
    });

    // Weather API
    async function getWeather(city) {
        try {
            const response = await fetch(`https://api.openweathermap.org/data/2.5/weather?q=${city}&appid=5b6b1206aefe5fa56d39570a34b45e14&units=metric`);
            const data = await response.json();
            
            if (data.cod === 200) {
                const temp = data.main.temp;
                const desc = data.weather[0].description;
                const humidity = data.main.humidity;
                const windSpeed = data.wind.speed;
                const weatherInfo = `${city}: ${temp}°C, ${desc}\nHumidity: ${humidity}%\nWind Speed: ${windSpeed} m/s`;
                showNotification(weatherInfo, 'success');
                addMessage(weatherInfo, false);
            } else {
                showNotification('City not found', 'error');
            }
        } catch (error) {
            showNotification('Failed to get weather data', 'error');
        }
    }

    // Wikipedia Search
    async function searchWikipedia(topic) {
        try {
            const response = await fetch(`https://en.wikipedia.org/api/rest_v1/page/summary/${topic}`);
            const data = await response.json();
            
            if (data.extract) {
                showNotification(data.extract, 'success');
            } else {
                showNotification('No results found', 'error');
            }
        } catch (error) {
            showNotification('Failed to search Wikipedia', 'error');
        }
    }

    // Show Time
    function showTime() {
        const now = new Date().toLocaleTimeString();
        showNotification(`Current time: ${now}`, 'success');
    }

    // Show Notification
    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = message;
        
        document.body.appendChild(notification);
        
        // Remove any existing notifications
        const existingNotifications = document.querySelectorAll('.notification');
        existingNotifications.forEach(notif => {
            if (notif !== notification) {
                notif.remove();
            }
        });
        
        setTimeout(() => {
            notification.classList.add('show');
        }, 100);
        
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    }

    // Update AI Tip
    async function updateAITip() {
        try {
            const response = await fetch(`${API_BASE_URL}/get_tip`);
            const data = await response.json();
            const tipElement = document.getElementById('ai-tip');
            tipElement.textContent = data.tip;
        } catch (error) {
            console.error('Failed to fetch AI tip:', error);
        }
    }

    // Update Time
    async function updateTime() {
        try {
            const response = await fetch(`${API_BASE_URL}/get_time`);
            const data = await response.json();
            const timeElement = document.getElementById('current-time');
            timeElement.textContent = data.time;
        } catch (error) {
            console.error('Failed to fetch time:', error);
        }
    }

    // Initialize
    updateAITip();
    updateTime();
    setInterval(updateTime, 1000);
    setInterval(updateAITip, 10000);

    // Avatar Change
    const avatarInput = document.getElementById('avatar-input');
    const aiAvatar = document.getElementById('ai-avatar');

    avatarInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                aiAvatar.src = e.target.result;
            };
            reader.readAsDataURL(file);
        }
    });

    // Handle text input
    const searchInput = document.querySelector('.search-bar input');
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && searchInput.value.trim()) {
            processCommand(searchInput.value.trim());
            searchInput.value = '';
        }
    });

    // Settings Panel Functionality
    const voiceEnabled = document.getElementById('voice-enabled');
    const voiceSpeed = document.getElementById('voice-speed');
    const themeSelect = document.getElementById('theme-select');

    // Load saved settings
    function loadSettings() {
        const savedVoiceEnabled = localStorage.getItem('voiceEnabled') !== 'false';
        const savedVoiceSpeed = localStorage.getItem('voiceSpeed') || '1';
        const savedTheme = localStorage.getItem('theme') || 'dark';

        voiceEnabled.checked = savedVoiceEnabled;
        voiceSpeed.value = savedVoiceSpeed;
        themeSelect.value = savedTheme;
        document.body.setAttribute('data-theme', savedTheme);
    }

    // Save settings
    function saveSettings() {
        localStorage.setItem('voiceEnabled', voiceEnabled.checked);
        localStorage.setItem('voiceSpeed', voiceSpeed.value);
        localStorage.setItem('theme', themeSelect.value);
    }

    // Voice settings handlers
    voiceEnabled.addEventListener('change', () => {
        saveSettings();
        if (!voiceEnabled.checked) {
            if (recognition && isListening) {
                recognition.stop();
            }
            showNotification('Voice input disabled', 'info');
        } else {
            showNotification('Voice input enabled', 'info');
        }
    });

    voiceSpeed.addEventListener('input', () => {
        saveSettings();
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance('Voice speed updated');
            utterance.rate = parseFloat(voiceSpeed.value);
            window.speechSynthesis.speak(utterance);
        }
    });

    // Theme selection handler
    themeSelect.addEventListener('change', () => {
        const theme = themeSelect.value;
        document.body.setAttribute('data-theme', theme);
        saveSettings();
        showNotification(`Theme changed to ${theme}`, 'info');
    });

    // Initialize settings
    loadSettings();
}); 