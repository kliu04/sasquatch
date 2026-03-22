"""GCS storage abstraction for file uploads and downloads."""
from __future__ import annotations

import os
import tempfile
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import storage

# Load .env from project root (resolves relative GOOGLE_APPLICATION_CREDENTIALS)
_PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# Make GOOGLE_APPLICATION_CREDENTIALS absolute if it's relative
_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
if _creds and not os.path.isabs(_creds):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(_PROJECT_ROOT / _creds)


class GCSStorage:
    """Google Cloud Storage client for signed URLs, uploads, and downloads."""

    def __init__(self, bucket_name: str | None = None):
        self._bucket_name = bucket_name or os.environ.get("GCS_BUCKET", "sasquatch-scans")
        self._client = storage.Client()
        self._bucket = self._client.bucket(self._bucket_name)
        # On Cloud Run, default compute credentials can't locally sign URLs.
        # Detect this and use IAM signBlob API instead.
        self._signing_kwargs: dict = {}
        creds = self._client._credentials
        if hasattr(creds, "service_account_email") and not hasattr(creds, "sign_bytes"):
            import google.auth.transport.requests
            creds.refresh(google.auth.transport.requests.Request())
            self._signing_kwargs = {
                "service_account_email": creds.service_account_email,
                "access_token": creds.token,
            }

    def generate_upload_url(
        self,
        path: str,
        content_type: str = "application/octet-stream",
        expiry_minutes: int = 30,
    ) -> str:
        """Generate a V4 signed URL for direct upload from iOS."""
        blob = self._bucket.blob(path)
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiry_minutes),
            method="PUT",
            content_type=content_type,
            **self._signing_kwargs,
        )

    def public_url(self, path: str) -> str:
        """Return the public URL for a blob (bucket must allow public reads or use signed read URLs)."""
        return f"https://storage.googleapis.com/{self._bucket_name}/{path}"

    def generate_read_url(self, path: str, expiry_minutes: int = 60) -> str:
        """Generate a signed read URL."""
        blob = self._bucket.blob(path)
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiry_minutes),
            method="GET",
            **self._signing_kwargs,
        )

    def upload_bytes(self, data: bytes, path: str, content_type: str = "image/png") -> str:
        """Upload bytes to GCS. Returns the GCS path (not a URL)."""
        blob = self._bucket.blob(path)
        blob.upload_from_string(data, content_type=content_type)
        return path

    def upload_file(self, local_path: Path, gcs_path: str, content_type: str | None = None) -> str:
        """Upload a local file to GCS. Returns the GCS path (not a URL)."""
        blob = self._bucket.blob(gcs_path)
        blob.upload_from_filename(str(local_path), content_type=content_type)
        return gcs_path

    def _gcs_path(self, path_or_url: str) -> str:
        """Strip public URL prefix to get the GCS object path."""
        prefix = f"https://storage.googleapis.com/{self._bucket_name}/"
        if path_or_url.startswith(prefix):
            return path_or_url[len(prefix):]
        return path_or_url

    def signed_url_or_none(self, path_or_url: str | None, expiry_minutes: int = 60) -> str | None:
        """Convert a stored path or public URL to a signed read URL. Returns None if input is None."""
        if not path_or_url:
            return None
        return self.generate_read_url(self._gcs_path(path_or_url), expiry_minutes)

    def download_to_tempfile(self, path: str, suffix: str = "") -> Path:
        """Download a GCS object to a local temp file. Caller must clean up."""
        blob = self._bucket.blob(path)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        blob.download_to_filename(tmp.name)
        tmp.close()
        return Path(tmp.name)

    def delete_prefix(self, prefix: str) -> None:
        """Delete all blobs with the given prefix."""
        blobs = self._bucket.list_blobs(prefix=prefix)
        for blob in blobs:
            blob.delete()
