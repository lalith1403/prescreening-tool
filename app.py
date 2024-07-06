import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify, session, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length
from flask_migrate import Migrate
from chatbot_modules.base_module import ModularPrescreeningTool
from job_matcher import JobMatcher
from sqlalchemy.sql import func

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

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    applicant_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    application_date = db.Column(db.DateTime, default=datetime.utcnow)

tool = ModularPrescreeningTool()
job_matcher = JobMatcher()

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8, max=80)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Role', choices=[('applicant', 'Applicant'), ('employer', 'Employer')])
    submit = SubmitField('Register')

class JobForm(FlaskForm):
    title = StringField('Job Title', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Job Description', validators=[DataRequired()])
    submit = SubmitField('Submit')

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
            if user.role == 'employer':
                return redirect(url_for('employer_dashboard'))
            else:
                return redirect(url_for('applicant_dashboard'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('role', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/applicant_dashboard')
@login_required
def applicant_dashboard():
    if session.get('role') != 'applicant':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))
    return render_template('applicant_dashboard.html')

@app.route('/employer_dashboard')
@login_required
def employer_dashboard():
    if session.get('role') != 'employer':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))
    jobs = Job.query.filter_by(employer_id=session['user_id']).all()
    return render_template('employer_dashboard.html', jobs=jobs)

@app.route('/create_job', methods=['GET', 'POST'])
@login_required
def create_job():
    if session.get('role') != 'employer':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))
    
    form = JobForm()
    if form.validate_on_submit():
        new_job = Job(title=form.title.data, description=form.description.data, employer_id=session['user_id'])
        db.session.add(new_job)
        db.session.commit()
        flash('Job created successfully!', 'success')
        return redirect(url_for('employer_dashboard'))
    return render_template('create_job.html', form=form)

@app.route('/edit_job/<int:job_id>', methods=['GET', 'POST'])
@login_required
def edit_job(job_id):
    if session.get('role') != 'employer':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))
    
    job = Job.query.get_or_404(job_id)
    if job.employer_id != session['user_id']:
        flash('Access denied.', 'danger')
        return redirect(url_for('employer_dashboard'))
    
    form = JobForm(obj=job)
    if form.validate_on_submit():
        job.title = form.title.data
        job.description = form.description.data
        db.session.commit()
        flash('Job updated successfully!', 'success')
        return redirect(url_for('employer_dashboard'))
    return render_template('edit_job.html', form=form, job=job)

@app.route('/delete_job/<int:job_id>', methods=['POST'])
@login_required
def delete_job(job_id):
    if session.get('role') != 'employer':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))
    
    job = Job.query.get_or_404(job_id)
    if job.employer_id != session['user_id']:
        flash('Access denied.', 'danger')
        return redirect(url_for('employer_dashboard'))
    
    db.session.delete(job)
    db.session.commit()
    flash('Job deleted successfully!', 'success')
    return redirect(url_for('employer_dashboard'))

@app.route('/chat', methods=['POST'])
@login_required
def chat():
    if session.get('role') != 'applicant':
        return jsonify({"error": "Access denied"}), 403
    
    data = request.json
    history = data.get('history', '')
    user_input = data.get('user_input', '')
    
    # Fetch a random job for demonstration purposes
    # In a real application, you might want to select a specific job or use the user's application details
    job = Job.query.order_by(func.random()).first()
    
    if job:
        job_details = f"Job Title: {job.title}\nDescription: {job.description}"
    else:
        job_details = "No job details available"
    
    response = tool.process_interaction(history, user_input, job_details)
    
    return jsonify({'response': response})

if __name__ == '__main__':
    app.run(debug=True)