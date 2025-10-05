import os
import logging
from dotenv import load_dotenv
import tweepy

# Setup logging
load_dotenv()
LOG_FILE = os.getenv('LOG_FILE')
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
X_API_KEY = os.getenv('X_API_KEY')
X_API_SECRET = os.getenv('X_API_SECRET')
X_ACCESS_TOKEN = os.getenv('X_ACCESS_TOKEN')
X_ACCESS_TOKEN_SECRET = os.getenv('X_ACCESS_TOKEN_SECRET')
POSTS_FOLDER = os.getenv('POSTS_FOLDER')

# Validate environment variables
if not all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET, POSTS_FOLDER, LOG_FILE]):
    logging.error("Missing required environment variables. Check .env file.")
    print("Error: Missing required environment variables. Check .env file.")
    exit(1)

# Initialize Tweepy client for API v2
client = tweepy.Client(
    consumer_key=X_API_KEY,
    consumer_secret=X_API_SECRET,
    access_token=X_ACCESS_TOKEN,
    access_token_secret=X_ACCESS_TOKEN_SECRET
)

# For media uploads (uses API v1.1)
auth = tweepy.OAuth1UserHandler(
    X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET
)
api_v1 = tweepy.API(auth)

def get_daily_file():
    """Find the first media file (jpg or mp4) sorted alphabetically."""
    folder = os.getenv('POSTS_FOLDER')
    try:
        files = [f for f in os.listdir(folder) if f.lower().endswith(('.jpg', '.jpeg', '.mp4'))]
        files = [os.path.join(folder, f) for f in sorted(files)]
        logging.info(f"Found files: {files}")
        
        if not files:
            logging.warning(f"No media files found in {folder}.")
            print(f"No media files found in {folder}.")
            return None, None
        
        media_file = files[0]  # Take the first file
        media_type = 'image' if media_file.lower().endswith(('.jpg', '.jpeg')) else 'video'
        text_file = media_file.rsplit('.', 1)[0] + '.txt' if media_type == 'image' else None
        logging.info(f"Selected media: {media_file}, Text file: {text_file}")
        return media_file, text_file
    except Exception as e:
        logging.error(f"Error accessing directory {folder}: {e}")
        print(f"Error accessing directory: {e}")
        return None, None

def get_text_content(text_file):
    """Read text content from the .txt file."""
    if text_file and os.path.exists(text_file):
        try:
            with open(text_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if len(content) > 280:
                    logging.warning(f"Text in {text_file} exceeds 280 characters. Truncating.")
                    content = content[:280]
                return content
        except Exception as e:
            logging.error(f"Error reading text file {text_file}: {e}")
            print(f"Error reading text file: {e}")
            return None
    return None

def post_media(media_file, text_content):
    """Upload media and post to X.com."""
    try:
        logging.info(f"Uploading media: {media_file}")
        media = api_v1.media_upload(
            filename=media_file,
            file=open(media_file, 'rb'),
            chunked=True if media_file.lower().endswith('.mp4') else False
        )
        media_id = media.media_id_string
        logging.info(f"Uploaded media ID: {media_id}")
        
        response = client.create_tweet(
            text=text_content or "",
            media_ids=[media_id]
        )
        logging.info(f"Posted to X.com: Tweet ID {response.data['id']}, Media: {media_file}, Text: {text_content}")
        print(f"Posted successfully: Tweet ID {response.data['id']}")
        return True
    except Exception as e:
        logging.error(f"Failed to post to X.com: {e}")
        print(f"Error posting to X.com: {e}")
        return False

def delete_files(media_file, text_file):
    """Delete the processed media and text files."""
    try:
        if os.path.exists(media_file):
            os.remove(media_file)
            logging.info(f"Deleted media file: {media_file}")
        if text_file and os.path.exists(text_file):
            os.remove(text_file)
            logging.info(f"Deleted text file: {text_file}")
    except Exception as e:
        logging.error(f"Error deleting files: {e}")
        print(f"Error deleting files: {e}")

def main():
    media_file, text_file = get_daily_file()
    if not media_file:
        return
    
    text_content = get_text_content(text_file) if text_file else None
    
    if post_media(media_file, text_content):
        delete_files(media_file, text_file)

if __name__ == '__main__':
    main()