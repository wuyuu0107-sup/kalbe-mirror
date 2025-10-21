
# OCR & Gemini Medical PDF Service - Setup & Usage Guide

This guide explains how to set up and run the OCR and Gemini medical PDF extraction features in this project.

## Prerequisites
- Python 3.12 or higher
- Windows OS (instructions use PowerShell)
- Git (optional, for cloning)

## 1. Setup Virtual Environment
Navigate to the `backend` directory:

```powershell
cd path\to\backend
python -m venv env
.\env\Scripts\Activate.ps1
```

## 2. Install Dependencies
Install required packages:

```powershell
pip install -r requirements.txt
```

## 3. Environment Variables
Create a `.env` file in the `backend` directory and add your Gemini API key:

```
GEMINI_API_KEY=your_api_key_here
```

## 4. Apply Migrations
Before running the server, apply Django migrations:

```powershell
python manage.py migrate
```

## 5. Run the Development Server
Start the Django development server:

```powershell
python manage.py runserver
```

The server will start at `http://127.0.0.1:8000/`.

## 6. Using the Features

### EasyOCR
- Go to `http://127.0.0.1:8000/ocr/image/` to upload images or PDFs for OCR extraction.
- Returns a downloadable JSON file with detected text and bounding boxes.

### Gemini OCR Extraction
- Go to `http://127.0.0.1:8000/ocr/` to upload a medical PDF.
- The backend will use Gemini API to extract structured medical data from the PDF.
- Results are displayed in the browser as JSON.

## 7. Troubleshooting
- If you see `ModuleNotFoundError`, ensure your virtual environment is activated and dependencies are installed.
- For migration issues, ensure the database (`db.sqlite3`) exists and is accessible.
- For Gemini errors, check your API key in `.env` and internet connection.

## 8. Deactivating the Environment
When done, deactivate the virtual environment:

```powershell
deactivate
```

---
For more details, see the code in `ocr/` and `kalbe_be/` folders.



