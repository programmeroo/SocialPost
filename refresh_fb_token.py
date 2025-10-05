import os
import requests
from dotenv import load_dotenv

ENV_FILE = ".env"

load_dotenv()

APP_ID = os.getenv("FB_APP_ID")
APP_SECRET = os.getenv("FB_APP_SECRET")
USER_TOKEN = os.getenv("FB_USER_TOKEN")  # short-lived user token
PAGE_ID = os.getenv("FB_PAGE_ID")        # your page id

GRAPH = "https://graph.facebook.com/v19.0"


def exchange_user_token():
    """Exchange short-lived user token for long-lived one"""
    url = f"{GRAPH}/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "fb_exchange_token": USER_TOKEN,
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    data = r.json()
    return data["access_token"]


def get_page_tokens(user_token):
    """Fetch pages and tokens for this user"""
    url = f"{GRAPH}/me/accounts"
    params = {"access_token": user_token}
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json().get("data", [])


def get_ig_user_id(page_id, page_token):
    """Fetch the IG business account ID linked to the Page"""
    url = f"{GRAPH}/{page_id}"
    params = {"fields": "instagram_business_account", "access_token": page_token}
    r = requests.get(url, params=params)
    r.raise_for_status()
    data = r.json()
    ig_account = data.get("instagram_business_account")
    return ig_account["id"] if ig_account else None


def save_to_env(key, value):
    """Save or update a key=value in the .env file"""
    lines = []
    found = False

    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r") as f:
            lines = f.readlines()

    with open(ENV_FILE, "w") as f:
        for line in lines:
            if line.startswith(f"{key}="):
                f.write(f"{key}={value}\n")
                found = True
            else:
                f.write(line)
        if not found:
            f.write(f"\n{key}={value}\n")

    print(f"💾 Saved {key} to {ENV_FILE}")


if __name__ == "__main__":
    try:
        # Step 1: exchange for long-lived user token
        long_user_token = exchange_user_token()
        save_to_env("FB_LONG_USER_TOKEN", long_user_token)

        # Step 2: get page tokens
        pages = get_page_tokens(long_user_token)
        target_page = None
        for p in pages:
            print(f"📄 Page: {p['name']} (ID: {p['id']})")
            if p["id"] == PAGE_ID:
                target_page = p

        if not target_page:
            print("❌ Target PAGE_ID not found.")
            exit(1)

        page_token = target_page["access_token"]
        save_to_env("FB_PAGE_TOKEN", page_token)

        # Step 3: get IG user id
        ig_user_id = get_ig_user_id(PAGE_ID, page_token)
        if ig_user_id:
            save_to_env("IG_USER_ID", ig_user_id)
            save_to_env("IG_PAGE_TOKEN", page_token)  # same as page token
            print(f"✅ IG_USER_ID = {ig_user_id}")
        else:
            print("⚠️ No Instagram account linked to this Page.")

        print("🎉 Tokens refreshed successfully!")

    except Exception as e:
        print("❌ Error:", e)
