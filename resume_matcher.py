from flask import Flask, request, render_template
import sqlite3
import PyPDF2
from sentence_transformers import SentenceTransformer, util
import io

app = Flask(__name__)

# Initialize the NLP model
model = SentenceTransformer('all-MiniLM-L6-v2')

def init_db():
    conn = sqlite3.connect('matches.db')
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS submissions')
    cursor.execute('''
        CREATE TABLE submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resume_text TEXT NOT NULL,
            job_desc TEXT NOT NULL,
            score REAL
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    resume_text = request.form.get('resume_text', '')
    job_desc = request.form.get('job_desc', '')
    
    # Handle PDF upload
    if 'resume' in request.files:
        resume_file = request.files['resume']
        if resume_file.filename != '':
            try:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(resume_file.read()))
                resume_text = ''
                for page in pdf_reader.pages:
                    resume_text += page.extract_text() + '\n'
            except Exception as e:
                return render_template('result.html', 
                                    message=f"Error processing PDF: {str(e)}")
    
    if not resume_text:
        return render_template('result.html', 
                             message="Error: Please provide resume text or upload a PDF")
    
    if not job_desc:
        return render_template('result.html', 
                             message="Error: Please provide a job description")
    
    # Compute similarity score
    try:
        resume_embedding = model.encode(resume_text, convert_to_tensor=True)
        job_embedding = model.encode(job_desc, convert_to_tensor=True)
        score = util.pytorch_cos_sim(resume_embedding, job_embedding).item() * 100
    except Exception as e:
        return render_template('result.html', 
                             message=f"Error computing similarity: {str(e)}")
    
    # Store in database
    conn = sqlite3.connect('matches.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO submissions (resume_text, job_desc, score) VALUES (?, ?, ?)',
                  (resume_text, job_desc, score))
    conn.commit()
    conn.close()
    
    return render_template('result.html', 
                         message="Submission saved successfully!", 
                         score=round(score, 2))

if __name__ == '__main__':
    init_db()
    app.run(debug=True) 