import os
import requests
from dotenv import load_dotenv

load_dotenv()
ENV_PATH = ".env"

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
FB_APP_ID = os.getenv("FB_APP_ID")
FB_APP_SECRET = os.getenv("FB_APP_SECRET")
FB_SHORT_LIVED_USER_TOKEN = os.getenv("FB_SHORT_LIVED_USER_TOKEN")


# ---------------------------------------------------------
# UTILITIES
# ---------------------------------------------------------
def save_env_var(key, value):
    """Insert or update a variable in the .env file."""
    lines = []
    found = False
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r") as f:
            lines = f.readlines()

    with open(ENV_PATH, "w") as f:
        for line in lines:
            if line.startswith(f"{key}="):
                f.write(f"{key}={value}\n")
                found = True
            else:
                f.write(line)
        if not found:
            f.write(f"{key}={value}\n")


def graph_get(url, params):
    """Helper to call Graph API with proper error handling."""
    r = requests.get(url, params=params)
    try:
        r.raise_for_status()
    except Exception:
        print("❌ Error:", r.text)
        raise
    return r.json()


# ---------------------------------------------------------
# TOKEN EXCHANGE
# ---------------------------------------------------------
def get_long_lived_user_token():
    print("🔄 Exchanging short-lived token for long-lived token...")
    url = "https://graph.facebook.com/v19.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": FB_APP_ID,
        "client_secret": FB_APP_SECRET,
        "fb_exchange_token": FB_SHORT_LIVED_USER_TOKEN,
    }
    data = graph_get(url, params)
    token = data["access_token"]
    save_env_var("FB_LONG_LIVED_USER_TOKEN", token)
    print("✅ Long-lived user token saved as FB_LONG_LIVED_USER_TOKEN")
    return token


def get_pages(user_token):
    print("📄 Fetching Facebook Pages...")
    url = "https://graph.facebook.com/v19.0/me/accounts"
    params = {"access_token": user_token}
    data = graph_get(url, params).get("data", [])
    if not data:
        raise RuntimeError("No pages found. Check permissions.")
    for p in data:
        print(f"- {p['name']} (ID: {p['id']})")
    return data


def get_instagram_account(page_id, page_token):
    print(f"📷 Checking Instagram account for page {page_id}...")
    url = f"https://graph.facebook.com/v19.0/{page_id}"
    params = {"fields": "instagram_business_account", "access_token": page_token}
    data = graph_get(url, params)
    return data.get("instagram_business_account", {}).get("id")


# ---------------------------------------------------------
# MAIN EXECUTION
# ---------------------------------------------------------
if __name__ == "__main__":
    print("🚀 Renewing Facebook & Instagram tokens...")

    if not FB_SHORT_LIVED_USER_TOKEN:
        print("❌ Missing FB_SHORT_LIVED_USER_TOKEN in .env")
        exit(1)

    long_token = get_long_lived_user_token()
    pages = get_pages(long_token)

    # Pick your main page — adjust if needed
    target_page = next(
        (p for p in pages if "Loan Officer" in p["name"]), pages[0]
    )

    page_id = target_page["id"]
    page_token = target_page["access_token"]

    save_env_var("FB_PAGE_TOKEN", page_token)

    ig_user_id = get_instagram_account(page_id, page_token)
    if ig_user_id:
        save_env_var("IG_USER_ID", ig_user_id)
        save_env_var("IG_PAGE_TOKEN", page_token)
        print(f"✅ Instagram linked: IG_USER_ID={ig_user_id}")
    else:
        print("⚠️ No Instagram business account found for this page.")

    print("\n🎉 Done — tokens updated in .env for ~60 days validity.")
    print(f"   FB_LONG_LIVED_USER_TOKEN ✅")
    print(f"   FB_PAGE_TOKEN ✅")
    print(f"   IG_PAGE_TOKEN ✅")
