import argparse
import logging
import json
import os
import time
import sys
import asyncio
from asyncio.events import AbstractEventLoop

import threading
from threading import Thread
from queue import Queue, Empty
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from svg_builder import SVGBuilder

GRACE_PERIOD = 4

logging.basicConfig(level=logging.INFO, format='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s', datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)

# WARNING: Consider this class' callbacks to run on a different thread, used by the file system watcher.
#   For example, DO NOT pass in asyncio.Events in, because they are NOT thread-safe.
class SegmentationMaskFileHandler(FileSystemEventHandler):
    def __init__(self, output_folder: Path, work_queue : Queue[SVGBuilder]):
        super().__init__()
        self.output_folder = output_folder
        self.work_queue = work_queue

    def on_created(self, event):
        is_file = not event.is_directory
        if is_file:
            file_path = Path(event.src_path)
            if file_path.suffix == ".json":
                json_path = file_path
                png_path = json_path.with_suffix(".png")
                if png_path.exists():
                    self.work_queue.put_nowait(SVGBuilder(png_path, json_path, self.output_folder))

async def grace_timer(python_done_event: asyncio.Event, grace_period: int = GRACE_PERIOD):
    await asyncio.sleep(grace_period) # NOTE: This may be cancelled if more SVGs come through. Then a new call of this method will replace this one afterwards.
    logger.info(f"No new requests received after {grace_period}sec of receiving \"exit\" from C#. Completing...")
    python_done_event.set()

def restart_timer(python_done_event: asyncio.Event, timer_state: dict):
    previous_timer = timer_state["task"]
    if previous_timer is not None:
        logger.info("TIMER CANCEL.")
        previous_timer.cancel()

    logger.info("TIMER CREATE.")
    timer_state["task"] = asyncio.create_task(grace_timer(python_done_event))

async def tcp_read_loop(
    reader: asyncio.StreamReader,
    cs_done_event: asyncio.Event,
    python_done_event: asyncio.Event,
    timer_state: dict
):
    try:
        while True:
            line = await reader.readline()
            if not line:
                break

            # NOTE: utf-8-sig is the same as utf-8 encoding, except it ignores the BOM (byte order mark) marking it as UTF-8, if it exists.
            #   Just in-case the C# side were to send it, this side would still be OK and not receive the "garbage" \ufeff (EF BB BF) at the beginning of the first message.
            message = line.decode("utf-8-sig").rstrip("\r\n")
            logger.info(f"C#: {message}")
            if message == "exit":
                break
    finally:
        cs_done_event.set()
        restart_timer(python_done_event, timer_state) # NOTE: This is just the FIRST call to starting off the timer. It may be interrupted and restarted if any more SVGs come through during the grace period.

async def tcp_write_loop(
    writer: asyncio.StreamWriter,
    cs_done_event: asyncio.Event,
    python_done_event: asyncio.Event
):
    await cs_done_event.wait()
    await python_done_event.wait()

    logger.info("Sending the Python completion message.")
    writer.write(b"complete\n")
    logger.info("Sent Python complete message.")
    await writer.drain()

def validate_path(value: Path, param_name: str, must_exist: bool):
    if value is None or not str(value).strip():
        raise ValueError(f"{param_name} must not be None nor empty.")
    if must_exist and not value.exists():
        raise FileNotFoundError(f"Path given by {param_name} does not exist: \"{value.as_posix()}\"")

def svg_thread(thread_event: threading.Event, work_queue: Queue[SVGBuilder], timer_message_queue: Queue[int]):
    while not thread_event.is_set():
        try:
            # IMPORTANT: If we used .get() here, we would block forever until the next queue item, and would NOT be able to break out of the loop from thread_event.is_set().
            svg_builder = work_queue.get_nowait()

            timer_message_queue.put_nowait(1) # NOTE: This is a notification for the START of a new SVG to generate.
            svg_path = svg_builder.generate_svg()
            if svg_path:
                logger.info(f"Generated SVG file at: {svg_path.as_posix()}")
            work_queue.task_done()
            timer_message_queue.put_nowait(2) # NOTE: This is a notification for the END of a newly-generated SVG.
        except Empty:
            time.sleep(0.1)
    logger.info("SVG Thread complete.")

