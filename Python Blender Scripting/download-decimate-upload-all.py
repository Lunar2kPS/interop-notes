import argparse
import asyncio
import os
import sys
import subprocess
import logging
import pg8000
import platform

from pathlib import Path
from typing import Any
from pg8000.legacy import Connection
from pg8000.exceptions import InterfaceError
from subprocess import CalledProcessError

from aws_cloud_system import AWSCloudSystem

logging.basicConfig(level=logging.INFO, format='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s', datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)
except ImportError:
    logger.error("Failed to import .env variables. Make sure that python-dotenv is installed.")

def get_connection() -> Connection:
    try:
        return pg8000.connect(
            host = os.environ["POSTGRES_HOST"],
            port = int(os.environ["POSTGRES_PORT"]),
            database = os.environ["POSTGRES_DATABASE"],
            user = os.environ["POSTGRES_USER"],
            password = os.environ["POSTGRES_PASSWORD"],
        )
    except InterfaceError:
        logger.error(f"Failed to connect to the database (is it running, and is your host correct?) at {os.environ['POSTGRES_HOST']} on port {os.environ['POSTGRES_PORT']}.")
        return None

def get_all_programs() -> list[dict[str, Any]]:
    conn = get_connection()
    if conn:
        with conn.cursor() as cursor:
            query = """
                SELECT
                    *******,
                    *******,
                    *******,
                    *******,
                    *******,
                    *******,
                    *******
                FROM *******.program_*******_stats
                WHERE *******
                    AND ******* > 0
                ORDER BY
                    ******* DESC,
                    ******* DESC,
                    ******* DESC,
                    ******* DESC,
                    *******;
            """
            params=()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            if rows:
                columns = [ desc[0] for desc in cursor.description ]
                lookup = [ dict(zip(columns, row)) for row in rows ]
                return lookup
    return None

def try_find_git_bash(bash_executable: dict[str, str]) -> bool:
    # NOTE: If bash cannot be found, assuming this is on Windows,
    if not bash_executable["git_bash"]:
        result = subprocess.run(
            [
                "cmd", "/C", "where bash"
            ],
            capture_output=True,
            text=True,
            check=True
        )

        # NOTE: Ignore paths like:
        #   - C:\Windows\System32\bash.exe (WSL bash, uses /mnt/c file paths and is in a different environment...)
        #   - C:\Users\ModLu\AppData\Local\Microsoft\WindowsApps\bash.exe (WSL bash...)

        # NOTE: Use paths like:
        #   - C:\Users\ModLu\AppData\Local\Programs\Git\usr\bin\bash.exe (Correct git bash... Oddly only shown in Python, not in cmd.exe)
        #   - C:\Program Files\Git\bin\bash.exe (Correct, but wasn't shown...)
        for line in result.stdout.splitlines():
            path = Path(line)
            if (path.exists()):
                print(path.as_posix())
                posix_path = path.as_posix()
                if "WindowsApps" in posix_path: # Ignore, WSL
                    continue
                if posix_path == "C:/Windows/System32/bash.exe": # Ignore, WSL
                    continue
                found_git_bash = str(path)
                logger.info(f"Found Git Bash at {found_git_bash}")
                bash_executable["value"] = found_git_bash
                bash_executable["git_bash"] = found_git_bash
            return True
    return False

def run_decimation(bash_executable: dict[str, str], decimation_script_folder: Path, relative_program_*******_path: str, download_folder: Path, output_folder: Path, blender_log_file_pattern: str, blender_main_log_file: str) -> bool:
    try:
        result = subprocess.run(
            [
                bash_executable["value"], (decimation_script_folder / "manual_decimation.sh").as_posix(),
                "--input-folder", download_folder.as_posix(),
                "--output-folder", output_folder.as_posix(),
                "--blender-log-file", (output_folder / blender_log_file_pattern).as_posix()
            ],
            capture_output=True,
            text=True,
            check=True
        )
        # NOTE: WSL bash failing to find a file path returns 127.
        if result.returncode == 127 and platform.system() == "Windows":
            if try_find_git_bash(bash_executable):
                # NOTE: Retry one more time:
                return run_decimation(bash_executable, decimation_script_folder, relative_program_*******_path, download_folder, output_folder, blender_main_log_file, blender_log_file_pattern)
        with open(output_folder / blender_main_log_file, "w", encoding="utf-8") as log_file:
            print(f"Process stdout: {result.stdout}", file=log_file)
            print(f"Process stderr: {result.stderr}", file=log_file)
        return result.returncode == 0
    except Exception as e:
        if platform.system() == "Windows" and try_find_git_bash(bash_executable):
            # NOTE: Retry one more time:
            return run_decimation(bash_executable, decimation_script_folder, relative_program_*******_path, download_folder, output_folder, blender_main_log_file, blender_log_file_pattern)
        with open(output_folder / blender_main_log_file, "w", encoding="utf-8") as log_file:
            print(f"Process stdout: {e.stdout}", file=log_file)
            print(f"Process stderr: {e.stderr}", file=log_file)
        logger.exception(f"Exit code {e.returncode} returned from decimation for {relative_program_*******_path}.")
    return False

