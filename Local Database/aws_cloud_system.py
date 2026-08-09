import re
import io
import logging
import os
from typing import AsyncIterator

import boto3
from botocore.client import BaseClient
from botocore.client import Config
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s', datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)

S3_PATH_REGEX = re.compile(
    r"^(?P<endpoint>.+\.com)/(?P<bucket>(?![0-9]+.?[0-9]*.?[0-9]*.?[0-9]*$)"
    r"(?!xn--)(?!.*--)(?!^.*\.$)[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])?)/(?P<key>.+)"
)

def create_s3_client(
    endpoint_url: str,
    access_key: str,
    secret_key: str,
    region: str,
    use_path_style: bool = True,
) -> BaseClient:
    s3_config = Config(s3={"addressing_style": "path" if use_path_style else "virtual"})

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=s3_config,
    )

class AWSS3Endpoint:
    """
    Represents one S3 endpoint that can serve multiple buckets.
    """

    endpoint_url: str
    access_key: str
    secret_key: str
    region: str = None
    use_path_style: bool = True
    buckets: list[str] = []

    s3_client: BaseClient = None

    def __init__(self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        region: str,
        use_path_style: bool,
        buckets: list[str]
    ):
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.use_path_style = use_path_style
        self.buckets = buckets
        self.s3_client: BaseClient = create_s3_client(
            self.endpoint_url,
            self.access_key,
            self.secret_key,
            self.region,
            self.use_path_style,
        )

