import requests, os
from dotenv import load_dotenv

load_dotenv()

MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL")

payload = {
    "message": "Test LinkedIn post 🚀 #MortgageWithAndy",
    "media_url": "https://images.pexels.com/photos/106399/pexels-photo-106399.jpeg",
    "media_type": "image",
    "filename": "pexels-test.jpeg"
}

r = requests.post(MAKE_WEBHOOK_URL, json=payload)
print(r.status_code, r.text)
