from flask import Flask, request, jsonify, send_file, render_template, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import mysql.connector
import bcrypt
import PyPDF2
import nltk
import re
import random
from pptx import Presentation
from pptx.util import Inches, Pt
from io import BytesIO
import base64
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, VectorParams, Distance
import uuid
from datetime import datetime, timezone
import google.generativeai as genai
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Download required NLTK data
try:
    nltk.download('punkt', quiet=True)
    nltk.download('averaged_perceptron_tagger', quiet=True)
except Exception as e:
    logging.error(f"Error downloading NLTK data: {str(e)}")
    raise

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  # Replace with a secure random key

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configure MySQL
db_config = {
    'host': 'localhost',
    'user': 'root',  # Replace with your MySQL username
    'password': 'Vishwanath1604@',  # Replace with your MySQL password
    'database': 'professor_bot_db'
}

try:
    db = mysql.connector.connect(**db_config)
    cursor = db.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL
        )
    ''')
    db.commit()
except Exception as e:
    logging.error(f"Error setting up MySQL database: {str(e)}")
    raise

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    try:
        cursor = db.cursor()
        cursor.execute("SELECT id, username FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if user:
            return User(id=user[0], username=user[1])
        return None
    except Exception as e:
        logging.error(f"Error loading user: {str(e)}")
        return None

# Configure Gemini API
GEMINI_API_KEY = "AIzaSyDgtWrBsWrPN6rx7OXX_F8YiRHK5s62zjE"  # Replace with your Gemini API key
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    logging.error(f"Error configuring Gemini API: {str(e)}")
    raise

# Initialize Qdrant client (currently bypassed)
qdrant_client = QdrantClient(url="http://localhost:6333")

# Qdrant collection name
COLLECTION_NAME = "professor_documents"

# Global variables
study_plan = []
mcq_questions = []
syllabus = []
current_document_id = None
current_document_text = ""

def setup_qdrant_collection():
    """Set up Qdrant collection if it doesn't exist."""
    try:
        collections = qdrant_client.get_collections()
        if COLLECTION_NAME not in [c.name for c in collections.collections]:
            qdrant_client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=1, distance=Distance.COSINE)
            )
    except Exception as e:
        logging.error(f"Error setting up Qdrant collection: {str(e)}")

def chunk_document(text, chunk_size=500):
    """Split document text into smaller chunks for better retrieval."""
    try:
        sentences = nltk.sent_tokenize(text)
        chunks = []
        current_chunk = ""
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= chunk_size:
                current_chunk += sentence + " "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "
        if current_chunk:
            chunks.append(current_chunk.strip())
        return chunks
    except Exception as e:
        logging.error(f"Error chunking document: {str(e)}")
        return []

def store_document_in_qdrant(text, document_id):
    """Store document chunks in Qdrant with valid UUID point IDs."""
    try:
        chunks = chunk_document(text)
        points = []
        for idx, chunk in enumerate(chunks):
            point_id = str(uuid.uuid4())
            point = PointStruct(
                id=point_id,
                vector=[random.random()],
                payload={
                    "text": chunk,
                    "document_id": document_id,
                    "chunk_idx": idx,
                    "uploaded_at": datetime.now(timezone.utc).isoformat()
                }
            )
            points.append(point)
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
    except Exception as e:
        return f"Error storing document in Qdrant: {str(e)}"
    return None

def retrieve_relevant_chunks(query, document_id, top_k=3):
    """Retrieve relevant chunks from Qdrant based on the query."""
    try:
        points = qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter={"must": [{"key": "document_id", "match": {"value": document_id}}]},
            limit=100
        )[0]
        if not points:
            return []

        query_words = set(query.lower().split())
        scored_chunks = []
        for point in points:
            chunk_text = point.payload["text"]
            chunk_words = set(chunk_text.lower().split())
            common_words = query_words.intersection(chunk_words)
            score = len(common_words) / len(query_words) if query_words else 0
            scored_chunks.append((chunk_text, score))

        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        return [chunk for chunk, score in scored_chunks[:top_k] if score > 0]
    except Exception as e:
        return [f"Error retrieving chunks from Qdrant: {str(e)}"]

def get_document_from_qdrant(document_id):
    """Retrieve and reconstruct full document text from Qdrant."""
    try:
        points = qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter={"must": [{"key": "document_id", "match": {"value": document_id}}]},
            limit=100
        )[0]
        if not points:
            return None
        points.sort(key=lambda p: p.payload["chunk_idx"])
        document_text = " ".join(point.payload["text"] for point in points)
        return document_text
    except Exception as e:
        return f"Error retrieving document from Qdrant: {str(e)}"

def read_pdf(file_stream):
    """Read text from a PDF file stream."""
    try:
        pdf = PyPDF2.PdfReader(file_stream)
        document_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                document_text += text + " "
        if not document_text.strip():
            return None, "Error: No text found in the PDF."
        return document_text, None
    except Exception as e:
        logging.error(f"Error reading PDF: {str(e)}")
        return None, f"Error reading PDF: {str(e)}"

def generate_study_plan(text):
    """Generate a study plan based strictly on document content."""
    global study_plan
    study_plan = []
    if not text:
        return ["Error: No document available."]
    
    try:
        sentences = nltk.sent_tokenize(text)
        if len(sentences) < 5:
            return ["Error: Document is too short to generate a study plan."]
        
        words = nltk.word_tokenize(text.lower())
        words = [w for w in words if w.isalpha()]
        freq = nltk.FreqDist(words)
        common_words = [word for word, count in freq.most_common(20) if len(word) > 5]
        
        for i, topic in enumerate(common_words[:5], 1):
            study_plan.append(f"Week {i}: Study '{topic}' - Focus on sections mentioning this term in the document.")
        return study_plan if study_plan else ["No key topics identified in the document."]
    except Exception as e:
        logging.error(f"Error generating study plan: {str(e)}")
        return [f"Error generating study plan: {str(e)}"]

def generate_syllabus_with_gemini(text):
    """Generate a detailed syllabus using Gemini from the document content."""
    global syllabus
    syllabus = []
    if not text:
        return ["Error: No document available to generate syllabus."]

    text = text[:5000]
    prompt = f"""Given the following document content, create a detailed syllabus for a student course. Include a course overview, 3–5 overall learning objectives, and 4–6 main topics with subtopics, timelines, prerequisites, estimated study hours, key resources from the document, learning outcomes, and assessment ideas. Focus on key concepts, organize logically, and ensure content is derived strictly from the document.

Content:
{text}

Output format:
Course Overview: [Summary of the course in 100–150 characters.]

Learning Objectives:
- [Objective 1, under 100 characters]
- [Objective 2, under 100 characters]
- [Objective 3, under 100 characters]

Syllabus Outline:
- Topic 1: [Main Topic]
  - Subtopic 1.1: [Subtopic, under 80 characters]
  - Subtopic 1.2: [Subtopic, under 80 characters]
  - Timeline: [e.g., Week 1–2]
  - Prerequisites: [e.g., Basic biology knowledge, or None, under 80 characters]
  - Estimated Study Hours: [e.g., 5 hours]
  - Key Resources: [Document sections or terms to focus on, under 120 characters]
  - Learning Outcome: [Outcome for this topic, under 100 characters]
  - Assessment: [Assessment idea, under 80 characters]
- Topic 2: [Main Topic]
  - Subtopic 2.1: [Subtopic, under 80 characters]
  - Subtopic 2.2: [Subtopic, under 80 characters]
  - Timeline: [e.g., Week 3]
  - Prerequisites: [e.g., Topic 1 knowledge, under 80 characters]
  - Estimated Study Hours: [e.g., 4 hours]
  - Key Resources: [Document sections or terms to focus on, under 120 characters]
  - Learning Outcome: [Outcome for this topic, under 100 characters]
  - Assessment: [Assessment idea, under 80 characters]
"""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-8b')
        response = model.generate_content(prompt)
        syllabus_text = response.text.strip()
        syllabus = syllabus_text.split("\n")
        syllabus = [line.strip() for line in syllabus if line.strip()]
        return syllabus if syllabus else ["No syllabus generated."]
    except Exception as e:
        logging.error(f"Error generating syllabus with Gemini: {str(e)}")
        return [f"Error generating syllabus with Gemini: {str(e)}"]

def generate_mcq(text):
    """Generate 10 MCQ questions strictly from document content without POS tagging."""
    global mcq_questions
    mcq_questions = []
    if not text:
        return [{"question": "Error: No document available.", "options": [], "correct": ""}]
    
    try:
        sentences = nltk.sent_tokenize(text)
        key_sentences = [s for s in sentences if len(s.split()) > 10 and '?' not in s]
        if len(key_sentences) < 5:
            return [{"question": "Error: Document is too short to generate MCQs.", "options": [], "correct": ""}]
        
        words = nltk.word_tokenize(text.lower())
        words = [w for w in words if w.isalpha() and len(w) > 3]
        freq = nltk.FreqDist(words)
        key_terms = [word for word, count in freq.most_common(20)]
        
        random.shuffle(key_sentences)
        
        for i, sentence in enumerate(key_sentences[:10], 1):
            sentence_lower = sentence.lower()
            key_term = None
            for term in key_terms:
                if term in sentence_lower:
                    key_term = term
                    break
            if not key_term:
                continue
            question = re.sub(r'\b' + re.escape(key_term) + r'\b', "______", sentence, count=1)
            question = f"Question {i}: {question} What fits in the blank?"
            correct_answer = key_term
            distractors = random.sample([t for t in key_terms if t != key_term], min(3, len(key_terms)-1))
            while len(distractors) < 3:
                distractors.append(f"Term_{len(distractors)+1}")
            options = [correct_answer] + distractors
            random.shuffle(options)
            mcq_questions.append({
                "question": question,
                "options": options,
                "correct": correct_answer
            })
        return mcq_questions if mcq_questions else [{"question": "No suitable content for MCQs found.", "options": [], "correct": ""}]
    except Exception as e:
        logging.error(f"Error generating MCQs: {str(e)}")
        return [{"question": f"Error generating MCQs: {str(e)}", "options": [], "correct": ""}]

def create_ppt_from_slides():
    """Create a PowerPoint presentation using content from the uploaded PDF."""
    try:
        global current_document_text
        if not current_document_text:
            return None, "Error: No document content available (please upload a PDF first)."

        sentences = nltk.sent_tokenize(current_document_text)
        if len(sentences) < 5:
            return None, "Error: Document is too short to generate a presentation."

        words = nltk.word_tokenize(current_document_text.lower())
        words = [w for w in words if w.isalpha() and len(w) > 5]
        freq = nltk.FreqDist(words)
        common_words = [word for word, count in freq.most_common(5)]

        if not common_words:
            return None, "Error: No key topics identified in the document."

        slides = []
        for topic in common_words:
            topic_sentences = [s for s in sentences if topic.lower() in s.lower()]
            if not topic_sentences:
                continue

            content = []
            for sentence in topic_sentences[:5]:
                bullet = sentence.strip()[:97] + "..." if len(sentence) > 97 else sentence.strip()
                content.append(bullet)
            if content:
                slides.append({
                    "title": f"Exploring {topic.capitalize()}",
                    "content": content
                })

        if not slides:
            return None, "Error: No suitable content found for slides."

        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        title = slide.shapes.title
        subtitle = slide.placeholders[1]
        title.text = "Presentation Based on Uploaded Document"
        subtitle.text = f"Generated on {datetime.now().strftime('%B %d, %Y')}"

        for slide_data in slides:
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            title = slide.shapes.title
            content_box = slide.placeholders[1]
            title.text = slide_data["title"]
            content_box.text = "\n".join(f"• {point}" for point in slide_data["content"])

        output = BytesIO()
        prs.save(output)
        return output.getvalue(), None
    except Exception as e:
        logging.error(f"Error creating PPT: {str(e)}")
        return None, f"Error creating PPT: {str(e)}"

def create_ppt_with_rag(topic, document_id):
    """Create a PowerPoint presentation using document content and Gemini."""
    global current_document_text
    if not current_document_text:
        return None, "Error: No document content available (Qdrant storage skipped)."

    context = current_document_text[:1000]
    prompt = f"Based on the following document content, generate content for a PowerPoint presentation about '{topic}'. Provide a title and 3 slide descriptions (each with a slide title and content, limited to 500 characters):\n\nContext:\n{context}\n\nOutput format:\nTitle: [Presentation Title]\nSlide 1: [Slide Title] - [Content]\nSlide 2: [Slide Title] - [Content]\nSlide 3: [Slide Title] - [Content]"

    try:
        model = genai.GenerativeModel('gemini-1.5-flash-8b')
        response = model.generate_content(prompt)
        ppt_content = response.text
    except Exception as e:
        return None, f"Error generating PPT content with Gemini: {str(e)}"

    lines = ppt_content.strip().split("\n")
    if len(lines) < 4:
        return None, "Error: Invalid PPT content generated by Gemini."

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    title = slide.shapes.title
    subtitle = slide.placeholders[1]
    presentation_title = lines[0].replace("Title: ", "").strip()
    title.text = presentation_title
    subtitle.text = "Based on Uploaded Document"

    for i in range(1, 4):
        slide_info = lines[i].split(" - ", 1)
        if len(slide_info) != 2:
            continue
        slide_title, slide_content = slide_info
        slide_title = slide_title.replace(f"Slide {i}: ", "").strip()
        slide_content = slide_content.strip()

        slide = prs.slides.add_slide(prs.slide_layouts[1])
        title = slide.shapes.title
        content_box = slide.placeholders[1]
        title.text = slide_title
        content_box.text = slide_content[:500]

    output = BytesIO()
    prs.save(output)
    return output.getvalue(), None

def clarify_doubts_with_rag(question, document_id, response_type):
    """Clarify doubts using document content, syllabus, and Gemini."""
    if "i can't understand" in question.lower():
        return jsonify({"message": "Here is the updated code.", "status": "success"})

    global current_document_text
    if not current_document_text:
        return f"Error: No document content available (Qdrant storage skipped)."

    context = current_document_text[:1000]
    syllabus_context = "\n".join(syllabus) if syllabus else "No syllabus available."
    if response_type == "short":
        prompt = f"Based on the following document content and syllabus, provide a short, student-friendly explanation for the question: '{question}'. Keep the explanation under 100 characters.\n\nDocument Content:\n{context}\n\nSyllabus:\n{syllabus_context}\n\nOutput format:\nHere's a short explanation: [Explanation]."
    elif response_type == "detailed":
        prompt = f"Based on the following document content and syllabus, provide a detailed, student-friendly explanation for the question: '{question}'. Keep the explanation under 300 characters.\n\nDocument Content:\n{context}\n\nSyllabus:\n{syllabus_context}\n\nOutput format:\nHere's a detailed explanation: [Explanation]."
    else:
        prompt = f"Based on the following document content and syllabus, provide a simple explanation for the question: '{question}', and include an example. Keep the explanation under 150 characters and the example under 100 characters.\n\nDocument Content:\n{context}\n\nSyllabus:\n{syllabus_context}\n\nOutput format:\nHere's a simple explanation: [Explanation]. For example: [Example]."

    try:
        model = genai.GenerativeModel('gemini-1.5-flash-8b')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logging.error(f"Error generating explanation with Gemini: {str(e)}")
        return f"Error generating explanation with Gemini: {str(e)}"

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            password = request.form.get('password')
            if not username or not password:
                flash('Username and password are required.', 'error')
                return redirect(url_for('login'))

            cursor = db.cursor()
            cursor.execute("SELECT id, username, password_hash FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            
            if user and bcrypt.checkpw(password.encode('utf-8'), user[2].encode('utf-8')):
                user_obj = User(id=user[0], username=user[1])
                login_user(user_obj)
                flash('Login successful!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid username or password.', 'error')
                return redirect(url_for('login'))
        except Exception as e:
            logging.error(f"Error during login: {str(e)}")
            flash('An error occurred during login.', 'error')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            password = request.form.get('password')
            if not username or not password:
                flash('Username and password are required.', 'error')
                return redirect(url_for('register'))

            # Check if username already exists
            cursor = db.cursor()
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                flash('Username already exists.', 'error')
                return redirect(url_for('register'))

            # Hash password
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # Insert new user
            cursor.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, password_hash))
            db.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            logging.error(f"Error during registration: {str(e)}")
            flash('An error occurred during registration.', 'error')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    """Handle user logout."""
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    """Serve the main chatbot interface."""
    try:
        setup_qdrant_collection()
        return render_template('index.html')
    except Exception as e:
        logging.error(f"Error rendering index.html: {str(e)}")
        return jsonify({"message": f"Error rendering UI: {str(e)}", "status": "error"}), 500

@app.route('/upload_pdf', methods=['POST'])
@login_required
def upload_pdf():
    """Handle PDF upload, store in Qdrant, generate study plan and syllabus."""
    try:
        logging.info("Received PDF upload request")
        if 'file' not in request.files:
            logging.warning("No file uploaded in request")
            return jsonify({"message": "No file uploaded", "status": "error"}), 400

        file = request.files['file']
        logging.info(f"Processing file: {file.filename}")
        
        text, error = read_pdf(file.stream)
        if error:
            logging.error(f"Failed to read PDF: {error}")
            return jsonify({"message": error, "status": "error"}), 400
        
        global current_document_id, current_document_text
        current_document_id = str(uuid.uuid4())
        current_document_text = text
        logging.info(f"PDF text extracted, document ID: {current_document_id}")
        
        plan = generate_study_plan(text)
        logging.info("Study plan generated")

        syllabus_result = generate_syllabus_with_gemini(text)
        logging.info("Syllabus generation attempted")
        
        if any("Error" in item for item in syllabus_result):
            logging.error(f"Syllabus generation failed: {syllabus_result[0]}")
            return jsonify({"message": syllabus_result[0], "status": "error"}), 400

        return jsonify({
            "message": "PDF processed. Study plan and syllabus generated (Qdrant storage skipped).",
            "study_plan": plan,
            "syllabus": syllabus_result,
            "status": "success"
        }), 200
    except Exception as e:
        logging.error(f"Error in upload_pdf route: {str(e)}")
        return jsonify({"message": f"Server error while processing PDF: {str(e)}", "status": "error"}), 500

@app.route('/generate_mcq', methods=['GET'])
@login_required
def get_mcq():
    """Generate MCQs from the stored document and return syllabus."""
    try:
        global current_document_id, syllabus, current_document_text
        if not current_document_id:
            return jsonify({"message": "Please upload a PDF first.", "status": "error"}), 400
        
        if not current_document_text:
            return jsonify({"message": "No document content available (Qdrant storage skipped).", "status": "error"}), 400
        
        questions = generate_mcq(current_document_text)
        return jsonify({
            "message": "MCQs generated from document.",
            "questions": questions,
            "syllabus": syllabus,
            "status": "success"
        }), 200
    except Exception as e:
        logging.error(f"Error in get_mcq route: {str(e)}")
        return jsonify({"message": f"Server error while generating MCQs: {str(e)}", "status": "error"}), 500

@app.route('/generate_mcq', methods=['POST'])
@login_required
def generate_mcq_route():
    """Generate MCQs (POST method)."""
    try:
        global current_document_text, current_document_id
        if not current_document_text:
            return jsonify({"message": "No document available. Please upload a PDF first.", "status": "error"}), 400

        questions = generate_mcq(current_document_text)
        return jsonify({
            "message": "MCQs generated from document.",
            "questions": questions,
            "status": "success"
        }), 200
    except Exception as e:
        logging.error(f"Error in generate_mcq route: {str(e)}")
        return jsonify({"message": f"Server error while generating MCQs: {str(e)}", "status": "error"}), 500

@app.route('/generate_ppt', methods=['POST'])
@login_required
def generate_ppt():
    """Generate structured PPT slide content from uploaded PDF using Gemini."""
    try:
        global current_document_text, current_document_id
        if not current_document_text:
            return jsonify({
                "message": "No document available. Please upload a PDF first.",
                "status": "error"
            }), 400

        text = current_document_text[:5000]
        prompt = f"""
You are an expert educational content creator. A user has uploaded a PDF document to help generate a PowerPoint presentation for a class titled **'Mastering Python for Data Science'**.

Your job is to read the content below (extracted from the uploaded PDF) and generate **5 informative slides**, each with:

- A clear **slide title**
- **3 to 5 concise bullet points** (each under 100 characters)
- Content must be strictly based on the PDF document below
- Emphasize topics related to **Python, Data Science, AI, or Machine Learning**
- Ensure all content is **student-friendly and educational**

Use the following format exactly:

Slide 1: [Title]
- Bullet 1
- Bullet 2
- Bullet 3
- Bullet 4 (optional)
- Bullet 5 (optional)

Slide 2: [Title]
- ...

Here is the uploaded PDF content:

{text}
"""
        model = genai.GenerativeModel('gemini-1.5-flash-8b')
        response = model.generate_content(prompt)
        ppt_text = response.text.strip()

        ppt_lines = [line.strip() for line in ppt_text.split("\n") if line.strip()]
        slides = []
        current_slide = {}

        for line in ppt_lines:
            if line.lower().startswith("slide"):
                if current_slide:
                    slides.append(current_slide)
                slide_title = line.split(":", 1)[-1].strip()
                current_slide = {"title": slide_title, "bullets": []}
            elif line.startswith("-"):
                current_slide["bullets"].append(line[1:].strip())

        if current_slide:
            slides.append(current_slide)

        return jsonify({
            "message": "PPT content generated successfully.",
            "status": "success",
            "slides": slides
        }), 200
    except Exception as e:
        logging.error(f"Error in generate_ppt route: {str(e)}")
        return jsonify({
            "message": f"Error generating PPT: {str(e)}",
            "status": "error"
        }), 500

@app.route('/download_ppt', methods=['POST'])
@login_required
def download_ppt():
    """Generate and download a PowerPoint presentation with predefined slides."""
    try:
        global current_document_id
        if not current_document_id:
            return jsonify({"message": "Please upload a PDF first.", "status": "error"}), 400

        ppt_data, error = create_ppt_from_slides()
        if error:
            return jsonify({"message": error, "status": "error"}), 400

        return send_file(
            BytesIO(ppt_data),
            mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
            as_attachment=True,
            download_name='Python_Data_Science_Presentation.pptx'
        )
    except Exception as e:
        logging.error(f"Error in download_ppt route: {str(e)}")
        return jsonify({"message": f"Server error while downloading PPT: {str(e)}", "status": "error"}), 500

@app.route('/clarify_doubt', methods=['POST'])
@login_required
def clarify():
    """Clarify doubts using document content, syllabus, and Gemini."""
    try:
        global current_document_id
        if not current_document_id:
            return jsonify({"message": "Please upload a PDF first.", "status": "error"}), 400
        
        data = request.json
        if not data or 'question' not in data:
            return jsonify({"message": "Please provide a question.", "status": "error"}), 400
        
        question = data.get('question', '')
        response_type = data.get('response_type', 'short')
        if not question:
            return jsonify({"message": "Please provide a question.", "status": "error"}), 400
        
        response = clarify_doubts_with_rag(question, current_document_id, response_type)
        if isinstance(response, dict):
            return response
        return jsonify({"message": response, "status": "success"}), 200
    except Exception as e:
        logging.error(f"Error in clarify_doubt route: {str(e)}")
        return jsonify({"message": f"Server error while clarifying doubt: {str(e)}", "status": "error"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)