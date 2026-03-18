# Vitality Health

Vitality Health is a comprehensive Python Flask web application designed to provide peer-reviewed medical information, specialist directories, and personalized wellness tracking. 

## Features

- **Comprehensive Medical Database**: Browse detailed information across 12 medical categories including Infectious Diseases, Respiratory Conditions, Digestive Issues, and Mental Health.
- **User Authentication**: Secure user registration and login system handling password hashing and session management via `Flask-Login`.
- **Personalized Profiles**: Users can bookmark articles and manage their health preferences in their own private dashboard.
- **Search Engine**: Fast, integrated search functionality allowing users to query the disease database by symptoms, condition names, or categories.
- **SEO Optimized**: Fully equipped with dynamic `sitemap.xml`, `robots.txt`, Canonical links, and Open Graph meta tags for maximum Google Search visibility.
- **Responsive UI/UX**: Built with modern HTML/CSS focusing on accessibility, dynamic micro-animations, and a clean, trustworthy aesthetic.

## Tech Stack

- **Backend**: Python 3, Flask, SQLAlchemy (ORM)
- **Frontend**: HTML5, Vanilla CSS, Jinja2 Templating
- **Database**: SQLite (Development & Production)
- **Deployment**: Render.com platforms (Gunicorn WSGI)

## Local Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/ShivamPandey2411/vitality-health-app.git
   cd vitality-health-app
   ```

2. **Create a Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables**
   Set up your standard Flask environment variables for security.
   ```bash
   export SECRET_KEY="your-secret-key"
   ```

5. **Run the Application**
   ```bash
   python app.py
   ```
   The application will be running at `http://127.0.0.1:5000`

## Project Structure

- `app.py`: Core Flask application routing and database models.
- `vitality.db`: Pre-populated SQLite database containing all medical articles.
- `/templates`: HTML templates for the frontend (index, login, register, profile).
- `/static`: Static assets, including Google Search Console verification files.
- `seed_data_*.py`: Injection files for rapidly populating the medical article database.
- `requirements.txt`: Python dependencies required for the environment.

## Deployment

This application is configured to deploy natively to Render using Gunicorn.
Live URL: [https://vitality-health-app.onrender.com/](https://vitality-health-app.onrender.com/)

## Author

Developed by Shivam Pandey.
