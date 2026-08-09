import os
import re
import logging
import asyncio
from aws_cloud_system import AWSCloudSystem
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s', datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)

async def main():
    try:
        from dotenv import load_dotenv
        _env_path = Path(__file__).parent / ".env"
        load_dotenv(_env_path)
    except ImportError:
        pass

    aws = AWSCloudSystem()
    aws.load_endpoints_from_env()

    endpoint = os.environ['S3_ENDPOINT_0']
    bucket = os.environ['S3_ENDPOINT_0_BUCKET_0']
    source_folder=Path(f"C:/dev/testing/decimation")

    local_program_pattern = re.compile(r"^(?P<valueA>.*)--(?P<valueB>.*)--(?P<valueC>.*)$")
    some_file_pattern = re.compile(r"(?P<tkv>.*)_some_file.glb")

    for path in source_folder.iterdir():
        if path.is_dir():
            folder_match = local_program_pattern.match(path.name)
            if folder_match:
                    valueA = folder_match.group("valueA")
                    valueB = folder_match.group("valueB")
                    valueC = folder_match.group("valueC")
                    print(f"Processing Program: {valueA}/{valueB}/{valueC}/")
            lod0_subfolder = path / "lod0"
            if lod0_subfolder.exists():
                for lod0_path in lod0_subfolder.iterdir():
                    if lod0_path.is_file():
                        file_match = some_file_pattern.match(lod0_path.name)
                        if file_match:
                             tkv = file_match.group("tkv")
                             with open(lod0_path, "rb") as file:
                                file_bytes = file.read()
                                s3_key = f"{valueA}/{valueB}/{valueC}/{tkv}/lod0/{tkv}_some_file.glb"
                                print(f"    Uploading to S3 at: {s3_key}")
                                await aws.upload_file(endpoint, bucket, s3_key, file_bytes, "model/gltf-binary")

asyncio.run(main())
