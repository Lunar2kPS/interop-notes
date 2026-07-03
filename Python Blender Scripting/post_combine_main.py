import argparse
import logging
import subprocess

from pathlib import Path

DEFAULT_BLENDER_LOG_FILE = "blender_combine_output.log"

def run_blender_subprocess(args: argparse.Namespace) -> int:
    logger = logging.getLogger(__name__)

    blender_script = Path(__file__).with_name("post_combine_blender.py").resolve()
    blender_command = [
        args.blender_executable,
        "--background",
        "--python", blender_script.as_posix(),
        "--",
    ]
    if hasattr(args, "input_folder"):
        blender_command.append("--input-folder")
        blender_command.append(Path(args.input_folder).as_posix())
    if hasattr(args, "output_file"):
        blender_command.append("--output-file")
        blender_command.append(Path(args.output_file).as_posix())

    blender_log_file = args.blender_log_file
    logger.info("Launching Blender subprocess:")
    logger.info(blender_command)
    blender_log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(blender_log_file, "w", encoding="utf-8") as fh:
        completed_process = subprocess.run(
            blender_command,
            check=False,
            stdout=fh,
            stderr=subprocess.STDOUT,
            text=True,
        )

    logger.info("Blender output captured to: %s", blender_log_file.as_posix())
    if completed_process.returncode != 0:
        logger.error("Blender exited with code %s. See log file for details.", completed_process.returncode)
    return completed_process.returncode


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(__name__)
    logger.info("Blender Post-Decimation Combine Helper Program")

    parser = argparse.ArgumentParser(description="Run Blender post-decimation combine in a subprocess")
    parser.add_argument("--input-folder",
                        help="Optional: process all .glb files in this folder (non-recursive).")
    parser.add_argument("--output-file",
                        help="Where to write the output .glb file to. This will overwrite if the file already exists.")
    parser.add_argument("--blender-log-file", type=Path,
                        default=Path.cwd() / DEFAULT_BLENDER_LOG_FILE,
                        help=f"Path where Blender stdout/stderr should be written. Defaults to ./{DEFAULT_BLENDER_LOG_FILE}.")
    args = parser.parse_args()

    has_input_and_output = bool(args.input_folder and args.output_file)
    if not has_input_and_output:
        parser.error("Provide both --input-folder and --output-file.")
        return 1

    def make_namespace(input_folder: Path, output_file: Path, log_file: Path):
        return argparse.Namespace(
            blender_executable="blender",
            blender_log_file=log_file,
            input_folder=input_folder.as_posix(),
            output_file=output_file.as_posix()
        )

    success_count = 0
    total_count = 0

    if has_input_and_output:
        ns = make_namespace(Path(args.input_folder), Path(args.output_file), args.blender_log_file)
        return_code = run_blender_subprocess(ns)
        total_count += 1
        if return_code  == 0:
            success_count += 1

    final_message = f"Completed post-decimation combining, with a success rate of {success_count} / {total_count}.\n"
    if success_count >= 1:
        logger.info(final_message)
        return 0
    else:
        logger.error(final_message)
        return 1

main()
