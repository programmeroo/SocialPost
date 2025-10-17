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


DEFAULT_CAPTION = "#MortgageWithAndy #LowMortgageRates #RealEstateInvesting #HomePurchase DM me today."


class SocialPoster:
    def __init__(
        self,
        *,
        # ---- Facebook / Instagram ----
        fb_app_id: str,
        fb_app_secret: str,                   # for appsecret_proof
        fb_long_lived_user_token: str,        # for page-token refresh via /me/accounts
        fb_page_id: str,
        fb_page_token: str,                   # starting page token (we can refresh)
        ig_user_id: str,
        ig_page_token: str,                   # can be same as FB Page token
        # ---- Storage (for listing/captions only; NOT used for X media bytes) ----
        s3_bucket: str,
        s3_endpoint: str,
        s3_key: str,
        s3_secret: str,
        # ---- Media URL service (stable public URL for FB/IG) ----
        media_base_url: str,                  # e.g. https://media.andysabo.com
        posts_folder: str,
    ):
        # Store exactly what you pass (no env reads here)
        self.fb_app_id = fb_app_id
        self.fb_app_secret = fb_app_secret
        self.fb_ll_user_token = fb_long_lived_user_token
        self.fb_page_id = fb_page_id
        self.fb_page_token = fb_page_token
        self.ig_user_id = ig_user_id
        self.ig_page_token = ig_page_token
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
        self.posts_folder = posts_folder.rstrip("/")



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


    def _poll_ig_container_ready(self, container_id: str, token: str, appsecret_func, printer, is_video: bool = False):
        """
        Poll Instagram Graph API until media container status_code == FINISHED.
        Avoids 'Media ID is not available' (error 9007).
        """
        if is_video:
            return  # IG handles longer video processing internally

        status_url = f"https://graph.facebook.com/v21.0/{container_id}"
        for attempt in range(10):  # wait up to ~50 seconds
            time.sleep(5)
            params = {"fields": "status_code", "access_token": token}
            proof = appsecret_func(token)
            if proof:
                params["appsecret_proof"] = proof

            try:
                rs = requests.get(status_url, params=params, timeout=30)
                if not rs.ok:
                    printer(f"⚠️ IG poll {attempt+1}/10 failed ({rs.status_code}): {rs.text}")
                    continue

                status = rs.json().get("status_code")
                printer(f"⏳ IG poll {attempt+1}/10: {status}")

                if status in ("FINISHED", "PUBLISHED"):
                    return
                if status in ("ERROR", "FAILED"):
                    raise RuntimeError(f"IG processing failed: {rs.text}")

            except Exception as e:
                printer(f"⚠️ IG polling error: {e}")

        raise TimeoutError(f"IG container {container_id} not ready after polling.")
    

    # ------------------------------------------------------------------
    # S3 File Management (local copy + move to posted)
    # ------------------------------------------------------------------
    def copy_current_to_local(self, media_key: str, local_dir: str):
        """
        Download the active media file and its caption (.txt) to a local directory.
        Used by the Raspberry Pi X-post script.
        """
        os.makedirs(local_dir, exist_ok=True)

        filename = os.path.basename(media_key)
        local_media_path = os.path.join(local_dir, filename)

        # Download media file
        self.s3.download_file(self.s3_bucket, media_key, local_media_path)
        safe_print(f"📥 Copied media {media_key} to {local_media_path}")

        # Download corresponding text file (if exists)
        base, _ = os.path.splitext(media_key)
        txt_key = base + ".txt"
        local_txt_path = os.path.join(local_dir, os.path.basename(txt_key))
        try:
            self.s3.download_file(self.s3_bucket, txt_key, local_txt_path)
            safe_print(f"📥 Copied caption {txt_key} to {local_txt_path}")
        except self.s3.exceptions.NoSuchKey:
            safe_print("⚠️ No caption file found for this media.")

        return local_media_path, local_txt_path


    def move_to_posted(self, media_key: str):
        """
        Move the media file and matching .txt from post/ → posted/.
        Called after successful posts to all platforms.
        """
        def move_one(key):
            filename = os.path.basename(key)
            dest_key = f"posted/{filename}"
            self.s3.copy_object(
                Bucket=self.s3_bucket,
                CopySource={"Bucket": self.s3_bucket, "Key": key},
                Key=dest_key,
            )
            self.s3.delete_object(Bucket=self.s3_bucket, Key=key)
            safe_print(f"📤 Moved {key} → {dest_key}")

        # Move media
        move_one(media_key)

        # Move caption (if present)
        base, _ = os.path.splitext(media_key)
        txt_key = base + ".txt"
        try:
            move_one(txt_key)
        except self.s3.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                safe_print("⚠️ No caption file found to move.")
            else:
                raise


    @staticmethod
    def _is_video_from_name(name: str) -> bool:
        mt, _ = mimetypes.guess_type(name)
        return (mt or "").startswith("video/") or name.lower().endswith(".mp4")


    # ------------------------------------------------------------------
    # Facebook (Page) — by URL (v21.0) with appsecret_proof + code 190 refresh
    # ------------------------------------------------------------------
    def _appsecret_proof(self, token: str) -> str | None:
        if not (token and self.fb_app_secret):
            return None
        mac = hmac.new(self.fb_app_secret.encode("utf-8"),
                       msg=token.encode("utf-8"),
                       digestmod=hashlib.sha256)
        return mac.hexdigest()


    def fb_refresh_page_token_if_needed(self) -> bool:
        """Use long-lived user token to fetch Page token via /me/accounts; update fb_page_token."""
        if not (self.fb_ll_user_token and self.fb_page_id):
            return False
        params = {"access_token": self.fb_ll_user_token}
        proof = self._appsecret_proof(self.fb_ll_user_token)
        if proof:
            params["appsecret_proof"] = proof

        r = requests.get("https://graph.facebook.com/v21.0/me/accounts", params=params, timeout=30)
        if not r.ok:
            safe_print("FB /me/accounts error:", r.status_code, r.text)
            return False

        new_tok = None
        for acc in r.json().get("data", []):
            if acc.get("id") == self.fb_page_id and acc.get("access_token"):
                new_tok = acc["access_token"]
                break
        if not new_tok:
            safe_print("FB: could not find page token for", self.fb_page_id)
            return False

        self.fb_page_token = new_tok
        # mirror to IG if you share tokens and it’s not set:
        if not self.ig_page_token:
            self.ig_page_token = new_tok
        safe_print("FB: refreshed page token.")
        return True


    def post_facebook(self, message: str, media_url: str | None, is_video: bool):
        token = self.fb_page_token
        if not (self.fb_page_id and token):
            raise RuntimeError("FB missing page_id or page_token")

        # endpoint + data
        if media_url:
            if is_video:
                url = f"https://graph.facebook.com/v21.0/{self.fb_page_id}/videos"
                data = {"description": message[:2000], "file_url": media_url, "access_token": token}
            else:
                url = f"https://graph.facebook.com/v21.0/{self.fb_page_id}/photos"
                data = {"caption": message[:2000], "url": media_url, "access_token": token}
        else:
            url = f"https://graph.facebook.com/v21.0/{self.fb_page_id}/feed"
            data = {"message": message[:2000], "access_token": token}

        params = {}
        proof = self._appsecret_proof(token)
        if proof:
            params["appsecret_proof"] = proof

        r = requests.post(url, params=params, data=data, timeout=90)
        if r.ok:
            safe_print("📘 Facebook:", r.status_code, r.text)
            return r.json()

        # code 190 -> refresh once
        try:
            code = (r.json().get("error") or {}).get("code")
        except Exception:
            code = None

        if code == 190 and self.fb_refresh_page_token_if_needed():
            token = self.fb_page_token
            data["access_token"] = token
            params = {}
            proof = self._appsecret_proof(token)
            if proof:
                params["appsecret_proof"] = proof
            r2 = requests.post(url, params=params, data=data, timeout=90)
            safe_print("📘 Facebook retry:", r2.status_code, r2.text)
            r2.raise_for_status()
            return r2.json()

        safe_print("📘 Facebook FAIL:", r.status_code, r.text)
        r.raise_for_status()
        return r.json()


    # ------------------------------------------------------------------
    # Instagram — by URL (container -> poll -> publish, v21.0)
    # ------------------------------------------------------------------
    def post_instagram(self, message: str, media_url: str, is_video: bool):
        token = self.ig_page_token or self.fb_page_token
        if not (self.ig_user_id and token):
            raise RuntimeError("IG missing ig_user_id or token")

        proof = self._appsecret_proof(token)

        # Step 1: Create IG media container
        ig_endpoint = f"https://graph.facebook.com/v21.0/{self.ig_user_id}/media"
        params = {"access_token": token}
        if proof:
            params["appsecret_proof"] = proof

        data = {"caption": message[:2200]}
        if is_video:
            data.update({"video_url": media_url, "media_type": "REELS", "share_to_feed": "true"})
        else:
            data.update({"image_url": media_url})

        rc = requests.post(ig_endpoint, params=params, data=data, timeout=90)
        safe_print("📤 IG Container:", rc.status_code, rc.text)
        rc.raise_for_status()

        container_id = rc.json().get("id")
        if not container_id:
            raise RuntimeError(f"IG container creation failed: {rc.text}")

        # Step 2: Poll for readiness
        self._poll_ig_container_ready(container_id, token, self._appsecret_proof, safe_print, is_video)

        # Step 3: Publish when ready
        pub_endpoint = f"https://graph.facebook.com/v21.0/{self.ig_user_id}/media_publish"
        pub_params = {"access_token": token}
        if proof:
            pub_params["appsecret_proof"] = proof

        pub = requests.post(
            pub_endpoint,
            params=pub_params,
            data={"creation_id": container_id},
            timeout=90,
        )

        safe_print("📣 IG Publish:", pub.status_code, pub.text)
        pub.raise_for_status()
        return pub.json()


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

        fb_res = self.post_facebook(caption, media_url, is_video)
        ig_res = self.post_instagram(caption, media_url, is_video)

        safe_print("SUMMARY:", {"facebook": bool(fb_res), "instagram": bool(ig_res)})        
        """
        Copy the files from the S3 bucket to the POST_FOLDER
        xpost script runs after this script. Posts to X, then deletes the files.
        Move the files on the S3 bucket to the posted folder.
        """
        self.copy_current_to_local(media_key, self.posts_folder)
        safe_print("Move the S3 files to posted.")
        self.move_to_posted(media_key)