def post_combine(decimation_script_folder: Path, relative_program_*******_path: str, input_folder: Path, output_folder: Path, output_file: Path, blender_log_file_pattern: str, blender_main_log_file: str) -> bool:
    try:
        result = subprocess.run(
            [
                sys.executable, (decimation_script_folder / "post_combine_main.py"),
                "--input-folder", input_folder,
                "--output-file", output_file,
                "--blender-log-file", output_file.parent / blender_log_file_pattern
            ],
            capture_output=True,
            text=True,
            check=True
        )
        with open(output_folder / blender_main_log_file, "w", encoding="utf-8") as log_file:
            print(f"Process stdout: {result.stdout}", file=log_file)
            print(f"Process stderr: {result.stderr}", file=log_file)
        return result.returncode == 0
    except Exception as e:
        with open(output_folder / blender_main_log_file, "w", encoding="utf-8") as log_file:
            print(f"Process stdout: {e.stdout}", file=log_file)
            print(f"Process stderr: {e.stderr}", file=log_file)
        logger.exception(f"Exit code {e.returncode} returned from decimation for {relative_program_*******_path}.")
        return False

async def main():
    parser = argparse.ArgumentParser(description="Scans S3 for ******* data and ouputs as JSON file(s).")
    parser.add_argument(
        "--blender-decimation-script-folder",
        type=Path,
        help="Path containing the Blender decimation scripts.",
    )
    args = parser.parse_args()

    decimation_script_folder : Path = args.blender_decimation_script_folder
    if not decimation_script_folder.exists():
        logger.error(f"Unable to proceed: Decimation folder does NOT exist at: {decimation_script_folder}")
        return 1

    # all_programs = get_all_programs()

    # all_programs = [
    #     {
    #         "*******": "???",
    #         "*******": "???",
    #         "*******": "",
    #         "*******": "???",
    #         "*******": ???,
    #         "*******": "???",
    #         "*******": "???"
    #     }
    # ]

    if all_programs:
        aws = AWSCloudSystem()
        aws.load_endpoints_from_env()

        for p in all_programs:
            ******* = p['*******']
            ******* = p['*******']
            ******* = p['*******']
            ******* = p['*******']
            ******* = p['*******']
            ******* = p['*******']
            ******* = p['*******']

            # NOTE: download_folder means input to the decimation stage (after the S3 download).
            root_folder = Path(f"vehicle_bodies/{*******}--{*******}--{*******}--{*******}")
            root_folder.mkdir(parents=True, exist_ok=True)

            *******_download_folder = root_folder / "*******"
            relative_program_*******_path=f"{*******}/{*******}/{*******}/{*******}"

            download_s3_keys = [ f"{relative_program_*******_path}/*******/{name}.glb" for name in ******* ]
            download_file_paths = [ *******_download_folder / f"{name}.glb" for name in ******* ]

            exists_on_s3 = []
            for key in download_s3_keys:
                exists_on_s3.append(await aws.file_exists(*******, *******, key))

            if not all(exists_on_s3):
                logger.warning(f"Skipping missing ******* part(s) on S3 for {relative_program_*******_path}.")
                continue

            if any(not path.exists() for path in download_file_paths):
                logger.info(f"Downloading for {relative_program_*******_path}...")
                *******_download_folder.mkdir(parents=True, exist_ok=True)

                tasks = [
                    asyncio.create_task(aws.download_file(*******, *******, key))
                    for key in download_s3_keys
                ]

                downloaded_file_bytes = await asyncio.gather(*tasks)
                for path, data in zip(download_file_paths, downloaded_file_bytes):
                    with open(path, "wb") as file:
                        file.write(data)

            lod0_*******_folder = *******_download_folder / "lod0"
            blender_log_file_pattern = f"blender_output_{*******}_$fileName.log"
            blender_main_log_file = f"blender_output_{*******}.log"

            bash_executable = {
                "value": "bash",
                "git_bash": ""
            }

            expected_lod0_part_files = [
                lod0_*******_folder / f"{name}.glb"
                for name in *******
            ]

            if any(not path.exists() for path in expected_lod0_part_files):
                logger.info(f"Running decimation for {relative_program_*******_path}...")
                if not run_decimation(bash_executable, decimation_script_folder, relative_program_*******_path, *******_download_folder, lod0_*******_folder, blender_log_file_pattern, blender_main_log_file):
                    continue

            post_combine_folder = root_folder / f"post_combine/lod0"
            post_combined_file_path = post_combine_folder / f"{*******}_*******.glb"
            post_combine_log_file = f"blender_post_combine_{*******}.log"

            if not post_combined_file_path.exists():
                logger.info(f"Running post-combine step for {relative_program_*******_path}")
                if not post_combine(decimation_script_folder, relative_program_*******_path, lod0_*******_folder, post_combine_folder, post_combined_file_path, post_combine_log_file, blender_main_log_file):
                    continue

                upload_s3_key = f"{*******}/{*******}/{*******}/{*******}/*******/lod0/{*******}_*******.glb"
                logger.info(f"Uploading to S3 at: {upload_s3_key}")
                with open(post_combined_file_path, "rb") as file:
                    file_bytes = file.read()
                    await aws.upload_file(*******, *******, upload_s3_key, file_bytes, "model/gltf-binary")

asyncio.run(main())
