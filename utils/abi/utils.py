import unicodedata
import re
import calendar
import requests
import yaml
from datetime import datetime, timedelta
import pytz
import hashlib


# Date format
DATE_ISO = "%Y-%m-%d"
DATE_ISO_DATETIME = "%Y-%m-%dT%H:%M:%S"
DATE_ISO_DATETIME_OFFSET = "%Y-%m-%dT%H:%M:%S%z"
DATE_WEEK = "W%W-%Y"

# Timezone
tz = None
if tz is None:
    tz = "Europe/Paris"
TIMEZONE = pytz.timezone(tz)

# Scenarios
TW = datetime.now(TIMEZONE).strftime(DATE_WEEK)
LW = (datetime.now(TIMEZONE) - timedelta(days=datetime.now(TIMEZONE).weekday() + 7)).strftime(DATE_WEEK)

# Mapping colors
MAPPING_COLORS = {
    TW: "#48DD82",
    LW: "#FFFDA2",
}

# Image Arrows
arrow_up = "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c0/Eo_circle_green_arrow-up.svg/2048px-Eo_circle_green_arrow-up.svg.png"
arrow_down = "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b7/Eo_circle_red_arrow-down.svg/2048px-Eo_circle_red_arrow-down.svg.png"
arrow_right = "https://upload.wikimedia.org/wikipedia/commons/thumb/4/42/Eo_circle_orange_arrow-right.svg/2048px-Eo_circle_orange_arrow-right.svg.png"

# Create SHA-256 Hash
def create_sha_256_hash(message):
    message_bytes = message.encode() # Encode the message to bytes
    sha_256_hash = hashlib.sha256(message_bytes) # Create the hash object
    return sha_256_hash.hexdigest() # Return the hexadecimal digest of the hash


def remove_accents(input_str):
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    only_ascii = nfkd_form.encode('ASCII', 'ignore')
    return only_ascii.decode()


def remove_emojis(text):
    # Emoji pattern
    emoji_pattern = re.compile("["
                               u"\U0001F600-\U0001F64F"  # emoticons
                               u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                               u"\U0001F680-\U0001F6FF"  # transport & map symbols
                               u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                               u"\U00002500-\U00002BEF"  # chinese char
                               u"\U00002702-\U000027B0"
                               u"\U00002702-\U000027B0"
                               u"\U000024C2-\U0001F251"
                               u"\U0001f926-\U0001f937"
                               u"\U00010000-\U0010ffff"
                               u"\u2640-\u2642"
                               u"\u2600-\u2B55"
                               u"\u200d"
                               u"\u23cf"
                               u"\u23e9"
                               u"\u231a"
                               u"\ufe0f"  # dingbats
                               u"\u3030"
                               "]+", flags=re.UNICODE)
    # Remove emojis from the text
    text = emoji_pattern.sub(r'', text)
    return text.strip()


def get_last_day_of_month(year, month):
    # Check if the month is valid
    if month < 1 or month > 12:
        raise ValueError("Month must be between 1 and 12")

    # Use calendar.monthrange to get the last day of the month
    last_day = calendar.monthrange(year, month)[1]
    return last_day


def download_image_from_url(url, destination):
    response = requests.get(url)
    with open(destination, 'wb') as file:
        file.write(response.content)
        
        
def read_file(file_name):
    f = open(file_name, 'r')
    file_contents = f.read()
    f.close()
    return file_contents


def open_yaml_file(file_path):
    try:
        with open(file_path, 'r') as file:
            data = yaml.safe_load(file)
            return data
    except FileNotFoundError:
        print(f"Oops! The file at {file_path} was not found.")
    except yaml.YAMLError as exc:
        print(f"Error while parsing YAML file: {exc}")