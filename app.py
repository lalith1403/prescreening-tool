import os
from dotenv import load_dotenv
import dspy
from flask import Flask, request, jsonify

load_dotenv()

app = Flask(__name__)

class PrescreeningTool:
    def __init__(self):
        self.lm = dspy.OpenAI(model="gpt-3.5-turbo")
        dspy.settings.configure(lm=self.lm)
        self.generate_response = dspy.ChainOfThought("history: str, user_input: str -> response: str")

    def process_interaction(self, history, user_input):
        response = self.generate_response(history=history, user_input=user_input)
        return response.response

tool = PrescreeningTool()

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    history = data.get('history', '')
    user_input = data.get('user_input', '')
    
    response = tool.process_interaction(history, user_input)
    
    return jsonify({'response': response})

@app.route('/')
def home():
    return "Prescreening Tool is running!"

if __name__ == '__main__':
    app.run(debug=True)