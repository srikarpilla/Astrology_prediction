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
import time
import threading

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

# Geolocation cache with common locations
geolocation_cache = {
    'visakhapatnam, india': {'latitude': 17.6868, 'longitude': 83.2185},
    'new york, usa': {'latitude': 40.7128, 'longitude': -74.0060},
    'london, uk': {'latitude': 51.5074, 'longitude': -0.1278},
    'delhi, india': {'latitude': 28.7041, 'longitude': 77.1025},
    'mumbai, india': {'latitude': 19.0760, 'longitude': 72.8777}
}

# Lock for thread-safe cache updates
cache_lock = threading.Lock()

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
    if not isinstance(longitude, (int, float)):
        logger.error(f"Invalid longitude type: {type(longitude)}, value: {longitude}")
        raise ValueError(f"Expected float for longitude, got {type(longitude)}")
    return signs[int(longitude // 30)]

@retry(stop_max_attempt_number=5, wait_fixed=5000)
def geocode_with_retry(place):
    try:
        normalized_place = place.lower().strip()
        with cache_lock:
            if normalized_place in geolocation_cache:
                logger.debug(f"Using cached geolocation for {place}")
                result = geolocation_cache[normalized_place]
                return type('obj', (object,), {'latitude': result['latitude'], 'longitude': result['longitude']})
        
        time.sleep(1)
        result = geolocator.geocode(place, timeout=30)
        if not result:
            raise ValueError(f"No results found for place: {place}")
        
        with cache_lock:
            geolocation_cache[normalized_place] = {'latitude': result.latitude, 'longitude': result.longitude}
        return result
    except Exception as e:
        logger.error(f"Geocoding error for {place}: {str(e)}")
        raise

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_birth_details():
    try:
        data = request.json
        logger.debug(f"Received JSON payload: {data}")
        
        required_keys = ['name', 'birth_date', 'birth_time', 'birth_place']
        missing_keys = [key for key in required_keys if key not in data or not data[key]]
        if missing_keys:
            logger.error(f"Missing required keys: {missing_keys}")
            return jsonify({'status': 'error', 'message': f'Missing required fields: {", ".join(missing_keys)}'})
        
        name = data['name'].strip()
        try:
            date = datetime.datetime.strptime(data['birth_date'], '%Y-%m-%d').date()
            time = datetime.datetime.strptime(data['birth_time'], '%H:%M').time()
        except ValueError as e:
            logger.error(f"Invalid date or time format: {str(e)}")
            return jsonify({'status': 'error', 'message': 'Invalid date (YYYY-MM-DD) or time (HH:MM) format'})
        
        place = data['birth_place'].strip()
        if 'vishakaptanam' in place.lower():
            place = 'Visakhapatnam, India'
        
        if ',' in place and all(p.strip().replace('-', '').replace('.', '').isdigit() for p in place.split(',')):
            try:
                lat, lon = map(float, place.split(','))
                location = type('obj', (object,), {'latitude': lat, 'longitude': lon})
                logger.debug(f"Using manual coordinates for {place}: lat={lat}, lon={lon}")
            except ValueError as e:
                logger.error(f"Invalid coordinates format: {place}")
                return jsonify({'status': 'error', 'message': 'Invalid coordinates format (use lat,lon e.g., 17.6868,83.2185)'})
        else:
            logger.debug(f"Processing birth details for {name}: {date}, {time}, {place}")
            try:
                location = geocode_with_retry(place)
            except Exception as e:
                logger.error(f"Geolocation failed after retries: {str(e)}")
                return jsonify({'status': 'error', 'message': 'Geolocation service unavailable. Try using coordinates (e.g., 17.6868,83.2185) or a specific city (e.g., Visakhapatnam, India).'})
        
        lat, lon = location.latitude, location.longitude
        
        tz = tf.timezone_at(lat=lat, lng=lon)
        if not tz:
            logger.error(f"Timezone not found for lat={lat}, lon={lon}")
            return jsonify({'status': 'error', 'message': 'Timezone not found'})
        
        tz_obj = pytz.timezone(tz)
        local_dt = datetime.datetime.combine(date, time, tzinfo=tz_obj)
        utc_dt = local_dt.astimezone(pytz.UTC)
        
        jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute / 60.0)
        
        # Calculate planetary positions
        sun_data = swe.calc_ut(jd, swe.SUN)
        moon_data = swe.calc_ut(jd, swe.MOON)
        houses_data = swe.houses(jd, lat, lon, b'P')
        
        logger.debug(f"Sun data: {sun_data}")
        logger.debug(f"Moon data: {moon_data}")
        logger.debug(f"Houses data: {houses_data}")
        
        sun_lon = sun_data[0]  # Longitude is first element
        moon_lon = moon_data[0]
        asc = houses_data[1][0]  # Ascendant is in ascmc[0]
        
        sun_sign = get_sign(sun_lon)
        moon_sign = get_sign(moon_lon)
        asc_sign = get_sign(asc)
        
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
