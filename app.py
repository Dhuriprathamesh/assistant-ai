from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import jwt
import datetime
import wikipedia
import requests
import json
import os
import logging
import random
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import math
import schedule
import time
import threading
import winsound  # For Windows sound notifications
from datetime import datetime, timedelta
import pytz

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.')
CORS(app)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this to a secure secret key

# Set timezone (you can change this to your local timezone)
TIMEZONE = 'Asia/Kolkata'  # For Indian time
timezone = pytz.timezone(TIMEZONE)

# Database initialization
def init_db():
    try:
        conn = sqlite3.connect('users.db', timeout=20)  # Add timeout to handle concurrent connections
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
    except Exception as e:
        logger.error(f"Database initialization error: {str(e)}")
        raise
    finally:
        conn.close()

# Initialize database on startup
init_db()

# Helper function for database connections
def get_db_connection():
    try:
        conn = sqlite3.connect('users.db', timeout=20)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        raise

# JWT token required decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        try:
            token = token.split(' ')[1]  # Remove 'Bearer ' prefix
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = data['username']
        except:
            return jsonify({'message': 'Token is invalid!'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

# Try to import optional dependencies
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    logger.warning("Speech recognition not available. Voice commands will be disabled.")
    SPEECH_RECOGNITION_AVAILABLE = False

try:
    import pyttsx3
    engine = pyttsx3.init()
    logger.info("Text-to-speech engine initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize text-to-speech engine: {str(e)}")
    engine = None

# Global variables
user_name = "User"
command_history = []
reminders = {}
active_reminders = set()
ai_tips = [
    "Ask me: What's the weather like today?",
    "Try saying: Search Wikipedia for AI",
    "Say: Play music",
    "Say: What time is it?",
    "Try: Calculate 2 + 2",
    "Say: Set a reminder",
    "Try: Translate hello to Spanish"
]

# Language codes for translation
LANGUAGE_CODES = {
    'hindi': 'hindi',
    'marathi': 'marathi',
    'gujarati': 'gujarati',
    'bengali': 'bengali',
    'tamil': 'tamil',
    'telugu': 'telugu',
    'kannada': 'kannada',
    'malayalam': 'malayalam',
    'punjabi': 'punjabi',
    'urdu': 'urdu',
    'spanish': 'spanish',
    'french': 'french',
    'german': 'german',
    'italian': 'italian',
    'portuguese': 'portuguese',
    'russian': 'russian',
    'japanese': 'japanese',
    'korean': 'korean',
    'chinese': 'chinese'
}

# Translation cache to store recent translations
translation_cache = {}
CACHE_SIZE = 100  # Maximum number of translations to cache

def translate_text(text, target_lang):
    """Translate text to target language using optimized approach"""
    try:
        # Convert language name to code if it's a full name
        target_lang = target_lang.lower()
        if target_lang in LANGUAGE_CODES:
            target_lang = LANGUAGE_CODES[target_lang]
        
        # Check cache first
        cache_key = f"{text}_{target_lang}"
        if cache_key in translation_cache:
            return f"Translation: {translation_cache[cache_key]}"
        
        # Use DeepL API (faster and more accurate)
        url = "https://api-free.deepl.com/v2/translate"
        headers = {
            "Authorization": "DeepL-Auth-Key YOUR_DEEPL_API_KEY"  # Replace with your DeepL API key
        }
        data = {
            "text": [text],
            "target_lang": target_lang
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=5)
            if response.status_code == 200:
                result = response.json()
                if "translations" in result and result["translations"]:
                    translation = result["translations"][0]["text"]
                    # Cache the result
                    if len(translation_cache) >= CACHE_SIZE:
                        translation_cache.pop(next(iter(translation_cache)))
                    translation_cache[cache_key] = translation
                    return f"Translation: {translation}"
        except Exception as e:
            logger.error(f"DeepL API error: {str(e)}")
        
        # Fallback to MyMemory API if DeepL fails
        url = f"https://api.mymemory.translated.net/get?q={text}&langpair=en|{target_lang}"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if data["responseStatus"] == 200:
            translation = data['responseData']['translatedText']
            # Cache the result
            if len(translation_cache) >= CACHE_SIZE:
                translation_cache.pop(next(iter(translation_cache)))
            translation_cache[cache_key] = translation
            return f"Translation: {translation}"
            
        return "Sorry, I couldn't translate that text"
    except Exception as e:
        logger.error(f"Error in translation: {str(e)}")
        return "Sorry, I couldn't translate that text"

def calculate(expression):
    """Calculate mathematical expressions"""
    try:
        # Remove any non-mathematical characters
        expression = ''.join(c for c in expression if c.isdigit() or c in '+-*/(). ')
        result = eval(expression)
        return f"The result is {result}"
    except Exception as e:
        logger.error(f"Error in calculation: {str(e)}")
        return "Sorry, I couldn't perform that calculation"

def get_current_time():
    """Get current time in the specified timezone"""
    try:
        current_time = datetime.now(timezone)
        return current_time.strftime('%I:%M:%S %p')  # 12-hour format with AM/PM
    except Exception as e:
        logger.error(f"Error getting time: {str(e)}")
        return "Sorry, I couldn't get the current time"

def parse_time(time_str):
    """Parse time string in various formats"""
    try:
        # Try different time formats
        formats = [
            '%H:%M',      # 24-hour format (14:30)
            '%I:%M %p',   # 12-hour format with AM/PM (2:30 PM)
            '%I:%M%p',    # 12-hour format without space (2:30PM)
            '%I:%M:%S %p' # 12-hour format with seconds (2:30:00 PM)
        ]
        
        for fmt in formats:
            try:
                # Parse the time
                parsed_time = datetime.strptime(time_str.strip(), fmt)
                # Convert to 24-hour format
                return parsed_time.strftime('%H:%M')
            except ValueError:
                continue
                
        raise ValueError("Time format not recognized")
    except Exception as e:
        logger.error(f"Error parsing time: {str(e)}")
        raise

def set_reminder(user, reminder_text, time_str):
    """Set a reminder for the user"""
    try:
        # Parse the time string
        time_str = parse_time(time_str)
        reminder_time = datetime.strptime(time_str, '%H:%M').time()
        
        # Get current time in the specified timezone
        current_time = datetime.now(timezone)
        current_time = current_time.replace(tzinfo=None)  # Remove timezone info for comparison
        
        # Calculate target datetime
        target_datetime = current_time.replace(
            hour=reminder_time.hour,
            minute=reminder_time.minute,
            second=0,
            microsecond=0
        )
        
        # If the time has already passed today, schedule for tomorrow
        if target_datetime < current_time:
            target_datetime = target_datetime + timedelta(days=1)
        
        # Create a unique ID for this reminder
        reminder_id = f"{user}_{target_datetime.strftime('%Y%m%d_%H%M')}"
        
        # Store the reminder
        reminders[reminder_id] = {
            'user': user,
            'text': reminder_text,
            'datetime': target_datetime,
            'active': True
        }
        
        # Start a new thread for this reminder
        reminder_thread = threading.Thread(
            target=check_single_reminder,
            args=(reminder_id,),
            daemon=True
        )
        reminder_thread.start()
        
        # Format the response time in 12-hour format
        response_time = target_datetime.strftime('%I:%M %p')
        return f"Reminder set for {response_time}: {reminder_text}"
    except Exception as e:
        logger.error(f"Error setting reminder: {str(e)}")
        return "Sorry, I couldn't set that reminder. Please use a valid time format (e.g., '2:30 PM' or '14:30')"

def check_single_reminder(reminder_id):
    """Check and notify for a single reminder"""
    try:
        if reminder_id not in reminders:
            return
        
        reminder = reminders[reminder_id]
        target_time = reminder['datetime']
        
        while reminder['active']:
            current_time = datetime.now(timezone)
            current_time = current_time.replace(tzinfo=None)  # Remove timezone info for comparison
            
            # If it's time for the reminder
            if current_time >= target_time:
                notify_reminder(reminder_id)
                break
            
            # Sleep for a short time to prevent CPU overuse
            time.sleep(1)
    except Exception as e:
        logger.error(f"Error checking reminder {reminder_id}: {str(e)}")

def notify_reminder(reminder_id):
    """Notify user about a reminder"""
    try:
        if reminder_id not in reminders:
            return
        
        reminder = reminders[reminder_id]
        message = f"Reminder for {reminder['user']}: {reminder['text']}"
        
        # Play a sound notification
        try:
            winsound.Beep(1000, 1000)  # Frequency: 1000Hz, Duration: 1000ms
        except:
            pass  # Ignore if sound fails
        
        # Speak the reminder
        speak(message)
        
        # Remove the reminder
        del reminders[reminder_id]
        
    except Exception as e:
        logger.error(f"Error notifying reminder: {str(e)}")

def cancel_reminder(reminder_id):
    """Cancel a specific reminder"""
    if reminder_id in reminders:
        reminders[reminder_id]['active'] = False
        del reminders[reminder_id]
        return True
    return False

def check_reminders():
    """Check and run scheduled reminders"""
    try:
        schedule.run_pending()
    except Exception as e:
        logger.error(f"Error checking reminders: {str(e)}")

# Start reminder checker in background
def start_reminder_checker():
    while True:
        check_reminders()
        time.sleep(1)  # Check every second

reminder_thread = threading.Thread(target=start_reminder_checker)
reminder_thread.daemon = True
reminder_thread.start()

def speak(text):
    """Convert text to speech"""
    try:
        if engine:
            engine.say(text)
            engine.runAndWait()
        return text
    except Exception as e:
        logger.error(f"Error in text-to-speech: {str(e)}")
        return text

def get_weather(city):
    """Get weather information for a city"""
    api_key = "5b6b1206aefe5fa56d39570a34b45e14"  # OpenWeatherMap API key
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
    
    try:
        response = requests.get(url)
        data = response.json()
        if data["cod"] == 200:
            temp = data["main"]["temp"]
            desc = data["weather"][0]["description"]
            humidity = data["main"]["humidity"]
            wind_speed = data["wind"]["speed"]
            return f"Temperature in {city} is {temp}°C with {desc}. Humidity: {humidity}%, Wind Speed: {wind_speed} m/s"
        return f"Sorry, I couldn't find weather data for {city}"
    except Exception as e:
        logger.error(f"Error fetching weather data: {str(e)}")
        return "Sorry, I couldn't fetch the weather data"

def search_wikipedia(topic):
    """Search Wikipedia for a topic with improved accuracy and detail"""
    try:
        # First try to get a direct page
        try:
            page = wikipedia.page(topic, auto_suggest=True)
            summary = wikipedia.summary(topic, sentences=3)
            return f"""Here's what I found about {topic}:

{summary}

Read more: {page.url}"""
        except wikipedia.DisambiguationError as e:
            # If there are multiple matches, suggest the most relevant ones
            options = e.options[:5]  # Get top 5 options
            return f"""There are multiple topics matching '{topic}'. Here are the most relevant ones:
{', '.join(options)}

Please be more specific about which topic you're interested in."""
        except wikipedia.PageError:
            # If the exact page isn't found, try searching
            search_results = wikipedia.search(topic, results=3)
            if search_results:
                # Try to get summary of the first search result
                try:
                    summary = wikipedia.summary(search_results[0], sentences=3)
                    page = wikipedia.page(search_results[0])
                    return f"""I found this related information about {search_results[0]}:

{summary}

Read more: {page.url}"""
                except:
                    return f"""I found these related topics: {', '.join(search_results)}
Please specify which one you'd like to know more about."""
            else:
                return f"Sorry, I couldn't find any information about '{topic}'. Please try a different search term."
    except Exception as e:
        logger.error(f"Error searching Wikipedia: {str(e)}")
        return f"Sorry, I encountered an error while searching for '{topic}'. Please try again."

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

def process_command(command):
    """Process a command and return the response"""
    try:
        command = command.lower().strip()
        logger.info(f"Processing command: {command}")
        
        # Add command to history
        command_history.append({
            'command': command,
            'timestamp': datetime.now().strftime('%H:%M:%S')
        })
        
        # Process the command
        response = ""
        if "remind" in command or "reminder" in command:
            if "cancel" in command:
                # Handle cancel reminder command
                parts = command.replace("cancel reminder", "").replace("cancel remind", "").strip()
                if parts:
                    # Try to find and cancel the reminder
                    for reminder_id, reminder in list(reminders.items()):
                        if parts.lower() in reminder['text'].lower():
                            if cancel_reminder(reminder_id):
                                response = f"Cancelled reminder: {reminder['text']}"
                                break
                    if not response:
                        response = "No matching reminder found to cancel"
                else:
                    response = "Please specify which reminder to cancel"
            else:
                # Handle set reminder command
                parts = command.replace("remind me", "").replace("set reminder", "").strip().split("at")
                if len(parts) == 2:
                    reminder_text = parts[0].strip()
                    time_str = parts[1].strip()
                    response = set_reminder(user_name, reminder_text, time_str)
                else:
                    response = "Please specify reminder text and time. Example: 'remind me to call mom at 15:30'"
        elif any(word in command for word in ["weather", "temperature", "forecast"]):
            city = command.replace("weather in", "").replace("temperature in", "").replace("forecast in", "").strip()
            if not city:
                response = "Please specify a city name. For example: 'weather in London'"
            else:
                response = get_weather(city)
        elif any(word in command for word in ["wikipedia", "search", "look up", "who is", "what is"]):
            # Extract the topic from various command formats
            topic = command
            for prefix in ["search wikipedia for", "look up", "who is", "what is"]:
                if prefix in command:
                    topic = command.replace(prefix, "").strip()
                    break
            if not topic:
                response = "Please specify a topic to search. For example: 'search wikipedia for AI' or 'who is Albert Einstein'"
            else:
                response = search_wikipedia(topic)
        elif any(word in command for word in ["time", "clock", "hour"]):
            response = get_current_time()
        elif "calculate" in command or "compute" in command:
            expression = command.replace("calculate", "").replace("compute", "").strip()
            response = calculate(expression)
        elif "translate" in command:
            parts = command.replace("translate", "").strip().split("to")
            if len(parts) == 2:
                text = parts[0].strip()
                target_lang = parts[1].strip()
                response = translate_text(text, target_lang)
            else:
                supported_langs = ", ".join(LANGUAGE_CODES.keys())
                response = f"Please specify text and target language. Example: 'translate hello to hindi'\nSupported languages: {supported_langs}"
        elif "hello" in command or "hi" in command:
            response = f"Hello! I'm your AI assistant. I can help you with weather, calculations, translations, and more. How can I assist you today?"
        elif "help" in command:
            supported_langs = ", ".join(LANGUAGE_CODES.keys())
            response = f"""I can help you with:
- Weather information
- Wikipedia searches (try: 'who is Albert Einstein' or 'what is AI')
- Current time
- Mathematical calculations
- Text translation (supported languages: {supported_langs})
- Setting reminders
Just ask me about any of these!"""
        else:
            response = "I'm not sure how to help with that. Try asking about weather, calculations, or say 'help' for more options."
        
        return {
            'response': response,
            'history': command_history[-5:],  # Return last 5 commands
            'suggestions': random.sample(ai_tips, 3)  # Return 3 random suggestions
        }
    except Exception as e:
        logger.error(f"Error processing command: {str(e)}")
        return {
            'error': 'Sorry, there was an error processing your command. Please try again.',
            'history': command_history[-5:],
            'suggestions': random.sample(ai_tips, 3)
        }

@app.route('/api/process_command', methods=['POST'])
def handle_command():
    """Handle incoming commands"""
    try:
        data = request.json
        if not data or 'command' not in data:
            return jsonify({'error': 'No command provided'}), 400

        command = data['command'].lower()
        
        # Process the command
        response = ""
        if "remind" in command or "reminder" in command:
            if "cancel" in command:
                # Handle cancel reminder command
                parts = command.replace("cancel reminder", "").replace("cancel remind", "").strip()
                if parts:
                    # Try to find and cancel the reminder
                    for reminder_id, reminder in list(reminders.items()):
                        if parts.lower() in reminder['text'].lower():
                            if cancel_reminder(reminder_id):
                                response = f"Cancelled reminder: {reminder['text']}"
                                break
                    if not response:
                        response = "No matching reminder found to cancel"
                else:
                    response = "Please specify which reminder to cancel"
            else:
                # Handle set reminder command
                parts = command.replace("remind me", "").replace("set reminder", "").strip().split("at")
                if len(parts) == 2:
                    reminder_text = parts[0].strip()
                    time_str = parts[1].strip()
                    response = set_reminder(user_name, reminder_text, time_str)
                else:
                    response = "Please specify reminder text and time. Example: 'remind me to call mom at 15:30'"
        elif any(word in command for word in ["weather", "temperature", "forecast"]):
            city = command.replace("weather in", "").replace("temperature in", "").replace("forecast in", "").strip()
            if not city:
                response = "Please specify a city name. For example: 'weather in London'"
            else:
                response = get_weather(city)
        elif any(word in command for word in ["wikipedia", "search", "look up", "who is", "what is"]):
            # Extract the topic from various command formats
            topic = command
            for prefix in ["search wikipedia for", "look up", "who is", "what is"]:
                if prefix in command:
                    topic = command.replace(prefix, "").strip()
                    break
            if not topic:
                response = "Please specify a topic to search. For example: 'search wikipedia for AI' or 'who is Albert Einstein'"
            else:
                response = search_wikipedia(topic)
        elif any(word in command for word in ["time", "clock", "hour"]):
            response = get_current_time()
        elif "calculate" in command or "compute" in command:
            expression = command.replace("calculate", "").replace("compute", "").strip()
            response = calculate(expression)
        elif "translate" in command:
            parts = command.replace("translate", "").strip().split("to")
            if len(parts) == 2:
                text = parts[0].strip()
                target_lang = parts[1].strip()
                response = translate_text(text, target_lang)
            else:
                supported_langs = ", ".join(LANGUAGE_CODES.keys())
                response = f"Please specify text and target language. Example: 'translate hello to hindi'\nSupported languages: {supported_langs}"
        elif "hello" in command or "hi" in command:
            response = f"Hello! I'm your AI assistant. I can help you with weather, calculations, translations, and more. How can I assist you today?"
        elif "help" in command:
            supported_langs = ", ".join(LANGUAGE_CODES.keys())
            response = f"""I can help you with:
- Weather information
- Wikipedia searches (try: 'who is Albert Einstein' or 'what is AI')
- Current time
- Mathematical calculations
- Text translation (supported languages: {supported_langs})
- Setting reminders
Just ask me about any of these!"""
        else:
            response = "I'm not sure how to help with that. Try asking about weather, calculations, or say 'help' for more options."
        
        return jsonify({
            'response': response,
            'history': command_history[-5:],  # Return last 5 commands
            'suggestions': random.sample(ai_tips, 3)  # Return 3 random suggestions
        })
    except Exception as e:
        logger.error(f"Error handling command: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'history': command_history[-5:] if command_history else [],
            'suggestions': random.sample(ai_tips, 3)
        }), 500

@app.route('/api/get_tip', methods=['GET'])
def get_tip():
    """Get a random AI tip"""
    try:
        tip = random.choice(ai_tips)
        logger.info(f"Generated tip: {tip}")
        return jsonify({'tip': tip})
    except Exception as e:
        logger.error(f"Error getting tip: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/get_time', methods=['GET'])
def get_current_time_api():
    """Get current time API endpoint"""
    try:
        current_time = get_current_time()
        return jsonify({
            'time': current_time,
            'timezone': TIMEZONE
        })
    except Exception as e:
        logger.error(f"Error getting time: {str(e)}")
        return jsonify({'error': 'Failed to get current time'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'speech_recognition': SPEECH_RECOGNITION_AVAILABLE,
        'text_to_speech': engine is not None
    })

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        if not username or not email or not password:
            return jsonify({'error': 'All fields are required'}), 400

        hashed_password = generate_password_hash(password)
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                     (username, email, hashed_password))
            conn.commit()
            return jsonify({'message': 'User registered successfully'}), 201
        except sqlite3.IntegrityError as e:
            if 'UNIQUE constraint failed: users.username' in str(e):
                return jsonify({'error': 'Username already exists'}), 400
            elif 'UNIQUE constraint failed: users.email' in str(e):
                return jsonify({'error': 'Email already exists'}), 400
            else:
                raise
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({'error': 'Registration failed'}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400

        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute('SELECT * FROM users WHERE username = ?', (username,))
            user = c.fetchone()
            
            if not user or not check_password_hash(user['password'], password):
                return jsonify({'error': 'Invalid username or password'}), 401

            # Generate JWT token
            token = jwt.encode({
                'username': username,
                'exp': datetime.utcnow() + timedelta(hours=24)
            }, app.config['SECRET_KEY'])

            return jsonify({
                'message': 'Login successful',
                'token': token,
                'username': username
            }), 200
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500

@app.route('/api/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('SELECT username, email, created_at FROM users WHERE username = ?', (current_user,))
        user = c.fetchone()
        conn.close()

        if not user:
            return jsonify({'error': 'User not found'}), 404

        return jsonify({
            'username': user[0],
            'email': user[1],
            'created_at': user[2]
        }), 200
    except Exception as e:
        logger.error(f"Profile error: {str(e)}")
        return jsonify({'error': 'Failed to get profile'}), 500

@app.route('/api/users', methods=['GET'])
@token_required
def get_users(current_user):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT id, username, email, created_at FROM users')
    users = c.fetchall()
    conn.close()
    
    return jsonify({
        'users': [{
            'id': user[0],
            'username': user[1],
            'email': user[2],
            'created_at': user[3]
        } for user in users]
    })

@app.route('/api/debug/db-structure', methods=['GET'])
def get_db_structure():
    """Get database structure (for development purposes only)"""
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        
        # Get table information
        c.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = c.fetchall()
        
        structure = {}
        for table in tables:
            table_name = table[0]
            c.execute(f"PRAGMA table_info({table_name});")
            columns = c.fetchall()
            structure[table_name] = [{
                'name': col[1],
                'type': col[2],
                'notnull': col[3],
                'default': col[4],
                'pk': col[5]
            } for col in columns]
        
        conn.close()
        return jsonify(structure)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    try:
        logger.info("Starting Flask application...")
        app.run(debug=True, port=5000)
    except Exception as e:
        logger.error(f"Failed to start Flask application: {str(e)}") 

        