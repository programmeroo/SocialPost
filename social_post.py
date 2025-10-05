import os
import time
import boto3
import requests
from requests_oauthlib import OAuth1Session
from urllib.parse import urlparse

DEFAULT_CAPTION = "#MortgageWithAndy #LowMortgageRates"


class SocialPoster:
    def __init__(self,
                 fb_page_id,
                 fb_token,
                 ig_user_id,
                 ig_token,
                 x_api_key,
                 x_api_secret,
                 x_access_token,
                 x_access_secret,
                 make_webhook_url,
                 s3_bucket,
                 s3_endpoint,
                 s3_key,
                 s3_secret,
                 dry_run=False):

        self.fb_page_id = fb_page_id
        self.fb_token = fb_token
        self.ig_user_id = ig_user_id
        self.ig_token = ig_token
        self.x_api_key = x_api_key
        self.x_api_secret = x_api_secret
        self.x_access_token = x_access_token
        self.x_access_secret = x_access_secret
        self.make_webhook_url = make_webhook_url
        self.s3_bucket = s3_bucket
        self.s3_endpoint = s3_endpoint
        self.s3_key = s3_key
        self.s3_secret = s3_secret
        self.dry_run = dry_run

        endpoint = self.s3_endpoint
        if not endpoint.startswith("http"):
            endpoint = f"https://{endpoint}"

        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=self.s3_key,
            aws_secret_access_key=self.s3_secret,
            endpoint_url=endpoint
        )


    # -----------------------
    # S3 Helpers
    # -----------------------
    def list_post_files(self):
        resp = self.s3.list_objects_v2(Bucket=self.s3_bucket, Prefix="post/")
        return [c["Key"] for c in resp.get("Contents", [])]

    def generate_url(self, key, expires=3600):
        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.s3_bucket, "Key": key},
            ExpiresIn=expires
        )

    def read_caption(self, key):
        obj = self.s3.get_object(Bucket=self.s3_bucket, Key=key)
        return obj["Body"].read().decode("utf-8").strip()

    def move_to_posted(self, key):
        dest_key = key.replace("post/", "posted/")
        self.s3.copy_object(
            Bucket=self.s3_bucket,
            CopySource={"Bucket": self.s3_bucket, "Key": key},
            Key=dest_key
        )
        self.s3.delete_object(Bucket=self.s3_bucket, Key=key)
        print(f"📦 Moved {key} → {dest_key}")

    # -----------------------
    # Facebook
    # -----------------------
    def post_facebook(self, message, media_url=None, is_video=False):
        if self.dry_run:
            print(f"🟡 [Dry-Run] FB ({'video' if is_video else 'image'}): {message}, media={media_url}")
            return {"status": "dry-run"}

        if media_url:
            if is_video:
                url = f"https://graph.facebook.com/v19.0/{self.fb_page_id}/videos"
                data = {"description": message, "file_url": media_url, "access_token": self.fb_token}
            else:
                url = f"https://graph.facebook.com/v19.0/{self.fb_page_id}/photos"
                data = {"caption": message, "url": media_url, "access_token": self.fb_token}
        else:
            url = f"https://graph.facebook.com/v19.0/{self.fb_page_id}/feed"
            data = {"message": message, "access_token": self.fb_token}

        r = requests.post(url, data=data)
        print("📘 Facebook:", r.status_code, r.text)
        r.raise_for_status()
        return r.json()

    # -----------------------
    # Instagram
    # -----------------------
    def post_instagram(self, message, media_url, is_video=False):
        if self.dry_run:
            print(f"🟡 [Dry-Run] IG ({'video' if is_video else 'image'}): {message}, media={media_url}")
            return {"status": "dry-run"}

        url = f"https://graph.facebook.com/v19.0/{self.ig_user_id}/media"
        if is_video:
            data = {"media_type": "REELS", "video_url": media_url, "caption": message,
                    "access_token": self.ig_token}
        else:
            data = {"image_url": media_url, "caption": message, "access_token": self.ig_token}

        r = requests.post(url, data=data)
        print("📦 IG Container:", r.status_code, r.text)
        r.raise_for_status()
        container_id = r.json()["id"]

        # Poll if video
        if is_video:
            status_url = f"https://graph.facebook.com/v19.0/{container_id}?fields=status_code&access_token={self.ig_token}"
            for _ in range(20):  # ~100s
                s = requests.get(status_url).json()
                print("⏳ IG Video Status:", s)
                if s.get("status_code") == "FINISHED":
                    break
                elif s.get("status_code") == "ERROR":
                    raise Exception("Instagram video processing failed")
                time.sleep(5)

        # Publish
        url = f"https://graph.facebook.com/v19.0/{self.ig_user_id}/media_publish"
        data = {"creation_id": container_id, "access_token": self.ig_token}
        r = requests.post(url, data=data)
        print("📸 IG Publish:", r.status_code, r.text)
        r.raise_for_status()
        return r.json()

    # -----------------------
    # X (Twitter)
    # -----------------------
    def post_x(self, message, media_url=None, is_video=False):
        if self.dry_run:
            print(f"🟡 [Dry-Run] X ({'video' if is_video else 'image'}): {message}, media={media_url}")
            return {"status": "dry-run"}

        twitter = OAuth1Session(
            self.x_api_key, self.x_api_secret,
            self.x_access_token, self.x_access_secret
        )

        media_ids = None
        if media_url:
            file_data = requests.get(media_url).content
            size = len(file_data)

            if is_video and size > 5 * 1024 * 1024:
                # Chunked upload for large video
                upload_url = "https://upload.twitter.com/1.1/media/upload.json"
                init = twitter.post(upload_url, data={
                    "command": "INIT",
                    "media_type": "video/mp4",
                    "total_bytes": size,
                    "media_category": "tweet_video"
                }).json()
                media_id = init["media_id_string"]

                # Append in 5MB chunks
                segment_id = 0
                for i in range(0, size, 5 * 1024 * 1024):
                    chunk = file_data[i:i + 5 * 1024 * 1024]
                    twitter.post(upload_url, data={
                        "command": "APPEND",
                        "media_id": media_id,
                        "segment_index": segment_id
                    }, files={"media": chunk})
                    segment_id += 1

                finalize = twitter.post(upload_url, data={"command": "FINALIZE", "media_id": media_id}).json()
                print("🐦 X Finalize:", finalize)

                # Poll processing
                while True:
                    status = twitter.get(upload_url, params={
                        "command": "STATUS",
                        "media_id": media_id
                    }).json()
                    print("⏳ X Video Status:", status)
                    if status.get("processing_info", {}).get("state") in ("succeeded", "failed"):
                        break
                    time.sleep(5)

                media_ids = [media_id]
            else:
                # Simple upload
                upload_url = "https://upload.twitter.com/1.1/media/upload.json"
                r = twitter.post(upload_url, files={"media": file_data})
                r.raise_for_status()
                media_ids = [r.json()["media_id_string"]]

        # Post Tweet
        post_url = "https://api.twitter.com/1.1/statuses/update.json"
        payload = {"status": message}
        if media_ids:
            payload["media_ids"] = ",".join(media_ids)
        r = twitter.post(post_url, params=payload)
        print("🐦 X Post:", r.status_code, r.text)
        r.raise_for_status()
        return r.json()

    # -----------------------
    # LinkedIn
    # -----------------------
    def post_linkedin(self, message, media_url=None, is_video=False):
        payload = {
            "message": message,
            "media_url": media_url,
            "media_type": "video" if is_video else "image",
            "filename": media_url.split("?")[0].split("/")[-1]
        }
        r = requests.post(self.make_webhook_url, json=payload, timeout=120)
        try:
            r.raise_for_status()
        except Exception:
            print("💥 Make error:", r.status_code, r.text)
            raise
        print("💼 LinkedIn (via Make):", r.status_code, r.text)
        return r.json() if r.text else {"status": "ok"}


    # -----------------------
    # Main loop
    # -----------------------
    def post_all_pending(self):
        keys = self.list_post_files()
        media_files = [k for k in keys if k.lower().endswith((".jpg", ".jpeg", ".png", ".mp4"))]

        if not media_files:
            print("✅ No media files to post.")
            return

        media_files.sort()
        media_key = media_files[0]
        base, ext = os.path.splitext(media_key)
        is_video = ext.lower() == ".mp4"
        txt_key = base + ".txt"

        caption = DEFAULT_CAPTION
        if txt_key in keys:
            caption = self.read_caption(txt_key)

        url = self.generate_url(media_key)

        print(f"\n🚀 Posting {media_key} ({'video' if is_video else 'image'}) with caption: {caption}")
        try:
            # self.post_facebook(caption, url, is_video)
            # self.post_instagram(caption, url, is_video)
            # self.post_x(caption, url, is_video)
            self.post_linkedin(caption, url, is_video)

            # self.move_to_posted(media_key)
            # if txt_key in keys:
            #     self.move_to_posted(txt_key)

        except Exception as e:
            print(f"❌ Failed posting {media_key}: {e}")
