import os
from dotenv import load_dotenv
import dspy
from flask import Flask, request, jsonify, session
from functools import wraps
import uuid

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management

class PrescreeningTool:
    def __init__(self):
        self.lm = dspy.OpenAI(model="gpt-3.5-turbo")
        dspy.settings.configure(lm=self.lm)
        self.generate_response = dspy.ChainOfThought("history: str, user_input: str, job_details: str -> response: str")

    def process_interaction(self, history, user_input, job_details):
        response = self.generate_response(history=history, user_input=user_input, job_details=job_details)
        return response.response

tool = PrescreeningTool()

# Simulated user database (replace with a real database in production)
users = {
    "user1@example.com": "password1",
    "user2@example.com": "password2"
}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    if email in users and users[email] == password:
        session['user_id'] = str(uuid.uuid4())
        return jsonify({"message": "Login successful"}), 200
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({"message": "Logout successful"}), 200

@app.route('/chat', methods=['POST'])
@login_required
def chat():
    data = request.json
    history = data.get('history', '')
    user_input = data.get('user_input', '')
    job_details = data.get('job_details', '')  # New parameter
    
    response = tool.process_interaction(history, user_input, job_details)
    
    return jsonify({'response': response})

@app.route('/')
def home():
    return "Prescreening Tool is running!"

if __name__ == '__main__':
    app.run(debug=True)