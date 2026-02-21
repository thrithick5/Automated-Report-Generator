# Automated Daily Report Generator

A comprehensive guide to using the AI Code Report Generator system.

## Prerequisites

1. **Python 3.10+** installed
2. **Git** installed
3. **Google Gemini API Key** ([Get one here](https://makersuite.google.com/app/apikey))
4. **SMTP Email Credentials** (Gmail App Password or SendGrid)

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

```env
GEMINI_API_KEY=your_actual_gemini_api_key
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_gmail_app_password
EMAIL_FROM=your_email@gmail.com
```

**Getting Gmail App Password:**
1. Go to Google Account settings
2. Security → 2-Step Verification → App passwords
3. Generate a new app password for "Mail"
4. Use this password in `.env`

### 3. Run the Application

```bash
python -m app.main
```

Or using uvicorn directly:

```bash
uvicorn app.main:app --reload
```

The application will start at: **http://localhost:8000**

## Using the Application

### Configure Repository

1. Open http://localhost:8000
2. Go to the **Configure** tab
3. Enter:
   - Repository URL (e.g., `https://github.com/username/repo`)
   - Branch name (default: `main`)
   - Email recipients (comma-separated)
   - Schedule time and frequency
4. Click **Save Configuration**

### Run Manual Analysis

1. Go to the **Analyze** tab
2. Click **Start Analysis**
3. Wait for the analysis to complete
4. View results in the **Report** tab

### View Reports

1. Go to the **Report** tab
2. See metrics:
   - Critical Issues
   - Warnings
   - Complexity Score
   - Quality Score
3. Read the AI-generated summary

### Schedule Automation

1. Go to the **Schedule** tab
2. View your configured schedule
3. Reports will be automatically generated and emailed

## API Endpoints

- `GET /` - Web interface
- `GET /api/config/` - Get configuration
- `POST /api/config/` - Save configuration
- `POST /api/analyze/now` - Trigger manual analysis
- `GET /api/reports/latest` - Get latest report
- `GET /api/reports/` - List all reports
- `GET /health` - Health check

## Troubleshooting

### "No module named 'app'"
- Make sure you're in the project root directory
- Run: `python -m app.main`

### "GEMINI_API_KEY not found"
- Check your `.env` file exists
- Verify the API key is correct

### Email not sending
- Verify SMTP credentials in `.env`
- For Gmail, ensure "Less secure app access" is enabled or use App Password
- Check firewall settings for port 587

### Analysis fails
- Ensure the repository URL is accessible
- Check that you have internet connection
- Verify Gemini API key is valid

## Project Structure

```
automated-report-generator/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration
│   ├── models.py            # Database models
│   ├── database.py          # Database connection
│   ├── routers/             # API endpoints
│   │   ├── config.py
│   │   ├── analysis.py
│   │   └── reports.py
│   └── services/            # Business logic
│       ├── git_manager.py
│       ├── analyzer.py
│       ├── emailer.py
│       └── scheduler.py
├── static/
│   └── index.html           # Frontend
├── data/                    # SQLite DB & repos
├── .env                     # Environment variables
└── requirements.txt         # Dependencies
```

## Features

✅ AI-powered code analysis using Gemini 1.5 Flash  
✅ Automated daily/weekly/bi-weekly reports  
✅ Email delivery with beautiful HTML templates  
✅ Web dashboard for configuration and viewing  
✅ SQLite database for report history  
✅ Git repository integration  
✅ RESTful API  

## Support

For issues or questions, check the logs in the terminal where the application is running.
