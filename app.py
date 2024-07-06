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
import uuid

from job_matcher import JobMatcher, Applicant, Job as MatcherJob

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

class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    additional_info = db.relationship('CompanyAdditionalInfo', backref='company', lazy='dynamic')

class CompanyAdditionalInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    field_name = db.Column(db.String(100), nullable=False)
    field_value = db.Column(db.Text, nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)


class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    employer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    unique_link = db.Column(db.String(36), unique=True, nullable=False)

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    applicant_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    application_date = db.Column(db.DateTime, default=datetime.utcnow)

class CompanyForm(FlaskForm):
    name = StringField('Company Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Company Description')
    submit = SubmitField('Save')

class AdditionalInfoForm(FlaskForm):
    field_name = StringField('Field Name', validators=[DataRequired(), Length(max=100)])
    field_value = TextAreaField('Field Value', validators=[DataRequired()])
    submit = SubmitField('Add')
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
    jobs = Job.query.all()
    return render_template('applicant_dashboard.html', jobs=jobs)

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
        unique_link = str(uuid.uuid4())
        new_job = Job(title=form.title.data, description=form.description.data, employer_id=session['user_id'], unique_link=unique_link)
        db.session.add(new_job)
        db.session.commit()
        flash('Job created successfully!', 'success')
        return redirect(url_for('job_link', unique_link=unique_link))
    return render_template('create_job.html', form=form)

@app.route('/company_profile', methods=['GET', 'POST'])
@login_required
def company_profile():
    if session.get('role') != 'employer':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))
    
    company = Company.query.filter_by(user_id=session['user_id']).first()
    form = CompanyForm(obj=company)
    add_info_form = AdditionalInfoForm()

    if form.validate_on_submit():
        if company:
            company.name = form.name.data
            company.description = form.description.data
        else:
            company = Company(name=form.name.data, description=form.description.data, user_id=session['user_id'])
            db.session.add(company)
        db.session.commit()
        flash('Company profile updated successfully!', 'success')
        return redirect(url_for('company_profile'))

    if add_info_form.validate_on_submit():
        new_info = CompanyAdditionalInfo(
            field_name=add_info_form.field_name.data,
            field_value=add_info_form.field_value.data,
            company_id=company.id
        )
        db.session.add(new_info)
        db.session.commit()
        flash('Additional information added successfully!', 'success')
        return redirect(url_for('company_profile'))

    additional_info = CompanyAdditionalInfo.query.filter_by(company_id=company.id).all() if company else []
    return render_template('company_profile.html', form=form, add_info_form=add_info_form, company=company, additional_info=additional_info)


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

@app.route('/job/<unique_link>')
def job_link(unique_link):
    job = Job.query.filter_by(unique_link=unique_link).first_or_404()
    if 'user_id' not in session:
        session['next'] = url_for('job_link', unique_link=unique_link)
        return redirect(url_for('login'))
    if session.get('role') != 'applicant':
        flash('Only applicants can apply for jobs.', 'warning')
        return redirect(url_for('home'))
    return render_template('job_application.html', job=job)


job_matcher = JobMatcher()

@app.route('/chat', methods=['POST'])
@login_required
def chat():
    if session.get('role') != 'applicant':
        return jsonify({"error": "Access denied"}), 403
    
    data = request.json
    chat_history = data.get('history', '')
    user_input = data.get('user_input', '')
    job_id = data.get('job_id')
    
    job = Job.query.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    job_details = f"Job Title: {job.title}\nDescription: {job.description}"
    
    response, assessment = tool.process_interaction(chat_history, user_input, job_details)
    
    if assessment.get('application_complete', False):
        applicant = Applicant(id=session['user_id'], profile=assessment.get('applicant_profile', ''))
        matcher_job = MatcherJob(id=job.id, title=job.title, description=job.description)
        
        match_result = job_matcher.match_job_applicant(matcher_job, applicant)
        
        if match_result['score'] > 0.7:  # You can adjust this threshold
            new_application = Application(applicant_id=session['user_id'], job_id=job.id)
            db.session.add(new_application)
            db.session.commit()
            status = f"Your application has been submitted successfully. The employer will be notified. Match score: {match_result['score']:.2f}"
        else:
            all_jobs = [MatcherJob(id=j.id, title=j.title, description=j.description) for j in Job.query.all()]
            similar_jobs = job_matcher.find_similar_jobs(matcher_job, applicant, all_jobs)
            status = f"Based on our assessment (match score: {match_result['score']:.2f}), we have some other job recommendations that might be a better fit."
            return jsonify({
                'response': response, 
                'status': status, 
                'similar_jobs': [{'id': j['job'].id, 'title': j['job'].title, 'score': j['score']} for j in similar_jobs[:3]]
            })
    
    return jsonify({'response': response, 'status': status if 'status' in locals() else None})

@app.route('/view_applicants/<int:job_id>')
@login_required
def view_applicants(job_id):
    if session.get('role') != 'employer':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))
    
    job = Job.query.get_or_404(job_id)
    if job.employer_id != session['user_id']:
        flash('Access denied.', 'danger')
        return redirect(url_for('employer_dashboard'))
    
    applications = Application.query.filter_by(job_id=job_id).all()
    applicants = []
    for application in applications:
        applicant = User.query.get(application.applicant_id)
        applicants.append({
            'id': applicant.id,
            'email': applicant.email,
            'status': application.status,
            'application_date': application.application_date
        })
    
    return render_template('view_applicants.html', job=job, applicants=applicants)

@app.route('/view_assessment/<int:job_id>/<int:applicant_id>')
@login_required
def view_assessment(job_id, applicant_id):
    if session.get('role') != 'employer':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))
    
    job = Job.query.get_or_404(job_id)
    if job.employer_id != session['user_id']:
        flash('Access denied.', 'danger')
        return redirect(url_for('employer_dashboard'))
    
    applicant = User.query.get_or_404(applicant_id)
    application = Application.query.filter_by(job_id=job_id, applicant_id=applicant_id).first_or_404()
    
    # Here you would typically fetch or generate the assessment details
    # For now, we'll just use placeholder data
    assessment = {
        'score': 0.75,
        'reasoning': 'This is a placeholder assessment reasoning.',
        'skill_similarity': 0.8
    }
    
    return render_template('view_assessment.html', job=job, applicant=applicant, application=application, assessment=assessment)

if __name__ == '__main__':
    app.run(debug=True)