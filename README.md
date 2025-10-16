# SocialPost

## ✅ Workflow

1. **Edit on Windows (OneDrive folder)**

   * You keep all originals and edits here.
   * (Optional: we could automate sync to S3 later, but manual copy works fine for now).

2. **Push to iDrive S3 bucket**

   * Upload your finalized media to a bucket like `maistory-media/images/2025/filename.jpg`.
   * Keep a clear folder structure (`images/`, `videos/`, `drafts/`, etc.).

3. **Generate a pre-signed URL in your Python poster script**

   * Python generates a short-lived HTTPS link (`ExpiresIn=3600` by default).
   * That URL is then fed into:

     * **Facebook API** → `image_url`/`video_url`
     * **Instagram API** → `image_url`/`video_url` in `/media` container
     * **X API** → script downloads file from that URL, then uploads to Twitter’s media endpoint
     * **Make.com Webhook** → LinkedIn module takes `{ "message": "...", "image_url": "..." }` and posts to your **personal feed**

4. **Raspberry Pi**

   * Still keeps a local mirror of the media if you want a fast-access archive or for your X.com automation.
   * But the “official” source for posting is now iDrive S3.

---

## ✅ Example: Generate Pre-signed URL for Make.com

Here’s a helper function for your poster:

```python
import boto3
import os

def generate_presigned_url(bucket, key, expiration=3600):
    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("IDRIVE_KEY"),
        aws_secret_access_key=os.getenv("IDRIVE_SECRET"),
        endpoint_url="https://<your-idrive-endpoint>"
    )
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expiration
    )

# Example usage
url = generate_presigned_url("maistory-media", "images/test.jpg")
print("✅ URL to feed into Make.com:", url)
```

---

## ✅ LinkedIn via Make.com Webhook

* In Make.com, create a **Webhook** scenario.
* Your poster script calls it like this:

```python
import requests

def post_linkedin_via_make(make_webhook_url, message, image_url=None):
    payload = {"message": message, "image_url": image_url}
    r = requests.post(make_webhook_url, json=payload)
    print("💼 LinkedIn (via Make):", r.status_code, r.text)
    r.raise_for_status()
    return r.json()
```

That way, your `SocialPoster` has a `post_linkedin_via_make()` method instead of directly hitting LinkedIn’s locked-down API.

---

## ✅ Big Advantages

* **One master copy** of media = iDrive S3
* **Every platform pulls from the same source** (or from a downloaded copy in the case of Twitter)
* **LinkedIn stays seamless** thanks to Make.com
* Future TikTok integration can also read from iDrive

---

👉 Do you want me to **extend your `SocialPoster` class** so that LinkedIn posts automatically go through a Make.com webhook, while FB/IG/X pull straight from the iDrive S3 URLs? That would unify everything under one script.


Got it, Andy 👍 — now we’re into **real workflow automation** for your posting pipeline. You want to:

