# OCR Service - Setup & Usage Guide

This guide explains how to set up and run the OCR service feature in this project.

## Prerequisites
- Python 3.12 or higher
- Windows OS (instructions use PowerShell)
- Git (optional, for cloning)

## 1. Setup Virtual Environment
Navigate to the `ocr_service` directory:

```powershell
cd path\to\be\ocr_service
```

Activate the virtual environment:

```powershell
.\env\Scripts\Activate.ps1
```

If you see an execution policy error, run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\env\Scripts\Activate.ps1
```

## 2. Install Dependencies
If not already installed, install required packages:

```powershell
pip install -r requirements.txt
```

## 3. Apply Migrations
Before running the server, apply Django migrations:

```powershell
python manage.py migrate
```

## 4. Run the Development Server
Start the Django development server:

```powershell
python manage.py runserver
```

The server will start at `http://127.0.0.1:8000/`.

## 5. Using the OCR Feature
- Access the OCR API endpoints as defined in `ocr_api/urls.py`.
- Interact with the service using HTTP requests (e.g., via Postman, curl, or a frontend).

## 6. Troubleshooting
- If you see `ModuleNotFoundError`, ensure your virtual environment is activated and dependencies are installed.
- For migration issues, ensure the database (`db.sqlite3`) exists and is accessible.

## 7. Deactivating the Environment
When done, deactivate the virtual environment:

```powershell
deactivate
```

---
