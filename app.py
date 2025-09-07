from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import math
import swisseph as swe
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import pytz
import torch
import torch.nn as nn
import nltk
from nltk.tokenize import word_tokenize
import logging
import time
import os
import urllib.request

os.makedirs('ephe', exist_ok=True)
ephe_files = ['sepl_18.se1', 'semo_18.se1', 'seas_18.se1']
for file in ephe_files:
    if not os.path.exists(f'ephe/{file}'):
        logger.debug(f"Downloading {file}...")
        urllib.request.urlretrieve(f'ftp://ftp.astro.com/pub/swisseph/ephe/{file}', f'ephe/{file}')

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

nltk.download('punkt', quiet=True)

app = Flask(__name__, static_folder='static')
CORS(app)

# Set ephemeris path
try:
    swe.set_ephe_path('./ephe')
except Exception as e:
    logger.error(f"Failed to set ephemeris path: {str(e)}")
    raise Exception("Ephemeris path './ephe' not found. Ensure ephemeris files are downloaded.")

# PyTorch model for personality traits
class TraitModel(nn.Module):
    def __init__(self):
        super(TraitModel, self).__init__()
        self.fc1 = nn.Linear(4, 10)
        self.fc2 = nn.Linear(10, 5)  # Outputs: confidence, luck, creativity, health, love

    def forward(self, x):
        x = torch.relu(self.fc1(x))
        return torch.sigmoid(self.fc2(x))

# Train dummy model
def train_model():
    try:
        model = TraitModel()
        inputs = torch.rand(10, 4) * torch.tensor([31, 12, 100, 24])
        targets = torch.rand(10, 5)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
        loss_fn = nn.MSELoss()
        for _ in range(100):
            preds = model(inputs)
            loss = loss_fn(preds, targets)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        return model
    except Exception as e:
        logger.error(f"Model training failed: {str(e)}")
        raise

model = train_model()

# Sign mapper
signs = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']

# Horoscope messages
horoscopes = {
    'Aries': 'Your fiery spirit shines. Take bold steps today.',
    'Taurus': 'Ground yourself in patience. Build for the long term.',
    'Gemini': 'Your mind sparkles. Share your ideas freely.',
    'Cancer': 'Embrace your emotions. Nurture your loved ones.',
    'Leo': 'Your radiance leads. Inspire others with confidence.',
    'Virgo': 'Precision is your gift. Plan your next move carefully.',
    'Libra': 'Seek harmony in all. Balance brings peace.',
    'Scorpio': 'Dive deep into passions. Transformation awaits.',
    'Sagittarius': 'Adventure calls. Explore new horizons.',
    'Capricorn': 'Discipline drives success. Keep climbing.',
    'Aquarius': 'Innovate boldly. The future is yours.',
    'Pisces': 'Trust your dreams. Intuition guides you.'
}

# Store birth details globally (for simplicity)
user_data = {}

# Geolocation cache and rate limit tracking
geolocation_cache = {}
last_geocode_time = 0

# Common spelling corrections for Indian cities
spelling_corrections = {
    'vishakapatanam': 'Visakhapatnam, India',
    'vizayanagaram': 'Vizianagaram, India',
    'vishakapatnam': 'Visakhapatnam, India',
    'vizianagram': 'Vizianagaram, India',
    'bombay': 'Mumbai, India'
}

@app.route('/')
def serve_index():
    return app.send_static_file('index.html')

