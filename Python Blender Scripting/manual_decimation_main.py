"""
Manual Blender Decimation Helper Program

See the README.md for more info on this program.
This file is runnable with python directly, because it runs Blender as a subprocess, which calls manual_decimation_blender.py.

COMMAND LINE USAGE:
    python ./helpers/manual_decimation_main.py --input-file PATH --output-file PATH --input-folder PATH --output-folder PATH
"""

import argparse
import logging
import os
import subprocess

from pathlib import Path

DEFAULT_BLENDER_LOG_FILE = "blender_output.log"


def run_blender_subprocess(args: argparse.Namespace) -> int:
    logger = logging.getLogger(__name__)

    blender_script = Path(__file__).with_name("manual_decimation_blender.py").resolve()
    blender_command = [
        args.blender_executable,
        "--background",
        "--python", str(blender_script),
        "--",
        "--input-file", str(Path(args.input_file)),
        "--output-file", str(Path(args.output_file)),
        "--decimation-ratio", str(args.decimation_ratio),
    ]
    blender_log_file = args.blender_log_file

    logger.info("Launching Blender subprocess for " + (args.input_file or ""))

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
    parser.add_argument("--decimation-ratio", type=float, default=0.1,
                        help="Defines the amount of triangles to leave behind, expressed as a percentage between 0 and 1. 0.1 = 10%% of original, 0.5 = 50%% of original (typical: 0.1-1.0).")
    parser.add_argument("--input-folder",
                        help="Optional: process all .glb files in this folder (non-recursive).")
    parser.add_argument("--output-folder",
                        help="Optional: output folder for files when using --input-folder.")
    parser.add_argument("--blender-log-file", type=Path,
                        default=Path.cwd() / DEFAULT_BLENDER_LOG_FILE,
                        help=f"Path where Blender stdout/stderr should be written. Defaults to ./{DEFAULT_BLENDER_LOG_FILE}. For batch runs a per-file .log will be created next to this path.")
    args = parser.parse_args()

    fallback_file = False
    fallback_folder = False
    if (args.input_file or "").strip() and args.input_file == args.output_file:
        fallback_file = True
        logger.warning("Input and output file paths match! Automatically add an _D suffix to the output file.")
    if (args.input_file or "").strip() and not (args.output_file or "").strip():
        fallback_file = True
        logger.info("Output file path missing while input file provided. Defaulting to the input file path plus a '_D' suffix for output.")
    if (args.input_folder or "").strip() and args.input_folder == args.output_folder:
        fallback_folder = True
        logger.warning("Input and output folders match! Automatically adding an _D suffix to the output.")
    if (args.input_folder or "").strip() and not (args.output_folder or "").strip():
        fallback_folder = True
        logger.info("Output folder path missing while input folder provided. Defaulting to the input folder path plus a '_D' suffix for output.")

    if fallback_file:
        args.output_file = (args.input_file or "") + "_D"
    if fallback_folder:
        args.output_folder = (args.input_folder or "") + "_D"

    # Determine requested mode
    has_file_pair = bool(args.input_file and args.output_file)
    has_folder_pair = bool(args.input_folder and args.output_folder)
    if not has_file_pair and not has_folder_pair:
        parser.error("Provide either --input-file and --output-file, or --input-folder and --output-folder.")

    def make_namespace(input_file: Path, output_file: Path, log_file: Path):
        return argparse.Namespace(
            blender_executable="blender",
            blender_log_file=log_file,
            input_file=input_file.as_posix(),
            output_file=output_file.as_posix(),
            decimation_ratio=args.decimation_ratio,
        )

    # Process a single file pair
    if has_file_pair:
        ns = make_namespace(Path(args.input_file), Path(args.output_file), args.blender_log_file)
        rc = run_blender_subprocess(ns)
        if rc != 0:
            raise SystemExit(rc)

    # Process a folder pair (non-recursive). Create per-file logs in the same folder as configured log file.
    if has_folder_pair:
        in_dir = Path(args.input_folder)
        out_dir = Path(args.output_folder)
        if not in_dir.is_dir():
            parser.error(f"--input-folder is not a directory: {in_dir.as_posix()}")

        base_log = args.blender_log_file
        base_name = base_log.stem
        for file in sorted(in_dir.iterdir()):
            if file.is_file() and file.suffix.lower() == ".glb":
                out_file = out_dir / file.name
                per_file_log = (base_log.parent / f"{base_name}_{file.stem}.log") if base_log.parent else Path(f"{base_name}_{file.stem}.log")
                ns = make_namespace(file, out_file, per_file_log)
                rc = run_blender_subprocess(ns)
                if rc != 0:
                    logger.error("Subprocess failed for %s (rc=%s)", file.as_posix(), rc)
    raise SystemExit(0)


main()