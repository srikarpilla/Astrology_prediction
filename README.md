 AI Astrologer App

A web application that calculates astrological signs (Sun, Moon, Ascendant) and personality traits based on birth details, and provides rule-based responses to user questions.

 Prerequisites
- Python 3.8+
- Swiss Ephemeris files (download from ftp://ftp.astro.com/pub/swisseph/ephe/)
- Internet connection for geolocation (Nominatim)

 Setup Instructions
1. Clone or set up the project:
   - Create a project folder.
   - Add `app.py`, `requirements.txt`, and a `static` folder containing `index.html`.
   - Download Swiss Ephemeris files (`sepl_18.se1`, `semo_18.se1`, `seas_18.se1`) from ftp://ftp.astro.com/pub/swisseph/ephe/ and place them in an `ephe` folder in the project root.

2. Install dependencies:
   - Create a virtual environment: `python -m venv venv`
   - Activate it: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Unix/Linux/Mac)
   - Install requirements: `pip install -r requirements.txt`

3. Run the application:
   - Run: `python app.py`
   - Open `http://127.0.0.1:5000` in a web browser.
   - For production, use: `gunicorn --timeout 60 -w 4 app:app`

4. Usage:
   - Enter birth details (Name, Date, Time, Place) and submit to see astrological signs and traits.
   - Ask a free-text question (e.g., "What's my horoscope?") to get a response.
   - Check the terminal for debug logs if issues occur.

 Troubleshooting
- Only title shows: Ensure `index.html` is in the `static` folder, ephemeris files are in `ephe`, and check terminal logs for errors.
- Geolocation timeout: Ensure internet access and valid place names (e.g., "New York"). Try increasing timeout in `app.py`.
- Ephemeris errors: Verify `ephe` folder contains `sepl_18.se1`, `semo_18.se1`, `seas_18.se1`.



 Deliverables
- Codebase: Zip the project folder (including `app.py`, `requirements.txt`, `static/index.html`, `ephe/` folder) or host on GitHub.
- Demo Video: 2–5 minute video showcasing the app’s functionality.


- The ML model uses dummy data for simplicity.
- Responses to questions are rule-based, triggered by keywords (horoscope, love, career, etc.).
- For production, avoid debug mode and use `gunicorn`.
