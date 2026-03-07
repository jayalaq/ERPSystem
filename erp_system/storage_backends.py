"""
Cloudflare R2 Storage Backend for Django.
R2 is S3-compatible, so we use django-storages S3 backend.
"""
import os
from storages.backends.s3boto3 import S3Boto3Storage


class CloudflareR2Storage(S3Boto3Storage):
    """Base Cloudflare R2 storage."""
    access_key = os.environ.get('CLOUDFLARE_R2_ACCESS_KEY', '')
    secret_key = os.environ.get('CLOUDFLARE_R2_SECRET_KEY', '')
    endpoint_url = os.environ.get('CLOUDFLARE_R2_ENDPOINT', '')
    bucket_name = os.environ.get('CLOUDFLARE_R2_BUCKET', 'erp-media')
    region_name = 'auto'
    default_acl = None
    signature_version = 's3v4'
    object_parameters = {
        'CacheControl': 'max-age=86400',
    }

    def url(self, name):
        """Return public URL via Cloudflare R2 public domain."""
        public_url = os.environ.get('CLOUDFLARE_R2_PUBLIC_URL', '')
        if public_url:
            return f"{public_url.rstrip('/')}/{name}"
        return super().url(name)


class StaticR2Storage(CloudflareR2Storage):
    """Static files on R2."""
    location = 'static'
    default_acl = None
    object_parameters = {
        'CacheControl': 'max-age=2592000',  # 30 days
    }


class MediaR2Storage(CloudflareR2Storage):
    """Media/uploads on R2."""
    location = 'media'
    file_overwrite = False
