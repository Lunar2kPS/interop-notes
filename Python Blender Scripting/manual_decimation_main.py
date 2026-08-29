"""
Manual Blender Decimation Helper Program

See the README.md for more info on this program.
This file is runnable with python directly, because it runs Blender as a subprocess, which calls manual_decimation_blender.py.

COMMAND LINE USAGE:
    python ./helpers/manual_decimation_main.py --input-file PATH --output-file PATH --input-folder PATH --output-folder PATH
"""

import argparse
import logging
import subprocess

from pathlib import Path

DEFAULT_BLENDER_LOG_FILE = "blender_output.log"

def run_blender_subprocess(args: argparse.Namespace) -> int:
    logger = logging.getLogger(__name__)

    blender_script = Path(__file__).with_name("manual_decimation_blender.py").resolve()
    blender_command = [
        args.blender_executable,
        "--background",
        "--python", blender_script.as_posix(),
        "--",
    ]
    if hasattr(args, "input_file"):
        blender_command.append("--input-file")
        blender_command.append(Path(args.input_file).as_posix())
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
    logger.info("Manual Blender Decimation Helper Program")

    parser = argparse.ArgumentParser(description="Run Blender mesh decimation in a subprocess")
    parser.add_argument("--input-file",
                        help="The input .glb file to process.")
    parser.add_argument("--output-file",
                        help="Where to write the output .glb file to. This will overwrite if the file already exists.")
    parser.add_argument("--blender-log-file",
                        type=Path,
                        default=Path.cwd() / DEFAULT_BLENDER_LOG_FILE,
                        help=f"Path where Blender stdout/stderr should be written. Defaults to ./{DEFAULT_BLENDER_LOG_FILE}. For batch runs a per-file .log will be created next to this path.")
    args = parser.parse_args()

    fallback_file = False
    if (args.input_file or "").strip() and args.input_file == args.output_file:
        fallback_file = True
        logger.warning("Input and output file paths match! Automatically add an _D suffix to the output file.")
    if (args.input_file or "").strip() and not (args.output_file or "").strip():
        fallback_file = True
        logger.info("Output file path missing while input file provided. Defaulting to the input file path plus a '_D' suffix for output.")

    if fallback_file:
        args.output_file = str(Path(args.input_file).with_name(f"{Path(args.input_file).stem}_D{Path(args.input_file).suffix}"))

    # Determine requested mode
    has_file_pair = bool(args.input_file and args.output_file)
    if not has_file_pair:
        parser.error("You must provide --input-file and --output-file.")
        return 1

    def make_namespace(input_file: Path, output_file: Path, log_file: Path):
        return argparse.Namespace(
            blender_executable="blender",
            blender_log_file=log_file,
            input_file=input_file.as_posix(),
            output_file=output_file.as_posix()
        )

    success_count = 0
    total_count = 0

    # Process a single file pair
    if has_file_pair:
        ns = make_namespace(Path(args.input_file), Path(args.output_file), args.blender_log_file)
        return_code = run_blender_subprocess(ns)
        total_count += 1
        if return_code  == 0:
            success_count += 1

    final_message = f"Completed decimation, with a success rate of {success_count} / {total_count}.\n"
    if success_count >= 1:
        logger.info(final_message)
        return 0
    else:
        logger.error(final_message)
        return 1

main()
