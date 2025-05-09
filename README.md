# Resume Keyword Matcher

A Flask-based web application that matches resumes to job descriptions using NLP. The app analyzes resumes and job descriptions to find matching keywords and provides a similarity score.

## Features

- User authentication (register, login, logout)
- PDF resume upload and text extraction
- Job description analysis
- Keyword matching and highlighting
- Similarity scoring using NLP
- Submission history
- PDF export of submissions
- Input validation and error handling
- Responsive Bootstrap UI
- Analytics dashboard
- Email notifications
- Job search integration

## Tech Stack

- Python 3.x
- Flask (Web framework)
- SQLite (Database)
- PyPDF2 (PDF processing)
- sentence-transformers (NLP)
- NLTK (Natural Language Processing)
- ReportLab (PDF generation)
- Bootstrap (UI)
- Chart.js (Analytics)
- Hunter API (Email verification)
- Adzuna API (Job search)

## Setup Instructions

1. Clone the repository:
```bash
git clone https://github.com/AbhinavAnand241201/resume-matcher.git
cd resume-matcher
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file in the root directory with the following variables:
```
HUNTER_API_KEY=your_hunter_api_key_here
ADZUNA_APP_ID=your_adzuna_app_id_here
ADZUNA_API_KEY=your_adzuna_api_key_here
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=your_secret_key_here
```

5. Initialize the database:
```bash
python resume_matcher.py
```

6. Run the application:
```bash
python resume_matcher.py
```

7. Open your browser and navigate to:
```
http://localhost:5000
```

## Usage

1. Register a new account or log in
2. Search for jobs using the Adzuna API
3. Upload your resume (PDF) or paste resume text
4. Enter a job description
5. Submit to get:
   - Match score
   - Matching keywords
   - Missing keywords
   - Highlighted text
6. View submission history
7. Export submissions as PDF
8. Check analytics dashboard

## Deployment

The app is configured for deployment on Render. Follow these steps:

1. Create a new Web Service on Render
2. Connect your GitHub repository
3. Set the following environment variables:
   - HUNTER_API_KEY
   - ADZUNA_APP_ID
   - ADZUNA_API_KEY
   - SECRET_KEY
4. Deploy

## License

MIT License 