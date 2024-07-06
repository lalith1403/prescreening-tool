import os
from dotenv import load_dotenv
import dspy
from flask import Flask, request, jsonify, session, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo
from flask_migrate import Migrate

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///prescreening.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='applicant')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    employer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class PrescreeningTool:
    def __init__(self):
        try:
            self.lm = dspy.OpenAI(model="gpt-3.5-turbo", api_key=os.environ.get('OPENAI_API_KEY'))
            dspy.settings.configure(lm=self.lm)
            self.generate_response = dspy.ChainOfThought("history: str, user_input: str, job_details: str -> response: str")
        except Exception as e:
            app.logger.error(f"Error initializing PrescreeningTool: {str(e)}")
            raise

    def process_interaction(self, history, user_input, job_details):
        try:
            response = self.generate_response(history=history, user_input=user_input, job_details=job_details)
            return response.response
        except Exception as e:
            app.logger.error(f"Error in process_interaction: {str(e)}")
            return "I'm sorry, but I encountered an error while processing your request. Please try again later."
        
tool = PrescreeningTool()

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Role', choices=[('applicant', 'Applicant'), ('employer', 'Employer')])
    submit = SubmitField('Register')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
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
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash('Email already registered. Please use a different email.', 'danger')
            return render_template('register.html', form=form)
        
        new_user = User(email=form.email.data, role=form.role.data)
        new_user.set_password(form.password.data)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            session['user_id'] = user.id
            session['role'] = user.role
            flash('Login successful!', 'success')
            return redirect(url_for('chat'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('role', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    if request.method == 'POST':
        try:
            data = request.json
            history = data.get('history', '')
            user_input = data.get('user_input', '')
            
            # Create a sample job for demonstration purposes
            sample_job = Job(
                title="Software Developer",
                description="We are looking for a skilled software developer to join our team. The ideal candidate should have experience with Python, Flask, and database management.",
                employer_id=1  # Assuming an employer with ID 1 exists
            )
            db.session.add(sample_job)
            db.session.commit()

            # Use the sample job for the chat interaction
            job = sample_job
            if not job:
                return jsonify({"error": "No jobs available"}), 404
            
            job_details = f"Job Title: {job.title}\nDescription: {job.description}"
            
            response = tool.process_interaction(history, user_input, job_details)
            
            return jsonify({'response': response})
        except Exception as e:
            app.logger.error(f"Error in chat processing: {str(e)}")
            return jsonify({"error": "An error occurred while processing your request."}), 500
    return render_template('chat.html')

@app.route('/job', methods=['POST'])
@login_required
def create_job():
    if session.get('role') != 'employer':
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.json
    title = data.get('title')
    description = data.get('description')
    
    new_job = Job(title=title, description=description, employer_id=session['user_id'])
    db.session.add(new_job)
    db.session.commit()
    
    return jsonify({"message": "Job created successfully", "job_id": new_job.id}), 201

if __name__ == '__main__':
    app.run(debug=True)