class AWSCloudSystem:
    def __init__(self):
        self._endpoints: list[AWSS3Endpoint] = []

    @property
    def endpoints(self) -> tuple[AWSS3Endpoint, ...]:
        """
        Returns all configured S3 endpoints (read-only view).
        """
        return tuple(self._endpoints)

    @property
    def endpoint_count(self) -> int:
        return len(self._endpoints)

    def add_s3_endpoint(
        self,
        endpoint_url: str,
        buckets: list[str],
        access_key: str,
        secret_key: str,
        region: str = None,
        use_path_style: bool = True,
    ) -> bool:
        """
        Add one endpoint with a list of buckets.
        Returns False if an endpoint with same endpoint_url & buckets already exists.
        """
        endpoint_url = endpoint_url or ""
        new_bucket_set = set(buckets)

        for ep in self._endpoints:
            if (ep.endpoint_url or "") == endpoint_url and set(ep.buckets) == new_bucket_set:
                # Already exists; don't add duplicate
                return False

        endpoint = AWSS3Endpoint(
            endpoint_url=endpoint_url,
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            use_path_style=use_path_style,
            buckets=list(buckets),
        )
        self._endpoints.append(endpoint)
        return True

    def load_endpoints_from_env(self, use_all_buckets: bool = False, max_endpoints: int = 10, max_buckets: int = 50):
        """
        Reads env vars like:
            S3_ENDPOINT_0
            S3_ENDPOINT_0_BUCKET_0, S3_ENDPOINT_0_BUCKET_1, ...
            S3_ACCESS_KEY_0
            S3_SECRET_KEY_0
        and calls aws.add_s3_endpoint(...) with a list of buckets for each index.

        max_endpoints and max_buckets are just safety caps to avoid infinite loops
        if env is malformed.
        """

        for i in range(max_endpoints):
            try:
                endpoint_key = f"S3_ENDPOINT_{i}"
                access_key_key = f"S3_ACCESS_KEY_{i}"
                secret_key_key = f"S3_SECRET_KEY_{i}"

                endpoint = os.getenv(endpoint_key)
                access_key = os.getenv(access_key_key)
                secret_key = os.getenv(secret_key_key)

                # If no credentials, assume this index is not defined
                if not access_key or not secret_key:
                    break

                # Endpoint can be empty/None for AWS default
                endpoint = endpoint if endpoint else None

                if use_all_buckets:
                    buckets = self._list_buckets_for_endpoint(
                        endpoint_url=endpoint,
                        access_key=access_key,
                        secret_key=secret_key,
                        region=None,
                        use_path_style=True,
                    )
                else:
                    buckets: list[str] = []
                    # We don't require contiguous indices; skip blanks but keep going
                    for b in range(max_buckets):
                        bucket_env = f"S3_ENDPOINT_{i}_BUCKET_{b}"
                        bucket = os.getenv(bucket_env, "")
                        if not bucket:
                            break
                        buckets.append(bucket)

                if not buckets:
                    break
                self.add_s3_endpoint(
                    endpoint_url=endpoint,
                    buckets=buckets,
                    access_key=access_key,
                    secret_key=secret_key,
                    region=None,
                    use_path_style=True,
                )
            except Exception as e:
                logger.exception(f"An error occurred while iterating endpoint \"{endpoint}\".")

    def _list_buckets_for_endpoint(
        self,
        endpoint_url: str | None,
        access_key: str,
        secret_key: str,
        region: str | None = None,
        use_path_style: bool = True,
    ) -> list[str]:
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region or "us-east-1",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(
                s3={"addressing_style": "path" if use_path_style else "virtual"}
            ),
        )

        resp = s3.list_buckets()
        return [ b["Name"] for b in resp.get("Buckets", []) ]

    def _find_endpoint_for_bucket(
        self, endpoint_url: str, bucket: str
    ) -> tuple[AWSS3Endpoint, str]:
        """
        Find an endpoint that has this bucket.
        - If endpoint_url is provided, prefer that.
        - Otherwise, search all endpoints for the bucket.
        """
        svc = endpoint_url or ""

        # Prefer exact endpoint_url match when given
        if svc:
            for ep in self._endpoints:
                if (ep.endpoint_url or "") == svc and bucket in ep.buckets:
                    return ep, bucket

        # Fallback: any endpoint with that bucket
        for ep in self._endpoints:
            if bucket in ep.buckets:
                return ep, bucket

        raise KeyError(f"AWS S3 endpoint not found for endpoint={endpoint_url}, bucket={bucket}")

    # ---- Path helpers ----

    def try_parse_s3_path(self, path: str):
        """
        Returns (success: bool, endpoint_url, bucket, key).
        """
        m = S3_PATH_REGEX.match(path)
        if not m:
            return False, None, None, None
        endpoint_url = m.group("endpoint")
        bucket = m.group("bucket")
        key = m.group("key")
        return True, endpoint_url, bucket, key

    def get_s3_folder_name(self, endpoint_url: str, bucket: str, prefix_name: str) -> str:
        name = prefix_name
        last_index = name.rfind("/")
        second_to_last_index = name.rfind("/", 0, last_index) if last_index > 0 else -1

        if last_index > 0:
            if second_to_last_index >= 0:
                name = name[second_to_last_index + 1 : last_index]
            else:
                name = name[:last_index]
        return name

    # ---- Core operations ----
    # Note: all these are still endpoint+bucket aware; they just pick the
    # right endpoint for the bucket using _find_endpoint_for_bucket.

    async def file_exists(self, endpoint_url: str, bucket: str, key: str) -> bool:
        endpoint, _ = self._find_endpoint_for_bucket(endpoint_url, bucket)
        s3 = endpoint.s3_client
        try:
            s3.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as e:
            if e.response["ResponseMetadata"]["HTTPStatusCode"] == 404:
                return False
            raise

    async def folder_exists(self, endpoint_url: str, bucket: str, prefix: str) -> bool:
        endpoint, _ = self._find_endpoint_for_bucket(endpoint_url, bucket)
        s3 = endpoint.s3_client

        resp = s3.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix,
            MaxKeys=1,
        )
        return resp.get("KeyCount", 0) > 0

    async def upload_file(
        self,
        endpoint_url: str,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str = "image/jpg",
    ) -> bool:
        endpoint, _ = self._find_endpoint_for_bucket(endpoint_url, bucket)
        s3 = endpoint.s3_client

        f = io.BytesIO(data)
        resp = s3.put_object(Bucket=bucket, Key=key, Body=f, ContentType=content_type)
        status = resp.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
        return 200 <= status <= 299

    async def download_file(
        self,
        endpoint_url: str,
        bucket: str,
        key: str,
    ) -> bytes:
        endpoint, _ = self._find_endpoint_for_bucket(endpoint_url, bucket)
        s3 = endpoint.s3_client

        def _download(k: str) -> bytes:
            resp = s3.get_object(Bucket=bucket, Key=k)
            with resp["Body"] as body:
                return body.read()

        try:
            return _download(key)
        except Exception:
            index = key.find("glb/")
            if index >= 0:
                alt_key = key[:index] + "parts_of_interest/" + key[index + 4 :]
                return _download(alt_key)
            raise

    async def get_files(
        self,
        endpoint_url: str,
        bucket: str,
        folder_path: str,
        recursive: bool,
    ) -> AsyncIterator[str]:
        endpoint, _ = self._find_endpoint_for_bucket(endpoint_url, bucket)
        s3 = endpoint.s3_client

        continuation_token = None
        delimiter = None if recursive else "/"

        while True:
            kwargs = {
                "Bucket": bucket,
                "Prefix": folder_path,
            }
            if delimiter is not None:
                kwargs["Delimiter"] = delimiter
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token

            resp = s3.list_objects_v2(**kwargs)
            for obj in resp.get("Contents", []):
                yield obj["Key"]

            continuation_token = resp.get("NextContinuationToken")
            if not continuation_token:
                break

    async def get_file_names(
        self,
        endpoint_url: str,
        bucket: str,
        folder_path: str,
        recursive: bool,
    ) -> AsyncIterator[str]:
        import os

        async for key in self.get_files(endpoint_url, bucket, folder_path, recursive):
            yield os.path.basename(key)

    async def get_subfolders(
        self,
        endpoint_url: str,
        bucket: str,
        folder_path: str,
        recursive: bool,
    ) -> AsyncIterator[str]:
        endpoint, _ = self._find_endpoint_for_bucket(endpoint_url, bucket)

        s3 = endpoint.s3_client

        continuation_token = None
        delimiter = None if recursive else "/"

        while True:
            kwargs = {
                "Bucket": bucket,
                "Prefix": folder_path,
            }
            if delimiter is not None:
                kwargs["Delimiter"] = delimiter
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token

            resp = s3.list_objects_v2(**kwargs)
            for prefix in resp.get("CommonPrefixes", []):
                yield prefix["Prefix"]

            continuation_token = resp.get("NextContinuationToken")
            if not continuation_token:
                break

    async def get_subfolder_names(
        self,
        endpoint_url: str,
        bucket: str,
        folder_path: str,
        recursive: bool,
    ) -> AsyncIterator[str]:
        async for prefix in self.get_subfolders(endpoint_url, bucket, folder_path, recursive):
            yield self.get_s3_folder_name(endpoint_url, bucket, prefix)
