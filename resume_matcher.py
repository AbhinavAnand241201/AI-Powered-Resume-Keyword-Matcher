from flask import Flask, request, render_template
import sqlite3

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('matches.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resume_text TEXT NOT NULL,
            job_desc TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    resume_text = request.form.get('resume_text')
    job_desc = request.form.get('job_desc')
    
    conn = sqlite3.connect('matches.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO submissions (resume_text, job_desc) VALUES (?, ?)',
                  (resume_text, job_desc))
    conn.commit()
    conn.close()
    
    return render_template('result.html', message="Submission saved successfully!")

if __name__ == '__main__':
    init_db()
    app.run(debug=True) 