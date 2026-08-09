import os
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
    valueA = ""
    valueB = 0
    valueC = ""
    program_path=f"{valueA}/{valueB}/{valueC}/"
    output_folder=f"C:/dev/testing/body-decimation/{valueA}--{valueB}--{valueC}"

    async for folder_name in aws.get_subfolder_names(endpoint, bucket, program_path, recursive=False):
        print(f"{folder_name}:", end="")
        s3_key = f"{program_path}{folder_name}/{folder_name}_some_file.glb"
        if await aws.file_exists(endpoint, bucket, s3_key):
            print(f"    FOUND FILE! Downloading...", end="")
            data = await aws.download_file(endpoint, bucket, s3_key)
            file_name = Path(s3_key).name

            output_path = Path(f"{output_folder}/{file_name}")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as file:
                file.write(data)
            print(f"Output written to {output_path}")
        print("")

asyncio.run(main())
