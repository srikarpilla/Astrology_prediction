from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import swisseph as swe
import geopy
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import pytz
import datetime
import os
import nltk
import logging
from retrying import retry

app = Flask(__name__, static_folder='static', template_folder='static')
CORS(app)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Set ephemeris path
swe.set_ephe_path('./ephe')
logger.debug("Ephemeris path set successfully")

# NLTK setup
nltk.download('punkt')

# Geolocation setup with unique user agent
geolocator = Nominatim(user_agent="astrology_prediction_app_srikarpilla")
tf = TimezoneFinder()

# Global data (replace with session in production)
user_data = {}
horoscopes = {
    'Aries': 'Today is a great day for bold actions!',
    'Taurus': 'Stability will guide your decisions today.',
    'Gemini': 'Communication is your strength today.',
    'Cancer': 'Trust your intuition in emotional matters.',
    'Leo': 'Your confidence shines brightly today.',
    'Virgo': 'Focus on details to achieve success.',
    'Libra': 'Balance is key in your relationships today.',
    'Scorpio': 'Embrace transformation and inner strength.',
    'Sagittarius': 'Adventure awaits you today.',
    'Capricorn': 'Hard work pays off in your career.',
    'Aquarius': 'Innovate and think outside the box.',
    'Pisces': 'Your creativity flows effortlessly today.'
}

def get_sign(longitude):
    signs = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
    return signs[int(longitude // 30)]

# Retry decorator for geolocation
@retry(stop_max_attempt_number=3, wait_fixed=2000)
def geocode_with_retry(place):
    return geolocator.geocode(place, timeout=20)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_birth_details():
    try:
        data = request.json
        logger.debug(f"Received JSON payload: {data}")
        
        # Validate required keys
        required_keys = ['name', 'date', 'time', 'place']
        missing_keys = [key for key in required_keys if key not in data or not data[key]]
        if missing_keys:
            logger.error(f"Missing required keys: {missing_keys}")
            return jsonify({'status': 'error', 'message': f'Missing required fields: {", ".join(missing_keys)}'})
        
        name = data['name']
        date = datetime.datetime.strptime(data['date'], '%Y-%m-%d')
        time = datetime.datetime.strptime(data['time'], '%H:%M')
        place = data['place'].lower().replace('vishakaptanam', 'Visakhapatnam, India')
        
        logger.debug(f"Processing birth details for {name}: {date}, {time}, {place}")
        
        # Geolocation with retry
        location = geocode_with_retry(place)
        if not location:
            logger.error("Geolocation error: Invalid place")
            return jsonify({'status': 'error', 'message': 'Invalid place. Try a specific city (e.g., Visakhapatnam, India).'})
        lat, lon = location.latitude, location.longitude
        
        # Timezone
        tz = tf.timezone_at(lat=lat, lng=lon)
        if not tz:
            logger.error("Timezone not found")
            return jsonify({'status': 'error', 'message': 'Timezone not found'})
        
        # Timezone conversion
        tz_obj = pytz.timezone(tz)
        local_dt = tz_obj.localize(datetime.datetime(date.year, date.month, date.day, time.hour, time.minute))
        utc_dt = local_dt.astimezone(pytz.UTC)
        
        # Julian day
        jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute / 60.0)
        
        # Calculate signs
        sun_lon = swe.calc_ut(jd, swe.SUN)[0]
        moon_lon = swe.calc_ut(jd, swe.MOON)[0]
        asc = swe.houses(jd, lat, lon, b'P')[0][0]
        
        sun_sign = get_sign(sun_lon)
        moon_sign = get_sign(moon_lon)
        asc_sign = get_sign(asc)
        
        # Static traits (no torch)
        trait_str = "Confidence: 0.80, Luck: 0.70, Creativity: 0.65, Health: 0.75, Love: 0.85"
        
        user_data.update({
            'name': name, 'sun_sign': sun_sign, 'moon_sign': moon_sign,
            'ascendant': asc_sign, 'traits': trait_str
        })
        
        return jsonify({
            'status': 'success', 'sun_sign': sun_sign, 'moon_sign': moon_sign,
            'ascendant': asc_sign, 'traits': trait_str
        })
    except Exception as e:
        logger.error(f"Error in /process: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Error processing birth details: {str(e)}'})

@app.route('/process_message', methods=['POST'])
def process_message():
    try:
        message = request.json['message'].lower()
        logger.debug(f"Processing message: {message}")
        tokens = nltk.word_tokenize(message)
        response = ""
        if 'horoscope' in tokens or 'day' in tokens:
            sun_sign = user_data.get('sun_sign', 'Aries')
            response += f"Your daily horoscope: {horoscopes.get(sun_sign, 'Please submit birth details first.')}"
        if 'love' in tokens:
            moon_sign = user_data.get('moon_sign', 'Aries')
            response += f" Love advice: Follow your {moon_sign} intuition."
        if 'career' in tokens or 'job' in tokens:
            sun_sign = user_data.get('sun_sign', 'Aries')
            response += f" Career tip: Leverage your {sun_sign} strengths."
        if 'mangal' in tokens or 'dosha' in tokens:
            response += " Consult an astrologer for remedies."
        if not response:
            response = "Please ask about horoscope, love, career, or dosha."
        return jsonify({'status': 'success', 'response': response})
    except Exception as e:
        logger.error(f"Error in /process_message: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
