from social_post import SocialPoster
from linkedin_post import LinkedInPoster
import sys
from safio import get_env, safe_print


def main():

    poster = SocialPoster(
        fb_app_id = get_env("FB_APP_ID"),
        fb_app_secret = get_env("FB_APP_SECRET"),
        fb_long_lived_user_token = get_env("FB_LL_USER_TOKEN"),
        fb_page_id = get_env("FB_PAGE_ID"),
        fb_page_token = get_env("FB_PAGE_TOKEN"),
        ig_user_id = get_env("IG_USER_ID"),
        ig_page_token = get_env("IG_PAGE_TOKEN"),
        s3_bucket = get_env("S3_BUCKET"),
        s3_endpoint = get_env("S3_ENDPOINT"),
        s3_key = get_env("S3_KEY"),
        s3_secret = get_env("S3_SECRET"),
        media_base_url = get_env("MEDIA_BASE_URL", "https://media.andysabo.com"),
        posts_folder = get_env("POSTS_FOLDER", "./post"),
    )

    li_poster = LinkedInPoster(
        make_webhook_url = get_env("MAKE_WEBHOOK_URL"),
        s3_bucket = get_env("S3_BUCKET"),
        s3_endpoint = get_env("S3_ENDPOINT"),
        s3_key = get_env("S3_KEY"),
        s3_secret = get_env("S3_SECRET"),
        media_base_url = get_env("MEDIA_BASE_URL", "https://media.andysabo.com"),
    )

    try:
        li_poster.post_one()
        poster.post_one()
    except Exception as e:
        safe_print(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()