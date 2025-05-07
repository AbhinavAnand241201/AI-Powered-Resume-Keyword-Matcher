# Resume Keyword Matcher

A Flask-based web application that allows users to compare resume text with job descriptions.

## Setup

1. Create a virtual environment:
```bash
python3 -m venv venv
```

2. Activate the virtual environment:
- On macOS/Linux:
```bash
source venv/bin/activate
```
- On Windows:
```bash
venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

1. Make sure your virtual environment is activated
2. Run the Flask application:
```bash
python resume_matcher.py
```
3. Open your web browser and navigate to `http://127.0.0.1:5000/`

## Features

- Input form for resume text and job description
- SQLite database storage for submissions
- Clean and responsive user interface
- Form validation
- Success confirmation page

## Project Structure

- `resume_matcher.py`: Main Flask application
- `templates/`: HTML templates
  - `index.html`: Main form page
  - `result.html`: Submission confirmation page
- `matches.db`: SQLite database (created automatically)
- `requirements.txt`: Project dependencies 