# Professor Bot 🤖 

**Professor Bot** is a web-based application designed to assist students by generating study plans, syllabi, multiple-choice questions (MCQs), PowerPoint presentations (PPTs), and answering questions based on uploaded PDF documents. It leverages natural language processing (NLP) with NLTK and AI with Google's Gemini API to process and analyze PDF content, making it a powerful educational tool.

---

## Overview 📚
Professor Bot helps students by automating educational tasks such as creating study plans, generating MCQs, and producing PPTs from uploaded PDFs. Built with Flask, it uses NLTK for text processing and the Gemini API for advanced content generation. The application is ideal for students and educators looking to streamline study material preparation.

---

## Features ✨

- 📄 PDF Upload:Extract text from uploaded PDF documents.
- 📅 Study Plan Generation: Automatically creates a study plan based on key PDF topics.
- 📋 Syllabus Generation: Uses Gemini API to generate a detailed syllabus.
- ❓ MCQ Generation: Creates MCQs by identifying key nouns in the PDF.
- 📊 PPT Generation: Generates PowerPoint slides based on PDF content.
- 💬 Question Clarification: Answers student queries using PDF and syllabus context.
- 🔍 Qdrant Integration: (Currently bypassed) Stores PDF content in a vector database.

---

## Prerequisites 🛠️
## Ensure you have the following installed:

- Python 3.10+ (tested with Python 3.13)
- pip for installing dependencies
- Internet Connection for NLTK downloads and Gemini API access
- (Optional) Docker for Qdrant (currently bypassed)

---

## Installation ⚙️
Follow these steps to set up Professor Bot locally.
1. Clone the Repository
git clone https://github.com/your-username/professor-bot.git
cd professor-bot

2. Set Up a Virtual Environment
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate

3. Install Dependencies
pip install flask PyPDF2 nltk python-pptx qdrant-client google-generativeai

4. Configure the Gemini API Key
Edit professor.py to add your Gemini API key:
GEMINI_API_KEY = "your-gemini-api-key"

Get your key from Google AI Studio.

5. Download NLTK Data
The application requires punkt and averaged_perceptron_tagger_eng. Run this script to download them:
- python -c "import nltk; import os; nltk_data_path = os.path.join(os.path.expanduser('~'),
- 'nltk_data'); os.makedirs(nltk_data_path, exist_ok=True);
- nltk.download('punkt', download_dir=nltk_data_path);
-  nltk.download('averaged_perceptron_tagger_eng',
-   download_dir=nltk_data_path);
-    print(f'NLTK data downloaded to {nltk_data_path}')"

6. (Optional) Set Up Qdrant
To enable vector storage (currently bypassed):

## Install Docker.
- Run Qdrant:docker run -p 6333:6333 qdrant/qdrant


Uncomment Qdrant-related code in professor.py.

## Usage 🚀
## 1. Run the Application
python professor.py

You’ll see:
 * Running on http://127.0.0.1:5000

## 2. Access the Interface
Open your browser and go to:
http://127.0.0.1:5000

## 3. Upload a PDF

Click "Choose File" and select a PDF.
Click "Upload PDF" to process the document and view the study plan and syllabus.

Note: PDFs must contain sufficient text (at least 5 sentences with 10+ words each, including nouns).
## 4. Generate MCQs

Click "Generate MCQ" to create MCQs from the PDF content.

## 5. Generate a PPT

Click "Generate PPT (Text)" to see slide content as text.
Click "Download PPT" to download a PowerPoint presentation based on the PDF.

## 6. Ask Questions

Enter a question in the input field and click "Ask" to get a response.

---

## Project Structure 📂

- professor-bot/
- │
- ├── professor.py          # Main Flask application script
- ├── venv/                 # Virtual environment directory
- ├── Templates   
-   ├── index.html          # Frontend HTML template
-   ├── login.html          # Create a new User
-   ├── register.html       # Existing user to login


--- 

## Key Functions 🔑

- read_pdf(file_stream): Extracts text from PDFs.
- generate_study_plan(text): Creates a study plan from frequent terms.
- generate_syllabus_with_gemini(text): Generates a syllabus using Gemini API.
- generate_mcq(text): Generates MCQs using NLTK.
- create_ppt_from_slides(): Creates PPT slides from PDF content.
- clarify_doubts_with_rag(question, document_id, response_type): Answers queries.
---

## Troubleshooting 🐞
- NLTK Resource Errors
- Resource averaged_perceptron_tagger_eng not found.


## Ensure internet access during setup.
- Verify write permissions for C:\Users\<your-username>\nltk_data.
- Run the NLTK download script from the "Installation" section.

## Gemini API Errors

- Verify your API key in professor.py.
- Check internet connectivity and API rate limits.

## PDF Issues

- No text found in the PDF: Use text-based PDFs or apply OCR.
- Document too short: Ensure the PDF has enough content (5+ sentences).

## Server Issues

- Port in use: Change the port in professor.py (e.g., port=5001).

## Limitations ⚠️

- Requires text-based PDFs with sufficient content.
- Qdrant integration is bypassed due to Docker issues.
- MCQ generation depends on nouns in the PDF.
- Gemini API requires internet and a valid key.
---

## Future Improvements 🔮

- Enable Qdrant for vector storage.
- Support scanned PDFs with OCR.
- Enhance MCQ generation with diverse question types.
- Add customizable PPT templates.
- Implement user authentication.

## Contributing 🤝
- Contributions are welcome! To contribute:

## Fork the repository.
- Create a branch: git checkout -b feature-name.
- Commit your changes: git commit -m "Add feature".
- Push to the branch: git push origin feature-name.
- Open a pull request.


## Contact 📧
- For questions or support, reach out to:

Email: vishwanathamrish@gmail.com

GitHub: Vishwanathamrish



