"""MinIO storage service for managing file uploads and access."""

from datetime import timedelta
from minio import Minio
from minio.error import S3Error
import logging

logger = logging.getLogger(__name__)

# Lazy initialization for storage service
_storage_service = None


class MinIOStorage:
    """Service for managing file storage in MinIO (S3-compatible object storage)."""
    
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
        external_endpoint: str = None,
        region: str = None,
    ):
        """Initialize MinIO client.
        
        Args:
            endpoint: MinIO server endpoint (e.g., 'localhost:9000')
            access_key: MinIO access key
            secret_key: MinIO secret key
            bucket: Default bucket name for file storage
            secure: Whether to use HTTPS (default: False for development)
            external_endpoint: External endpoint for presigned URLs (optional, defaults to endpoint)
            region: AWS region (optional, defaults to config value)
        """
        from app.config import settings
        # MinIO uses SigV4; region affects signing. We default to config value which is
        # the typical MinIO default and also avoids a GetBucketLocation call during presign.
        self.region = region or settings.aws_region_value

        # Internal client (used for bucket ops / uploads inside the docker network)
        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            region=self.region,
        )
        self.bucket = bucket
        self.endpoint = endpoint
        self.external_endpoint = external_endpoint or endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.secure = secure

        # External client (used ONLY for generating presigned URLs with externally reachable host)
        # Note: host is part of the SigV4 signed headers; do NOT generate with internal host and then string-replace.
        self.external_client = Minio(
            endpoint=self.external_endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            region=self.region,
        )
        logger.info(f"MinIO client initialized for endpoint: {endpoint}, bucket: {bucket}")
    
    def ensure_bucket_exists(self) -> None:
        """Create bucket if it doesn't exist.
        
        Checks if the configured bucket exists and creates it with default permissions
        if it doesn't exist.
        
        Raises:
            S3Error: If bucket creation fails
        """
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Created bucket: {self.bucket}")
            else:
                logger.debug(f"Bucket already exists: {self.bucket}")
        except S3Error as e:
            logger.error(f"Failed to ensure bucket exists: {e}")
            raise

    def upload_file(self, file_content: bytes, task_id: str, filename: str, content_type: str = "application/pdf") -> str:
        """Upload file to MinIO.
        
        Uploads file content to MinIO with object naming pattern: {task_id}/{filename}
        
        Args:
            file_content: File content as bytes
            task_id: Task identifier for organizing files
            filename: Original filename
            content_type: MIME type of the file (default: application/pdf)
        
        Returns:
            str: Object name (path) in MinIO
        
        Raises:
            S3Error: If upload fails
        """
        from io import BytesIO
        
        # Construct object name with pattern {task_id}/{filename}
        object_name = f"{task_id}/{filename}"
        
        try:
            # Ensure bucket exists before upload
            self.ensure_bucket_exists()
            
            # Upload file using BytesIO stream
            file_stream = BytesIO(file_content)
            file_size = len(file_content)
            
            self.client.put_object(
                bucket_name=self.bucket,
                object_name=object_name,
                data=file_stream,
                length=file_size,
                content_type=content_type
            )
            
            logger.info(f"Uploaded file to MinIO: {object_name} ({file_size} bytes)")
            return object_name
            
        except S3Error as e:
            logger.error(f"Failed to upload file {object_name}: {e}")
            raise
    
    def get_presigned_url(self, object_name: str, expires: int = None) -> str:
        """Generate presigned URL for secure file access.
        
        Creates a time-limited signed URL that allows temporary access to the file
        without requiring authentication.
        
        Args:
            object_name: Object path in MinIO (e.g., 'task_id/filename.pdf')
            expires: URL expiration time in seconds (default: from config)
        
        Returns:
            str: Presigned URL for file access
        
        Raises:
            S3Error: If URL generation fails
        """
        from app.config import settings
        if expires is None:
            expires = settings.presigned_url_expires
        try:
            # Convert seconds to timedelta as required by MinIO client
            expiry_timedelta = timedelta(seconds=expires)
            
            url = self.external_client.presigned_get_object(
                bucket_name=self.bucket,
                object_name=object_name,
                expires=expiry_timedelta
            )
            
            logger.debug(f"Generated presigned URL for {object_name} (expires in {expires}s)")
            return url
            
        except S3Error as e:
            logger.error(f"Failed to generate presigned URL for {object_name}: {e}")
            raise


def get_storage_service() -> MinIOStorage:
    """Get or create the singleton storage service instance.
    
    Returns:
        MinIOStorage: Singleton storage service instance
    """
    global _storage_service
    if _storage_service is None:
        from app.config import settings
        _storage_service = MinIOStorage(
            endpoint=settings.minio_endpoint,
            external_endpoint=settings.minio_external_endpoint,
            region=settings.aws_region,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_bucket,
            secure=settings.minio_secure
        )
    return _storage_service


# Create singleton instance for convenience
storage_service = get_storage_service()