* Keep media + caption together in **S3/social-post/post/**.
* Each media file (jpg/png/mp4) may have a corresponding `.txt` file with the caption/tweet text.
* After posting, move **both files** into **S3/social-post/posted/**.
* If a video has **no `.txt` file**, fall back to a default caption (e.g. `#MortgageWithAndy #LowMortgageRates`).

---

## ✅ Proposed File Convention

* `9-18-25_1.jpg` → `9-18-25_1.txt` (optional, for custom text)
* `9-18-25_2.mp4` → `9-18-25_2.txt` (optional, else fallback text used)

---

## ✅ Updated Posting Logic

1. Script scans **S3/post/** for files.
2. For each file:

   * Check if a `.txt` with the same basename exists.
   * If yes → read caption text.
   * If no → use default fallback.
3. Post to FB / IG / X / LinkedIn (via Make).
4. Once successful → move **both the media and txt (if exists)** to **S3/posted/**.

---

## 🐍 Example Implementation

```python
import os
import boto3
import requests
from requests_oauthlib import OAuth1Session

DEFAULT_CAPTION = "#MortgageWithAndy #LowMortgageRates"

class SocialPoster:
    def __init__(self, s3_bucket, s3_endpoint, s3_key, s3_secret,
                 fb_page_id, fb_token,
                 ig_user_id, ig_token,
                 x_api_key, x_api_secret, x_access_token, x_access_secret,
                 make_webhook_url):
        # S3
        self.s3_bucket = s3_bucket
        self.s3_endpoint = s3_endpoint
        self.s3_key = s3_key
        self.s3_secret = s3_secret

        # FB/IG
        self.fb_page_id = fb_page_id
        self.fb_token = fb_token
        self.ig_user_id = ig_user_id
        self.ig_token = ig_token

        # X
        self.x_api_key = x_api_key
        self.x_api_secret = x_api_secret
        self.x_access_token = x_access_token
        self.x_access_secret = x_access_secret

        # LinkedIn via Make
        self.make_webhook_url = make_webhook_url

        # S3 client
        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=self.s3_key,
            aws_secret_access_key=self.s3_secret,
            endpoint_url=self.s3_endpoint
        )

    # -----------------------
    # S3 Helpers
    # -----------------------
    def list_post_files(self, prefix="post/"):
        """List files in post/ folder of the S3 bucket"""
        resp = self.s3.list_objects_v2(Bucket=self.s3_bucket, Prefix=prefix)
        return [item["Key"] for item in resp.get("Contents", []) if not item["Key"].endswith("/")]

    def generate_url(self, key, expiration=3600):
        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.s3_bucket, "Key": key},
            ExpiresIn=expiration
        )

    def move_to_posted(self, key):
        """Move file from post/ → posted/ in S3"""
        dest_key = key.replace("post/", "posted/")
        copy_source = {"Bucket": self.s3_bucket, "Key": key}
        self.s3.copy_object(CopySource=copy_source, Bucket=self.s3_bucket, Key=dest_key)
        self.s3.delete_object(Bucket=self.s3_bucket, Key=key)
        print(f"📂 Moved {key} → {dest_key}")
        return dest_key

    def read_caption(self, txt_key):
        try:
            obj = self.s3.get_object(Bucket=self.s3_bucket, Key=txt_key)
            return obj["Body"].read().decode("utf-8").strip()
        except self.s3.exceptions.NoSuchKey:
            return DEFAULT_CAPTION

    # -----------------------
    # Posting methods (stubs here, use your working ones)
    # -----------------------
    def post_facebook(self, message, image_url=None):
        print("📘 Posting to Facebook:", message, image_url)

    def post_instagram(self, message, image_url):
        print("📸 Posting to Instagram:", message, image_url)

    def post_x(self, message, media_url=None):
        print("🐦 Posting to X:", message, media_url)

    def post_linkedin(self, message, image_url=None):
        payload = {"message": message, "image_url": image_url}
        r = requests.post(self.make_webhook_url, json=payload)
        print("💼 LinkedIn (via Make):", r.status_code, r.text)

    # -----------------------
    # Main Post Loop
    # -----------------------
    def post_all_pending(self):
        keys = self.list_post_files()
        media_files = [k for k in keys if k.lower().endswith((".jpg", ".jpeg", ".png", ".mp4"))]

        for media_key in media_files:
            base, _ = os.path.splitext(media_key)
            txt_key = base + ".txt"

            caption = DEFAULT_CAPTION
            if txt_key in keys:
                caption = self.read_caption(txt_key)

            url = self.generate_url(media_key)

            print(f"\n🚀 Posting {media_key} with caption: {caption}")
            try:
                if media_key.endswith(".mp4"):
                    # IG videos: require special handling, but stub here
                    self.post_facebook(caption, url)
                    self.post_linkedin(caption, url)
                    self.post_x(caption, url)
                else:
                    self.post_facebook(caption, url)
                    self.post_instagram(caption, url)
                    self.post_x(caption, url)
                    self.post_linkedin(caption, url)

                # Move files
                self.move_to_posted(media_key)
                if txt_key in keys:
                    self.move_to_posted(txt_key)

            except Exception as e:
                print(f"❌ Failed posting {media_key}: {e}")
```

---

## ✅ How it Works

1. Script scans `social-post/post/` for media.
2. Finds each `.jpg/.png/.mp4`.
3. Looks for `basename.txt` → reads caption or falls back to `#MortgageWithAndy #LowMortgageRates`.
4. Posts to all platforms.
5. Moves both media + caption to `social-post/posted/`.

---

## Example Run

Say S3 has:

```
post/9-18-25_1.jpg
post/9-18-25_1.txt   (→ "Rates just dropped! 🚀")
post/9-18-25_2.mp4   (→ no txt)
```

Result:

* `9-18-25_1.jpg` posts with caption `"Rates just dropped! 🚀"`.
* `9-18-25_2.mp4` posts with caption `"#MortgageWithAndy #LowMortgageRates"`.
* Both pairs moved to `posted/`.

---

👉 Do you want me to **integrate your existing FB/IG/X/Make posting code** directly into this `post_all_pending()` loop, so it’s a fully functional pipeline instead of stubbed `print()` calls?