async def main() -> int:
    try:
        logger.info(f"Python SVG Generator Program (pid {os.getpid()})")
        current_folder = Path(os.getcwd())
        inner_folder = current_folder / "scripts/svg-generator"
        if inner_folder.exists():
            logger.warning("Changing working directory to the correct scripts/svg-generator folder.")
            os.chdir(inner_folder)

        parser = argparse.ArgumentParser(description="Generates SVG files based on a mask.")
        parser.add_argument(
            "-m",
            "--mask",
            help="The file path of a grayscale .png mask image.",
            type=Path,
        )
        parser.add_argument(
            "--labels",
            type=Path,
            help="The file path of a JSON file containing a dictionary of key-value pairs under a field named \"values\", representing part label information."
        )
        parser.add_argument(
            "-o",
            "--output-folder",
            default=Path("./svg-output"),
            type=Path,
            help="The output folder path for .svg files."
        )
        parser.add_argument(
            "--watch-mode",
            action="store_true",
            help="Using watch mode makes this program wait for new files to be saved to ./masks, and will trigger generation of .svg files automatically upon .json label files being completed."
        )
        args = parser.parse_args()

        # NOTE: Use this if you want to test easily:
        # args = type("Args", (), {
        #     "output_folder": Path("./svg-output"),
        #     "watch_mode": True
        # })()
        validate_path(args.output_folder, "--output-folder", must_exist=False)

        if args.watch_mode:
            cs_tcp_file_path = Path("./cs-tcp.json")
            if not cs_tcp_file_path.exists():
                raise FileNotFoundError(f"The {cs_tcp_file_path} file is required to connect back to Unity/C#.")
            with open(cs_tcp_file_path, "r", encoding="utf-8") as file:
                cs_json = json.load(file)
            if "csPort" not in cs_json:
                raise RuntimeError(f"\"csPort\" field is required in the JSON.")
            cs_port = cs_json['csPort']
            if type(cs_port) is not int:
                raise TypeError(f"Incorrect type for csPort: {type(cs_port)}. It must be an int value.")

            # IMPORTANT: These are NOT thread-safe like threading.Event(), so these should ONLY be accessed on the main thread and the async event loop.
            cs_done_event = asyncio.Event()
            python_done_event = asyncio.Event()
            timer_state = {
                "task": None
            }
            logger.info(f"FOUND C# PORT: {cs_port}")

            args.output_folder.mkdir(parents=True, exist_ok=True)
            logger.info(f"Clearing {args.output_folder.as_posix()}.")
            for file in args.output_folder.iterdir():
                if file.is_file():
                    file.unlink()
            mask_folder = Path("./masks")
            mask_folder.mkdir(exist_ok=True)

            reader, writer = await asyncio.open_connection("127.0.0.1", cs_port)
            read_task = asyncio.create_task(tcp_read_loop(reader, cs_done_event, python_done_event, timer_state))
            write_task = asyncio.create_task(tcp_write_loop(writer, cs_done_event, python_done_event))

            # NOTE: This is a thread-safe queue:
            work_queue : Queue[SVGBuilder] = Queue()
            timer_message_queue: Queue[int] = Queue()

            observer = Observer()
            observer.schedule(
                SegmentationMaskFileHandler(args.output_folder, work_queue),
                path=mask_folder.as_posix(),
                recursive=False,
            )

            observer.start()
            logger.info(f"Monitoring directory: {mask_folder.as_posix()}")

            try:
                thread_event = threading.Event()
                processing_thread = Thread(target=svg_thread, args=(thread_event, work_queue, timer_message_queue))
                processing_thread.start()

                while processing_thread.is_alive():
                    try:
                        message = timer_message_queue.get_nowait()
                        if cs_done_event.is_set():
                            restart_timer(python_done_event, timer_state)
                        timer_message_queue.task_done()
                    except Empty:
                        pass
                    # IMPORTANT: asyncio.sleep(...) **yields** control so the background task can run!
                    #   Without any awaits, our method would continue blocking synchronously and none of our asyncio.create_tasks(...) above would be able to even start!
                    # time.sleep(0.1)
                    await asyncio.sleep(0.2)

                    if not thread_event.is_set() and python_done_event.is_set():
                        logger.info("SETTING thread_event")
                        thread_event.set()
                logger.info("Waiting for file system watcher to stop...")
            except KeyboardInterrupt:
                logger.info("Stopping file system watcher...")
                if not python_done_event.is_set():
                    python_done_event.set()
                if not thread_event.is_set():
                    thread_event.set()
            finally:
                observer.stop()
                observer.join()

            logger.info("Waiting for asyncio.gather(...)")
            await asyncio.gather(read_task, write_task, return_exceptions=True)
        else:
            validate_path(args.mask, "--mask", must_exist=True)
            validate_path(args.labels, "--labels", must_exist=True)

            svg_builder = SVGBuilder(args.mask, args.labels, args.output_folder)
            svg_path = svg_builder.generate_svg()

            if svg_path:
                logger.info(f"Generated SVG file at: {svg_path.as_posix()}")
        logger.info("Main program completed.")
        return 0
    except ConnectionRefusedError:
        logger.error("Connection refused: is the Unity/C# side running?")
    except Exception as e:
        logger.exception(f"An unhandled exception occurred in the main program: {e}")
        return 1

asyncio.run(main())