@app.route('/process', methods=['POST'])
def process_birth_details():
    global last_geocode_time
    try:
        data = request.get_json()
        name = data['name']
        birth_date = datetime.strptime(data['birth_date'], '%Y-%m-%d')
        birth_time = datetime.strptime(data['birth_time'], '%H:%M')
        place = data['birth_place'].strip().lower()
        logger.debug(f"Processing birth details for {name}: {birth_date}, {birth_time}, {place}")

        # Check for spelling corrections
        corrected_place = spelling_corrections.get(place, place)
        if corrected_place != place:
            logger.debug(f"Corrected place name: {place} -> {corrected_place}")
            place = corrected_place

        # Check geolocation cache
        if place in geolocation_cache:
            logger.debug(f"Using cached geolocation for {place}: {geolocation_cache[place]}")
            lat, lon = geolocation_cache[place]
        else:
            # Respect Nominatim rate limits (1 request per second)
            current_time = time.time()
            if current_time - last_geocode_time < 1:
                time.sleep(1 - (current_time - last_geocode_time))
            last_geocode_time = time.time()

            # Geolocation
            geolocator = Nominatim(user_agent='ai_astrologer', timeout=10)
            try:
                location = geolocator.geocode(place, exactly_one=True)
                if not location:
                    # Fallback to country if specific place fails
                    country = place.split(',')[-1].strip()
                    logger.debug(f"Falling back to country: {country}")
                    location = geolocator.geocode(country, exactly_one=True)
                    if not location:
                        logger.error(f"Geolocation failed for place: {place} and country: {country}")
                        return jsonify({'status': 'error', 'message': f'Invalid place: "{place}". Try a specific location like "Visakhapatnam, India" or check spelling.'})
                logger.debug(f"Geolocation result: {location.address}, Lat: {location.latitude}, Lon: {location.longitude}")
                lat = location.latitude
                lon = location.longitude
                # Cache the result
                geolocation_cache[place] = (lat, lon)
            except Exception as e:
                logger.error(f"Geolocation error: {str(e)}")
                return jsonify({'status': 'error', 'message': f'Geolocation failed: {str(e)}. Try "Visakhapatnam, India" or check your internet connection.'})

        # Timezone
        tf = TimezoneFinder()
        tz_str = tf.timezone_at(lng=lon, lat=lat)
        if not tz_str:
            logger.error(f"Timezone lookup failed for lat: {lat}, lon: {lon}")
            return jsonify({'status': 'error', 'message': 'Could not determine timezone'})
        tz = pytz.timezone(tz_str)

        # Birth datetime
        birth_dt_local = datetime.combine(birth_date, birth_time.time())
        birth_dt_local = tz.localize(birth_dt_local)
        birth_dt_utc = birth_dt_local.astimezone(pytz.utc)

        # Julian date
        try:
            jd = swe.utc_to_jd(birth_dt_utc.year, birth_dt_utc.month, birth_dt_utc.day,
                               birth_dt_utc.hour, birth_dt_utc.minute, birth_dt_utc.second, 1)[1]
        except Exception as e:
            logger.error(f"Julian date calculation failed: {str(e)}")
            return jsonify({'status': 'error', 'message': f'Astrological calculation failed: {str(e)}'})

        # Planet positions
        try:
            sun_lon = swe.calc_ut(jd, swe.SUN)[0][0]
            moon_lon = swe.calc_ut(jd, swe.MOON)[0][0]
            asc = swe.houses(jd, lat, lon)[0][0]
        except Exception as e:
            logger.error(f"Planet position calculation failed: {str(e)}")
            return jsonify({'status': 'error', 'message': f'Astrological calculation failed: {str(e)}'})

        # Get signs
        def get_sign(lon):
            return signs[int(math.floor(lon / 30)) % 12]

        sun_sign = get_sign(sun_lon)
        moon_sign = get_sign(moon_lon)
        ascendant = get_sign(asc)

        # Store user data
        user_data['name'] = name
        user_data['sun_sign'] = sun_sign
        user_data['moon_sign'] = moon_sign
        user_data['ascendant'] = ascendant
        user_data['birth_date'] = birth_date
        user_data['birth_time'] = birth_time

        # Predictive model
        try:
            year = birth_date.year % 100
            month = birth_date.month
            day = birth_date.day
            hour = birth_time.hour
            input_tensor = torch.tensor([[day, month, year, hour]], dtype=torch.float32)
            traits = model(input_tensor)[0].tolist()
            trait_names = ['Confidence', 'Luck', 'Creativity', 'Health', 'Love']
            trait_str = ', '.join([f"{name}: {score:.2f}" for name, score in zip(trait_names, traits)])
        except Exception as e:
            logger.error(f"Trait model prediction failed: {str(e)}")
            trait_str = "Traits calculation failed"

        logger.debug(f"Success: Sun: {sun_sign}, Moon: {moon_sign}, Asc: {ascendant}, Traits: {trait_str}")
        return jsonify({
            'status': 'success',
            'sun_sign': sun_sign,
            'moon_sign': moon_sign,
            'ascendant': ascendant,
            'traits': trait_str
        })
    except Exception as e:
        logger.error(f"Unexpected error in /process: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Processing failed: {str(e)}'})

@app.route('/process_message', methods=['POST'])
def process_message():
    try:
        data = request.get_json()
        message = data['message'].lower()
        tokens = word_tokenize(message)
        logger.debug(f"Processing message: {message}")

        response = f"Namaste {user_data.get('name', 'User')}! "
        if 'horoscope' in tokens:
            response += f"Your daily horoscope: {horoscopes[user_data['sun_sign']]}"
        elif any(word in tokens for word in ['love', 'relationship', 'compatibility']):
            response += f"In love, your Moon in {user_data['moon_sign']} suggests emotional depth. Trust your heart."
        elif any(word in tokens for word in ['career', 'job', 'work']):
            response += f"For career, your Sun in {user_data['sun_sign']} encourages bold moves."
        elif 'mangal' in tokens or 'dosha' in tokens:
            response += "Mangal Dosha analysis requires deeper chart analysis. Try chanting Hanuman Chalisa."
        elif 'remedies' in tokens:
            response += f"For balance, with Ascendant in {user_data['ascendant']}, try meditation or gemstones."
        else:
            response += f"Your chart suggests optimism. Follow your intuition for {message}."

        logger.debug(f"Message response: {response}")
        return jsonify({'status': 'success', 'message': response})
    except Exception as e:
        logger.error(f"Error in /process_message: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

