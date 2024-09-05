from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor
import subprocess
import json
import os
import random
import speech_recognition as sr
import tempfile
import re

app = Flask(__name__)
CORS(app)

executor = ThreadPoolExecutor(max_workers=3)
response_cache = {}

# Load intents
with open('intents.json', 'r') as file:
    intents = json.load(file)['intents']

# Emotion mapping
emotion_mapping = {
    'greeting': 'happy',
    'goodbye': 'sad',
    # ... add the rest of the mappings
    'neutral': 'neutral'
}

class MistralAssistant:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.wake_words = ["luna", "danna"]
        self.response_cache = {}
        self.temp_dir = tempfile.mkdtemp()
        self.executor = ThreadPoolExecutor()

    def listen_for_speech(self):
        with sr.Microphone() as source:
            print("Listening...")
            audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
        try:
            text = self.recognizer.recognize_google(audio)
            return text
        except sr.UnknownValueError:
            return "Sorry, I couldn't understand that."
        except sr.RequestError:
            return "Sorry, there was an error with the speech recognition service."

    def generate_response(self, prompt):
        if prompt in self.response_cache:
            return self.response_cache[prompt]

        try:
            result = subprocess.run(
                ['ollama', 'run', 'phi3', prompt],
                capture_output=True,
                text=True,
                check=True,
                encoding='utf-8',
                timeout=120
            )

            response = result.stdout.strip()
            response = re.sub(r'failed to get console mode for std(out|err):.*\n?', '', response).strip()

            if not response:
                return "I'm sorry, I couldn't generate a proper response. How else can I assist you?"

            self.response_cache[prompt] = response
            return response
        except subprocess.TimeoutExpired:
            print("Mistral response timed out after 30 seconds")
            return "I'm sorry, but I couldn't generate a response in time. Please try again."
        except subprocess.CalledProcessError as e:
            print(f"Error running Mistral: {e}")
            print(f"Stderr: {e.stderr}")
            return "Sorry, there was an error generating a response. Please check if Ollama and Mistral are set up correctly."
        except Exception as e:
            print(f"Unexpected error: {e}")
            return "An unexpected error occurred. Please try again."

    def cleanup(self):
        for file in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, file))
        os.rmdir(self.temp_dir)
        self.executor.shutdown()

# Flask Routes

@app.route('/')
def index():
    return render_template('emotisphere.html')

@app.route('/send_message', methods=['POST'])
def send_message():
    user_message = request.json['message']
    intent = detect_intent(user_message)
    emotion = emotion_mapping.get(intent, 'neutral')
    
    # Generate response using the assistant
    assistant = MistralAssistant()
    response = assistant.generate_response(user_message)

    return jsonify({'response': response, 'emotion': emotion})

@app.route('/start_listening', methods=['POST'])
def start_listening():
    assistant = MistralAssistant()
    try:
        transcript = assistant.listen_for_speech()
        return jsonify({'transcript': transcript})
    except Exception as e:
        return jsonify({'error': str(e)})

def detect_intent(message):
    for intent in intents:
        for pattern in intent['patterns']:
            if pattern.lower() in message.lower():
                return intent['tag']
    return 'neutral'

if __name__ == "__main__":
    assistant = MistralAssistant()
    app.run(debug=True, use_reloader=False)
    assistant.cleanup()
nup()