from dotenv import load_dotenv
from social_post import SocialPoster
import os
import sys

load_dotenv()

def main():
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

    poster = SocialPoster(
        fb_page_id=os.getenv("FB_PAGE_ID"),
        fb_token=os.getenv("FB_PAGE_TOKEN"),
        ig_user_id=os.getenv("IG_USER_ID"),
        ig_token=os.getenv("FB_PAGE_TOKEN"),
        x_api_key=os.getenv("X_API_KEY"),
        x_api_secret=os.getenv("X_API_SECRET"),
        x_access_token=os.getenv("X_ACCESS_TOKEN"),
        x_access_secret=os.getenv("X_ACCESS_SECRET"),
        make_webhook_url=os.getenv("MAKE_WEBHOOK_URL"),
        s3_bucket=os.getenv("IDRIVE_BUCKET"),
        s3_endpoint=os.getenv("IDRIVE_ENDPOINT"),
        s3_key=os.getenv("IDRIVE_KEY"),
        s3_secret=os.getenv("IDRIVE_SECRET"),
        dry_run=dry_run
    )

    mode = "🟡 DRY-RUN MODE" if dry_run else "🚀 LIVE MODE"
    print(f"\nStarting SocialPoster in {mode}\n")

    try:
        poster.post_all_pending()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
