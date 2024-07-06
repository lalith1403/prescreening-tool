import os
from dotenv import load_dotenv
import dspy
from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import uuid
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///prescreening.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)

class PrescreeningTool:
    def __init__(self):
        self.lm = dspy.OpenAI(model="gpt-3.5-turbo")
        dspy.settings.configure(lm=self.lm)
        self.generate_response = dspy.ChainOfThought("history: str, user_input: str, job_details: str -> response: str")

    def process_interaction(self, history, user_input, job_details):
        response = self.generate_response(history=history, user_input=user_input, job_details=job_details)
        return response.response

tool = PrescreeningTool()

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Register')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        
        if User.query.filter_by(email=email).first():
            return render_template('register.html', form=form, error="Email already registered")
        
        new_user = User(email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id'] = str(uuid.uuid4())
            return redirect(url_for('chat'))
        return render_template('login.html', form=form, error="Invalid credentials")
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('home'))

@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    if request.method == 'POST':
        data = request.json
        history = data.get('history', '')
        user_input = data.get('user_input', '')
        
        # For simplicity, we're using a default job. In a real application, you'd select the appropriate job.
        job = Job.query.first()
        if not job:
            return jsonify({"error": "No jobs available"}), 404
        
        job_details = f"Job Title: {job.title}\nDescription: {job.description}"
        
        response = tool.process_interaction(history, user_input, job_details)
        
        return jsonify({'response': response})
    return render_template('chat.html')

@app.route('/job', methods=['POST'])
@login_required
def create_job():
    data = request.json
    title = data.get('title')
    description = data.get('description')
    
    new_job = Job(title=title, description=description)
    db.session.add(new_job)
    db.session.commit()
    
    return jsonify({"message": "Job created successfully", "job_id": new_job.id}), 201

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)