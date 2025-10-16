# social_post.py — class-based; FB/IG by URL
import os
import time
import mimetypes
import tempfile
import hmac
import hashlib
from urllib.parse import urlparse
import requests
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from safio import safe_print


DEFAULT_CAPTION = "#MortgageWithAndy #LowMortgageRates DM me today."


class LinkedInPoster:
    def __init__(
        self,
        *,
        # ---- LinkedIn via Make (not our focus now) ----
        make_webhook_url: str | None,
        # ---- Storage (for listing/captions only; NOT used for X media bytes) ----
        s3_bucket: str,
        s3_endpoint: str,
        s3_key: str,
        s3_secret: str,
        # ---- Media URL service (stable public URL for FB/IG) ----
        media_base_url: str,                  # e.g. https://media.andysabo.com
    ):

        self.make_webhook_url = make_webhook_url

        # S3 client (for listing keys and reading captions ONLY)
        endpoint = s3_endpoint if str(s3_endpoint).startswith("http") else f"https://{s3_endpoint}"
        self.s3_bucket = s3_bucket
        self.s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=s3_key,
            aws_secret_access_key=s3_secret,
            config=Config(signature_version="s3v4"),
        )

        # Media URL base and local cache root
        self.media_base_url = media_base_url.rstrip("/")


    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def list_post_files(self):
        """List objects under post/ on iDrive (used to pick ‘next’)."""
        resp = self.s3.list_objects_v2(Bucket=self.s3_bucket, Prefix="post/")
        return [c["Key"] for c in (resp.get("Contents") or []) if not c["Key"].endswith("/")]


    def read_caption(self, key: str) -> str | None:
        """Read optional post/<name>.txt from iDrive."""
        try:
            obj = self.s3.get_object(Bucket=self.s3_bucket, Key=key)
            return obj["Body"].read().decode("utf-8", errors="replace").strip() or None
        except ClientError:
            return None


    def public_url(self, key: str) -> str:
        """Public URL served by media-service (what FB/IG will fetch)."""
        return f"{self.media_base_url}/media/{key}"


    @staticmethod
    def _is_video_from_name(name: str) -> bool:
        mt, _ = mimetypes.guess_type(name)
        return (mt or "").startswith("video/") or name.lower().endswith(".mp4")


    # ------------------------------------------------------------------
    # LinkedIn via Make (left as-is; we’ll fix scenario later)
    # ------------------------------------------------------------------
    def post_linkedin(self, message: str, media_url: str | None, is_video: bool):
        if not self.make_webhook_url:
            raise RuntimeError("MAKE_WEBHOOK_URL not set")
        payload = {
            "message": message,
            "media_url": media_url,
            "media_type": "video" if is_video else "image",
            "filename": (media_url or "").split("?")[0].split("/")[-1] if media_url else ""
        }
        r = requests.post(self.make_webhook_url, json=payload, timeout=120)
        safe_print("💼 LinkedIn (via Make):", r.status_code, r.text)
        
        return r.status_code


    # ------------------------------------------------------------------
    # Post ONE item (main.py orchestrates calls)
    # ------------------------------------------------------------------
    def post_one(self):
        keys = self.list_post_files()
        media_files = [k for k in keys if k.lower().endswith((".jpg", ".jpeg", ".png", ".mp4"))]
        if not media_files:
            safe_print("✅ No media files to post.")
            return

        media_files.sort()
        media_key = media_files[0]
        base, ext = os.path.splitext(media_key)
        is_video = ext.lower() == ".mp4"
        txt_key = base + ".txt"

        caption = self.read_caption(txt_key) or DEFAULT_CAPTION
        media_url = self.public_url(media_key)

        safe_print(f"\n🚀 Posting {media_key} ({'video' if is_video else 'image'})")
        safe_print(f"   URL : {media_url}")
        safe_print(f"   Text: {caption}")

        li_res = self.post_linkedin(caption, media_url, is_video)

