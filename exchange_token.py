import os
import requests
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("FB_APP_ID")
APP_SECRET = os.getenv("FB_APP_SECRET")
USER_TOKEN = os.getenv("FB_USER_TOKEN")  # short-lived user token

GRAPH = "https://graph.facebook.com/v19.0"

def exchange_user_token():
    url = f"{GRAPH}/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "fb_exchange_token": USER_TOKEN,
    }
    r = requests.get(url, params=params)
    print("📡 Request URL:", r.url.replace(USER_TOKEN, "*****"))  # mask token
    r.raise_for_status()
    return r.json()


def debug_token(token):
    url = f"{GRAPH}/debug_token"
    params = {
        "input_token": token,
        "access_token": f"{APP_ID}|{APP_SECRET}"
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json()


if __name__ == "__main__":
    try:
        result = exchange_user_token()
        print("✅ Response:", result)
        
        result = debug_token(os.getenv("FB_USER_TOKEN"))
        print("✅ Debug Token Info:", result)
    except Exception as e:
        print("❌ Error:", e)
