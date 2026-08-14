"""
Applies a permissive CORS policy to the asset and ingest buckets.
"""

from botocore.exceptions import ClientError

from tamper.app.config import get_settings

CORS_CONFIGURATION = {
    "CORSRules": [
        {
            "AllowedOrigins": ["*"],
            "AllowedMethods": ["GET", "HEAD", "PUT"],
            "AllowedHeaders": ["*"],
            "ExposeHeaders": ["ETag"],
            "MaxAgeSeconds": 3600,
        }
    ]
}


def main():
    settings = get_settings()
    s3 = settings.get_object_storage().s3_client

    for bucket in (settings.tamper_assets_bucket, settings.tamper_ingest_bucket):
        try:
            s3.put_bucket_cors(Bucket=bucket, CORSConfiguration=CORS_CONFIGURATION)
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("NoSuchBucket", "404"):
                raise SystemExit(f"Bucket {bucket} does not exist.")
            raise
        print(f"Applied CORS policy to {bucket}")


if __name__ == "__main__":
    main()
