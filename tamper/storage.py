from uuid import uuid7

import boto3

from botocore.config import Config
from botocore.exceptions import ClientError


class ObjectStorage:
    def __init__(
        self,
        endpoint_url: str,
        region_name: str,
    ):
        self.endpoint_url = endpoint_url
        self.region_name = region_name

        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            region_name=self.region_name,
            config=Config(signature_version="s3v4"),
        )

    def object_exists(self, bucket_name: str, key: str):
        try:
            self.s3_client.head_object(Bucket=bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise e

    def presign_get(
        self,
        bucket_name: str,
        key: str,
        content_type: str = "application/octet-stream",
        expires: int = 900,
    ):
        return self.s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket_name,
                "Key": key,
                "ResponseContentType": content_type,
            },
            ExpiresIn=expires,
        )

    def presign_put(self, bucket_name: str, key: str, expires: int = 900):
        return self.s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket_name,
                "Key": key,
            },
            ExpiresIn=expires,
            HttpMethod="PUT",
        )

    def download_object(self, bucket_name: str, key: str, local_filename: str):
        self.s3_client.download_file(
            Bucket=bucket_name,
            Key=key,
            Filename=local_filename,
        )

    def copy_object(
        self, src_bucket: str, src_key: str, dest_bucket: str, dest_key: str
    ):
        self.s3_client.copy_object(
            Bucket=dest_bucket,
            Key=dest_key,
            CopySource={"Bucket": src_bucket, "Key": src_key},
        )

    def delete_object(self, bucket_name: str, key: str):
        self.s3_client.delete_object(Bucket=bucket_name, Key=key)

    def upload_object(self, bucket_name: str, key: str, local_filename: str):
        self.s3_client.upload_file(
            Filename=local_filename,
            Bucket=bucket_name,
            Key=key,
        )


class AssetStorage:
    def __init__(self, object_storage: ObjectStorage, bucket_name: str):
        self.object_storage = object_storage
        self.bucket_name = bucket_name

    def _format_key(self, hex_digest: str) -> str:
        return f"assets/sha256/{hex_digest[:2]}/{hex_digest[2:4]}/{hex_digest}"

    def asset_file_exists(self, hex_digest: str) -> bool:
        key = self._format_key(hex_digest)
        return self.object_storage.object_exists(self.bucket_name, key)

    def presign_get(self, hex_digest: str, content_type: str) -> str:
        return self.object_storage.presign_get(
            self.bucket_name,
            self._format_key(hex_digest),
            content_type=content_type,
        )

    def download_asset_file(self, hex_digest: str, local_filename: str):
        return self.object_storage.download_object(
            self.bucket_name,
            self._format_key(hex_digest),
            local_filename,
        )

    def upload_asset_file(self, hex_digest: str, local_filename: str):
        return self.object_storage.upload_object(
            self.bucket_name,
            self._format_key(hex_digest),
            local_filename,
        )

    def copy_from(self, src_bucket: str, src_key: str, hex_digest: str):
        """Copies an object into this bucket under its content-addressed key"""
        self.object_storage.copy_object(
            src_bucket,
            src_key,
            self.bucket_name,
            self._format_key(hex_digest),
        )


class IngestStorage:
    def __init__(self, object_storage: ObjectStorage, bucket_name: str):
        self.object_storage = object_storage
        self.bucket_name = bucket_name

    def presign_put(self, ingest_id: str):
        key = f"{ingest_id}/{uuid7()}"
        url = self.object_storage.presign_put(self.bucket_name, key)
        return key, url

    def download(self, key: str, local_filename: str):
        self.object_storage.download_object(self.bucket_name, key, local_filename)

    def delete(self, key: str):
        self.object_storage.delete_object(self.bucket_name, key)
