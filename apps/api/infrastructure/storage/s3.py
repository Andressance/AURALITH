import os

import boto3
from botocore.config import Config


class S3StorageProvider:
    def __init__(
        self,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket: str | None = None,
        region: str = "us-east-1",
    ):
        self.endpoint = (
            endpoint
            or os.getenv("NEON_STORAGE_ENDPOINT", "")
            or os.getenv("NEON_URL", "")
        ).rstrip("/")
        self.bucket = bucket or os.getenv("NEON_STORAGE_BUCKET", "music")
        self.access_key = (
            access_key
            or os.getenv("NEON_ACCESS_KEY_ID", "")
            or os.getenv("AWS_ACCESS_KEY_ID", "")
        )
        self.secret_key = (
            secret_key
            or os.getenv("NEON_SECRET_ACCESS_KEY", "")
            or os.getenv("AWS_SECRET_ACCESS_KEY", "")
        )
        if not self.endpoint:
            raise RuntimeError("NEON_URL or NEON_STORAGE_ENDPOINT is required")
        if not self.access_key or not self.secret_key:
            raise RuntimeError(
                "NEON_ACCESS_KEY_ID and NEON_SECRET_ACCESS_KEY are required"
            )
        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=os.getenv("NEON_STORAGE_REGION", region),
            config=Config(s3={"addressing_style": "path"}),
        )

    def upload(self, key: str, content: bytes, content_type: str) -> str:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
        )
        return key

    def open(self, key: str):
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"]

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def exists(self, key: str) -> bool:
        try:
            self.size(key)
            return True
        except self.client.exceptions.NoSuchKey:
            return False

    def size(self, key: str) -> int:
        response = self.client.head_object(Bucket=self.bucket, Key=key)
        return int(response["ContentLength"])
