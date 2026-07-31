from curses import BUTTON_CTRL
import io
import os

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

s3_client = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION", "ap-south-1"),
)

BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

def upload_file_to_s3(file_bytes: bytes, s3_key: str, content_type: str = "text/csv") -> str:
    try:
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=file_bytes,
            ContentType=content_type,
        )
        return s3_key
    except ClientError as e:
        raise Exception(f"Failed to upload file to S3: {str(e)}")

def download_file_from_s3(s3_key: str) -> bytes:
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
        return response["Body"].read()
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "NoSuchKey":
            raise Exception(f"File not found in S3: {s3_key}")
        raise Exception(f"Failed to download file from S3: {str(e)}")

def generate_presigned_url(s3_key: str, expires_in: int = 3600) -> str:
    try:
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_NAME, "Key": s3_key},
            ExpiresIn=expires_in,
        )
        return url
    except ClientError as e:
        raise Exception(f"Failed to generate presigned URL: {str(e)}")

def get_s3_key(user_id: str, filename: str) -> str:
    return f"uploads/{user_id}/{filename}"