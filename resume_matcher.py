from flask import Flask, request, render_template, redirect, url_for, flash, send_file
import sqlite3
import PyPDF2
from sentence_transformers import SentenceTransformer, util
import io
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import re
import html
import logging
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import os
import requests
from collections import Counter
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a secure secret key

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    try:
        conn = sqlite3.connect('matches.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, username FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        if user:
            return User(user[0], user[1])
    except Exception as e:
        logger.error(f"Error loading user: {str(e)}")
    return None

# Initialize the database
init_db()

# Initialize the NLP model
try:
    logger.info("Initializing sentence-transformers model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    logger.info("Model initialized successfully")
except Exception as e:
    logger.error(f"Error initializing model: {str(e)}")
    raise

# Constants
MAX_TEXT_LENGTH = 10000  # ~2000 words
MAX_PDF_SIZE = 5 * 1024 * 1024  # 5MB
MAX_SUGGESTIONS = 5

# Hunter API configuration
HUNTER_API_KEY = os.environ.get('HUNTER_API_KEY', 'your-api-key-here')
HUNTER_API_URL = 'https://api.hunter.io/v2/email-verifier'
ADZUNA_APP_ID = os.environ.get('ADZUNA_APP_ID', 'your-app-id-here')
ADZUNA_API_KEY = os.environ.get('ADZUNA_API_KEY', 'your-api-key-here')
ADZUNA_API_URL = 'https://api.adzuna.com/v1/api/jobs/us/search/1'

def init_db():
    try:
        conn = sqlite3.connect('matches.db')
        cursor = conn.cursor()
        
        # Drop existing tables
        cursor.execute('DROP TABLE IF EXISTS submissions')
        cursor.execute('DROP TABLE IF EXISTS users')
        
        # Create users table
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL
            )
        ''')
        
        # Create submissions table with user_id foreign key and created_at
        cursor.execute('''
            CREATE TABLE submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                resume_text TEXT NOT NULL,
                job_desc TEXT NOT NULL,
                score REAL,
                matching_keywords TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        
        conn.commit()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise
    finally:
        conn.close()

def sanitize_text(text):
    """Sanitize text input to prevent XSS"""
    return html.escape(text)

def truncate_text(text):
    """Truncate text to prevent performance issues"""
    return text[:MAX_TEXT_LENGTH] if len(text) > MAX_TEXT_LENGTH else text

def extract_keywords(text):
    # Sanitize and truncate input
    text = sanitize_text(truncate_text(text))
    
    # Convert to lowercase and handle special cases
    text = text.lower()
    text = text.replace('node.js', 'nodejs')
    text = text.replace('express.js', 'expressjs')
    text = text.replace('dev ops', 'devops')
    text = text.replace('dev-ops', 'devops')
    text = text.replace('devops engineer', 'devops engineer')
    
    # Tokenize
    words = word_tokenize(text)
    
    # Remove stopwords and non-alphabetic tokens
    stop_words = set(stopwords.words('english'))
    # Add common words that shouldn't be considered as keywords
    stop_words.update(['experience', 'year', 'years', 'skill', 'skills', 'strong',
                      'description', 'candidate', 'looking', 'ideal', 'job',
                      'knowledge', 'familiarity', 'high', 'control', 'seeking',
                      'with'])
    
    # Define technical terms that should always be considered
    technical_terms = {
        # Job Titles
        'developer', 'engineer', 'architect', 'devops', 'sre', 'administrator',
        'lead', 'senior', 'junior', 'fullstack', 'frontend', 'backend',
        
        # Programming Languages
        'python', 'javascript', 'java', 'typescript', 'ruby', 'php', 'scala', 'kotlin', 'swift',
        
        # Web Technologies
        'react', 'angular', 'vue', 'nodejs', 'expressjs', 'django', 'flask', 'fastapi',
        'spring', 'hibernate', 'jquery', 'bootstrap', 'tailwind', 'sass', 'less',
        'webpack', 'babel', 'html', 'css',
        
        # DevOps & Infrastructure
        'docker', 'kubernetes', 'jenkins', 'circleci', 'travis', 'gitlab', 'github',
        'aws', 'azure', 'gcp', 'terraform', 'ansible', 'puppet', 'chef', 'nginx',
        'apache', 'container', 'microservices', 'serverless', 'lambda',
        'ci', 'cd', 'cicd', 'infrastructure', 'orchestration',
        
        # Databases
        'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch', 'dynamodb',
        'cassandra', 'mariadb', 'oracle',
        
        # Operating Systems & Tools
        'linux', 'unix', 'windows', 'macos', 'git', 'svn', 'mercurial',
        
        # API & Architecture
        'restful', 'graphql', 'api', 'apis', 'soap', 'microservice',
        
        # Cloud & Infrastructure
        'cloud', 'iaas', 'paas', 'saas', 'virtualization', 'containerization',
        
        # UI/UX
        'material', 'ui', 'ux', 'responsive', 'mobile', 'cross-platform',
        'accessibility', 'wcag', 'usability',
        
        # Security
        'oauth', 'jwt', 'authentication', 'authorization', 'security',
        
        # Testing
        'junit', 'pytest', 'jest', 'selenium', 'cypress', 'testing'
    }
    
    # Extract keywords
    keywords = []
    i = 0
    while i < len(words):
        # Clean the current word
        word = words[i].strip('.,()[]{}')
        
        # Skip if word is too short or in stop words
        if len(word) <= 2 or word in stop_words:
            i += 1
            continue
        
        # Try to match two-word technical terms
        if i < len(words) - 1:
            two_words = word + ' ' + words[i + 1].strip('.,()[]{}')
            if two_words in technical_terms:
                keywords.append(two_words)
                i += 2
                continue
        
        # Handle technical terms
        if word in technical_terms:
            keywords.append(word)
            i += 1
            continue
        
        # Handle compound terms
        if '.' in word or '-' in word:
            parts = word.replace('-', '.').split('.')
            if all(len(p) > 2 for p in parts):
                keywords.extend(parts)
            i += 1
            continue
        
        # Handle regular words
        if word.isalpha() and len(word) > 2:
            keywords.append(word)
        i += 1
    
    # Get unique keywords while preserving order
    seen = set()
    unique_keywords = [x for x in keywords if not (x in seen or seen.add(x))]
    
    return set(unique_keywords)

def get_important_keywords(text):
    """Extract important keywords that should be considered for matching"""
    # Sanitize and truncate input
    text = sanitize_text(truncate_text(text))
    
    # Tokenize and convert to lowercase
    words = word_tokenize(text.lower())
    
    # Remove stopwords and non-alphabetic tokens
    stop_words = set(stopwords.words('english'))
    # Add common words that shouldn't be considered as important keywords
    stop_words.update(['experience', 'year', 'years', 'skill', 'skills', 'strong',
                      'description', 'candidate', 'looking', 'ideal', 'job',
                      'knowledge', 'familiarity', 'high', 'control', 'match',
                      'moderate', 'version', 'proficiency'])
    
    # Define technical terms that should always be considered
    technical_terms = {
        'python', 'javascript', 'java', 'react', 'angular', 'vue', 'node', 'express',
        'django', 'flask', 'fastapi', 'spring', 'hibernate', 'docker', 'kubernetes',
        'jenkins', 'circleci', 'git', 'aws', 'azure', 'gcp', 'sql', 'mysql',
        'postgresql', 'mongodb', 'redis', 'elasticsearch', 'linux', 'unix', 'windows',
        'restful', 'graphql', 'api', 'apis', 'ci', 'cd', 'devops', 'terraform',
        'ansible', 'puppet', 'chef', 'nginx', 'apache', 'kubernetes', 'docker',
        'container', 'microservices', 'serverless', 'lambda', 'sass', 'less',
        'webpack', 'babel', 'typescript', 'jquery', 'bootstrap', 'tailwind',
        'material', 'ui', 'ux', 'responsive', 'mobile', 'cross-platform'
    }
    
    # Extract words that are either technical terms or meet our criteria
    important_keywords = []
    for word in words:
        word = word.strip('.,()[]{}')
        if (word in technical_terms or 
            (word.isalpha() and 
             len(word) > 2 and 
             word not in stop_words and
             not any(common in word for common in ['ing', 'ed', 'ly']))):
            important_keywords.append(word)
    
    return set(important_keywords)

def highlight_keywords(text, keywords):
    """Highlight keywords in text while properly escaping HTML"""
    # Sanitize input
    text = sanitize_text(text)
    
    # Create a regex pattern for the keywords
    pattern = r'\b(' + '|'.join(re.escape(k) for k in keywords) + r')\b'
    
    # Replace keywords with highlighted version, but escape HTML first
    escaped_text = html.escape(text)
    highlighted_text = re.sub(
        pattern,
        lambda m: f'<span class="highlight">{html.escape(m.group(1))}</span>',
        escaped_text,
        flags=re.IGNORECASE
    )
    return highlighted_text

def send_email_notification(user_email, score):
    """Send email notification using Hunter API"""
    try:
        # Verify email first
        verify_params = {
            'api_key': HUNTER_API_KEY,
            'email': user_email
        }
        verify_response = requests.get(HUNTER_API_URL, params=verify_params)
        verify_data = verify_response.json()
        
        if verify_data.get('data', {}).get('status') == 'valid':
            # Send email using Hunter's email sending service
            email_params = {
                'api_key': HUNTER_API_KEY,
                'to': user_email,
                'subject': 'New Resume Match Submission',
                'text': f'Your resume match submission has been processed.\n\nMatch Score: {score:.2f}%\n\nView your submissions at: {request.host_url}submissions'
            }
            response = requests.post('https://api.hunter.io/v2/email-sender', params=email_params)
            return response.status_code == 200
        return False
    except Exception as e:
        logger.error(f"Error sending email notification: {str(e)}")
        return False

def fetch_job_description(query):
    """Fetch job description from Adzuna API"""
    try:
        params = {
            'app_id': ADZUNA_APP_ID,
            'app_key': ADZUNA_API_KEY,
            'what': query,
            'results_per_page': 1
        }
        response = requests.get(ADZUNA_API_URL, params=params)
        data = response.json()
        
        if response.status_code == 200 and data.get('results'):
            job = data['results'][0]
            return {
                'title': job.get('title', ''),
                'description': job.get('description', ''),
                'company': job.get('company_name', ''),
                'location': job.get('location', {}).get('display_name', '')
            }
        return None
    except Exception as e:
        logger.error(f"Error fetching job description: {str(e)}")
        return None

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
@login_required
def submit():
    try:
        resume_text = request.form.get('resume_text', '')
        job_desc = request.form.get('job_desc', '')
        
        # Input validation
        if not resume_text and 'resume' not in request.files:
            flash('Please provide resume text or upload a PDF', 'error')
            return redirect(url_for('index'))
            
        if not job_desc:
            flash('Please provide a job description', 'error')
            return redirect(url_for('index'))
            
        # Handle PDF upload
        if 'resume' in request.files:
            resume_file = request.files['resume']
            if resume_file.filename != '':
                # Check file size
                resume_file.seek(0, 2)  # Seek to end
                size = resume_file.tell()
                resume_file.seek(0)  # Reset file pointer
                
                if size > MAX_PDF_SIZE:
                    flash('PDF file size must be less than 5MB', 'error')
                    return redirect(url_for('index'))
                    
                if not resume_file.filename.lower().endswith('.pdf'):
                    flash('File must be a PDF', 'error')
                    return redirect(url_for('index'))
                
                try:
                    # Read PDF content
                    pdf_reader = PyPDF2.PdfReader(resume_file)
                    resume_text = ''
                    for page in pdf_reader.pages:
                        resume_text += page.extract_text() + '\n'
                except Exception as e:
                    logger.error(f"Error processing PDF: {str(e)}")
                    flash('Error processing PDF file', 'error')
                    return redirect(url_for('index'))
        
        # Truncate texts if too long
        resume_text = truncate_text(resume_text)
        job_desc = truncate_text(job_desc)
        
        # Extract keywords
        resume_keywords = extract_keywords(resume_text)
        job_keywords = extract_keywords(job_desc)
        
        # Find matching and missing keywords
        matching_keywords = resume_keywords.intersection(job_keywords)
        missing_keywords = job_keywords - resume_keywords
        
        # Sort missing keywords by length (longer keywords first) and limit to top 5
        missing_keywords = sorted(list(missing_keywords), key=len, reverse=True)[:MAX_SUGGESTIONS]
        
        # Compute similarity score
        try:
            resume_embedding = model.encode(resume_text, convert_to_tensor=True)
            job_embedding = model.encode(job_desc, convert_to_tensor=True)
            score = util.pytorch_cos_sim(resume_embedding, job_embedding).item() * 100
        except Exception as e:
            logger.error(f"Error computing similarity: {str(e)}")
            flash(f"Error computing similarity: {str(e)}", 'error')
            return redirect(url_for('index'))
        
        # Store in database with user_id
        try:
            conn = sqlite3.connect('matches.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO submissions 
                (user_id, resume_text, job_desc, score, matching_keywords) 
                VALUES (?, ?, ?, ?, ?)
            ''', (current_user.id, resume_text, job_desc, score, ','.join(matching_keywords)))
            conn.commit()
            
            # Get user's email from database
            cursor.execute('SELECT email FROM users WHERE id = ?', (current_user.id,))
            user_email = cursor.fetchone()[0]
            
            # Send email notification
            if user_email:
                if send_email_notification(user_email, score):
                    flash('Email notification sent successfully', 'success')
                else:
                    flash('Submission successful, but email notification failed', 'warning')
            
        except Exception as e:
            logger.error(f"Error saving to database: {str(e)}")
            flash(f"Error saving to database: {str(e)}", 'error')
            return redirect(url_for('index'))
        finally:
            conn.close()
        
        # Highlight keywords in texts
        highlighted_resume = highlight_keywords(resume_text, matching_keywords)
        highlighted_job_desc = highlight_keywords(job_desc, matching_keywords)
        
        flash('Submission successful!', 'success')
        return render_template('result.html', 
                             message="Submission saved successfully!", 
                             score=score,
                             matching_keywords=', '.join(matching_keywords),
                             highlighted_resume=highlighted_resume,
                             highlighted_job_desc=highlighted_job_desc,
                             missing_keywords=', '.join(missing_keywords))
    
    except Exception as e:
        logger.error(f"Unexpected error in submit route: {str(e)}")
        flash(f"An unexpected error occurred: {str(e)}", 'error')
        return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Input validation
        if not username or not password or not email:
            flash('Username, email, and password are required', 'error')
            return render_template('register.html')
            
        if len(username) < 3:
            flash('Username must be at least 3 characters long', 'error')
            return render_template('register.html')
            
        if not username.isalnum():
            flash('Username must be alphanumeric with no spaces', 'error')
            return render_template('register.html')
            
        if len(password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            return render_template('register.html')
            
        if not any(char.isdigit() for char in password):
            flash('Password must contain at least one number', 'error')
            return render_template('register.html')
            
        if not '@' in email or not '.' in email:
            flash('Please enter a valid email address', 'error')
            return render_template('register.html')
        
        try:
            conn = sqlite3.connect('matches.db')
            cursor = conn.cursor()
            
            # Check if username exists
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            if cursor.fetchone():
                flash('Username already exists', 'error')
                return render_template('register.html')
                
            # Check if email exists
            cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
            if cursor.fetchone():
                flash('Email already registered', 'error')
                return render_template('register.html')
            
            # Hash password and create user
            hashed_password = generate_password_hash(password)
            cursor.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                         (username, email, hashed_password))
            conn.commit()
            
            flash('Registration successful! Please log in', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            logger.error(f"Error in registration: {str(e)}")
            flash('An error occurred during registration', 'error')
            return render_template('register.html')
        finally:
            conn.close()
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Input validation
        if not username or not password:
            flash('Username and password are required', 'error')
            return render_template('login.html')
            
        if len(username) < 3:
            flash('Invalid username format', 'error')
            return render_template('login.html')
        
        try:
            conn = sqlite3.connect('matches.db')
            cursor = conn.cursor()
            cursor.execute('SELECT id, username, password FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
            
            if user and check_password_hash(user[2], password):
                user_obj = User(user[0], user[1])
                login_user(user_obj)
                flash('Logged in successfully', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid username or password', 'error')
        except Exception as e:
            logger.error(f"Error in login: {str(e)}")
            flash('An error occurred during login', 'error')
        finally:
            conn.close()
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

@app.route('/submissions')
@login_required
def submissions():
    try:
        conn = sqlite3.connect('matches.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, resume_text, job_desc, score, matching_keywords 
            FROM submissions 
            WHERE user_id = ? 
            ORDER BY id DESC
        ''', (current_user.id,))
        submissions = cursor.fetchall()
        conn.close()
        
        return render_template('submissions.html', submissions=submissions)
    except Exception as e:
        logger.error(f"Error fetching submissions: {str(e)}")
        flash('Error loading submissions', 'error')
        return redirect(url_for('index'))

@app.route('/export/<int:submission_id>')
@login_required
def export_pdf(submission_id):
    try:
        conn = sqlite3.connect('matches.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT resume_text, job_desc, score, matching_keywords 
            FROM submissions 
            WHERE id = ? AND user_id = ?
        ''', (submission_id, current_user.id))
        submission = cursor.fetchone()
        conn.close()
        
        if not submission:
            flash('Submission not found', 'error')
            return redirect(url_for('submissions'))
        
        # Create PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30
        )
        story.append(Paragraph("Resume Keyword Matcher Submission", title_style))
        story.append(Spacer(1, 20))
        
        # Score
        score_style = ParagraphStyle(
            'Score',
            parent=styles['Normal'],
            fontSize=16,
            textColor=colors.blue,
            spaceAfter=20
        )
        story.append(Paragraph(f"Match Score: {submission[2]:.2f}%", score_style))
        story.append(Spacer(1, 20))
        
        # Resume Text
        story.append(Paragraph("Resume Text:", styles['Heading2']))
        story.append(Spacer(1, 10))
        story.append(Paragraph(submission[0][:1000] + "...", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Job Description
        story.append(Paragraph("Job Description:", styles['Heading2']))
        story.append(Spacer(1, 10))
        story.append(Paragraph(submission[1][:1000] + "...", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Matching Keywords
        story.append(Paragraph("Matching Keywords:", styles['Heading2']))
        story.append(Spacer(1, 10))
        story.append(Paragraph(submission[3], styles['Normal']))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f'submission_{submission_id}.pdf',
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        flash('Error generating PDF', 'error')
        return redirect(url_for('submissions'))

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        conn = sqlite3.connect('matches.db')
        cursor = conn.cursor()
        
        # Get all submissions for the user
        cursor.execute('''
            SELECT score, matching_keywords, created_at 
            FROM submissions 
            WHERE user_id = ? 
            ORDER BY created_at DESC
        ''', (current_user.id,))
        submissions = cursor.fetchall()
        
        if not submissions:
            flash('No submissions found. Make your first submission to see analytics.', 'info')
            return render_template('dashboard.html')
        
        # Prepare data for charts
        dates = []
        scores = []
        all_keywords = []
        recent_submissions = []
        
        for submission in submissions:
            # Add to recent submissions
            recent_submissions.append({
                'date': submission[2],
                'score': submission[0],
                'matching_keywords': submission[1]
            })
            
            # Add to score chart data
            dates.append(submission[2])
            scores.append(submission[0])
            
            # Add to keyword data
            keywords = submission[1].split(',')
            all_keywords.extend(keywords)
        
        # Get top 10 keywords
        keyword_counter = Counter(all_keywords)
        top_keywords = keyword_counter.most_common(10)
        keywords = [k[0] for k in top_keywords]
        keyword_counts = [k[1] for k in top_keywords]
        
        # Limit recent submissions to 10
        recent_submissions = recent_submissions[:10]
        
        return render_template('dashboard.html',
                             dates=dates,
                             scores=scores,
                             keywords=keywords,
                             keyword_counts=keyword_counts,
                             recent_submissions=recent_submissions)
                             
    except Exception as e:
        logger.error(f"Error in dashboard: {str(e)}")
        flash('Error loading dashboard', 'error')
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route('/fetch-job', methods=['POST'])
@login_required
def fetch_job():
    query = request.form.get('job_search')
    if not query:
        flash('Please enter a job search term', 'error')
        return redirect(url_for('index'))
    
    job_data = fetch_job_description(query)
    if job_data:
        return render_template('index.html', 
                             job_title=job_data['title'],
                             job_desc=job_data['description'],
                             job_company=job_data['company'],
                             job_location=job_data['location'])
    else:
        flash('No job found for the search term', 'warning')
        return redirect(url_for('index'))

if __name__ == '__main__':
    try:
        # Download required NLTK data
        nltk.download('punkt')
        nltk.download('stopwords')
        
        # Initialize the database
        init_db()
        
        # Run the app
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        logger.error(f"Error starting application: {str(e)}")
        raise 