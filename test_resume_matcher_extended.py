import unittest
import requests
import io
import sqlite3
import PyPDF2
from reportlab.pdfgen import canvas
from bs4 import BeautifulSoup
import logging
import html

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestResumeMatcherExtended(unittest.TestCase):
    BASE_URL = 'http://127.0.0.1:5000'
    
    def setUp(self):
        """Create test data and resources"""
        self.sample_text = "Python developer with 5 years experience"
        self.sample_job = "Looking for Python developer"
        
        # Create a test PDF
        self.pdf_buffer = io.BytesIO()
        c = canvas.Canvas(self.pdf_buffer)
        c.drawString(100, 750, self.sample_text)
        c.save()
        self.pdf_buffer.seek(0)
    
    def test_pdf_upload(self):
        """Test PDF upload functionality"""
        logger.info("Testing PDF upload...")
        
        # Test valid PDF upload
        files = {'resume': ('test.pdf', self.pdf_buffer, 'application/pdf')}
        data = {'job_desc': self.sample_job}
        response = requests.post(f"{self.BASE_URL}/submit", files=files, data=data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Submission saved successfully", response.text)
        
        # Test oversized PDF
        large_pdf = io.BytesIO(b'0' * (5 * 1024 * 1024 + 1))  # 5MB + 1 byte
        files = {'resume': ('large.pdf', large_pdf, 'application/pdf')}
        response = requests.post(f"{self.BASE_URL}/submit", files=files, data=data)
        self.assertIn("Error: PDF file too large", response.text)
        
        # Test invalid PDF
        files = {'resume': ('fake.pdf', b'not a pdf', 'application/pdf')}
        response = requests.post(f"{self.BASE_URL}/submit", files=files, data=data)
        self.assertIn("Error processing PDF", response.text)
    
    def test_input_validation(self):
        """Test input validation and error handling"""
        logger.info("Testing input validation...")
        
        # Test empty inputs
        response = requests.post(f"{self.BASE_URL}/submit", data={
            'resume_text': '',
            'job_desc': ''
        })
        self.assertIn("Error: Please provide resume text", response.text)
        
        # Test very long inputs
        long_text = "a" * 11000  # Exceeds MAX_TEXT_LENGTH
        response = requests.post(f"{self.BASE_URL}/submit", data={
            'resume_text': long_text,
            'job_desc': self.sample_job
        })
        self.assertEqual(response.status_code, 200)  # Should accept but truncate
        
        # Test XSS attempt
        xss_text = "<script>alert('xss')</script>"
        response = requests.post(f"{self.BASE_URL}/submit", data={
            'resume_text': xss_text,
            'job_desc': self.sample_job
        })
        self.assertNotIn("<script>", response.text)
        # Verify that the script tags are properly escaped
        self.assertIn("&amp;lt;script&amp;gt;", response.text.replace("&lt;", "&amp;lt;").replace("&gt;", "&amp;gt;"))
    
    def test_database_storage(self):
        """Test database operations"""
        logger.info("Testing database storage...")
        
        # Submit a test entry
        response = requests.post(f"{self.BASE_URL}/submit", data={
            'resume_text': self.sample_text,
            'job_desc': self.sample_job
        })
        self.assertEqual(response.status_code, 200)
        
        # Verify database entry
        conn = sqlite3.connect('matches.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM submissions ORDER BY id DESC LIMIT 1')
        row = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(row)
        self.assertEqual(row[1], self.sample_text)  # resume_text
        self.assertEqual(row[2], self.sample_job)   # job_desc
        self.assertIsInstance(row[3], float)        # score
        self.assertIsInstance(row[4], str)          # matching_keywords
    
    def test_security_features(self):
        """Test security features"""
        logger.info("Testing security features...")
        
        # Test SQL injection attempt
        sql_injection = "'; DROP TABLE submissions; --"
        response = requests.post(f"{self.BASE_URL}/submit", data={
            'resume_text': self.sample_text,
            'job_desc': sql_injection
        })
        self.assertEqual(response.status_code, 200)
        
        # Verify table still exists
        conn = sqlite3.connect('matches.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='submissions'")
        table_exists = cursor.fetchone() is not None
        conn.close()
        self.assertTrue(table_exists)
        
        # Test XSS in keywords
        xss_resume = "Python <script>alert('xss')</script> developer"
        xss_job = "Looking for <script>alert('xss')</script> developer"
        response = requests.post(f"{self.BASE_URL}/submit", data={
            'resume_text': xss_resume,
            'job_desc': xss_job
        })
        self.assertNotIn("<script>", response.text)
        
        # Test path traversal attempt
        traversal_pdf = io.BytesIO(b'fake pdf content')
        files = {'resume': ('../../etc/passwd', traversal_pdf, 'application/pdf')}
        response = requests.post(f"{self.BASE_URL}/submit", files=files, data={'job_desc': self.sample_job})
        self.assertNotIn("/etc/passwd", response.text)

if __name__ == '__main__':
    unittest.main(verbosity=2) 