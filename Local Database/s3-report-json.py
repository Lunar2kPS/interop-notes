import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s', datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)

from aws_cloud_system import AWSCloudSystem

DATA_REPORTS_FOLDER = "data-reports"
DATA_REPORTS_OUTPUT_FOLDER = f"{DATA_REPORTS_FOLDER}/output/found-valueDs"
PROGRAM_PATTERNS_FILE_PATH = f"{DATA_REPORTS_FOLDER}/Patterns.json"

@dataclass
class StructA:
    valueA: str = ""
    valueB: int = -1
    valueC: str = ""
    valueD: str = ""

    def get_path(self) -> str:
        # Rough equivalent of valueD.GetPath()
        # Adjust if your actual C# GetPath() does something different.
        return f"{self.valueA}/{self.valueB}/{self.valueC}/{self.valueD}"

@dataclass
class StructB:
    valueA: str
    valueB: int
    valueC: str
    valueD: str

    jtFileCount: int = 0
    glbFileCount: int = 0
    drcFileCount: int = 0
    hasSomeFile: bool = False

    @classmethod
    def from_valueD(cls, valueD: StructA) -> "StructB":
        return cls(
            valueA=valueD.valueA,
            valueB=valueD.valueB,
            valueC=valueD.valueC,
            valueD=valueD.valueD,
        )

@dataclass
class ProgramIDInfo:
    valueA: str
    valueB: int
    valueC: str
    valueDs: List[StructB] = field(default_factory=list)

class S3TKVReport:
    def __init__(self, s3_endpoint: str, s3_bucket: str, s3_parent_path: str, aws: AWSCloudSystem):
        self.s3_endpoint = s3_endpoint
        self.s3_bucket = s3_bucket
        self.s3_parent_path = s3_parent_path
        self.aws = aws

    @property
    def output_file_path(self) -> str:
        suffix = f" - {self.s3_bucket}" if self.s3_bucket.strip() else ""
        return os.path.join(DATA_REPORTS_OUTPUT_FOLDER, f"AWS S3 TKVs{suffix}.json")

    async def _count_files_by_extension(self, folder: str, file_extension: str) -> int:
        count = 0
        async for file_name in self.aws.get_file_names(self.s3_endpoint, self.s3_bucket, folder, recursive=False):
            if file_name.endswith(file_extension):
                count += 1
        return count

    async def _count_files_by_regex(self, folder: str, pattern: re.Pattern) -> int:
        count = 0
        async for file_name in self.aws.get_file_names(self.s3_endpoint, self.s3_bucket, folder, recursive=False):
            if pattern.search(file_name):
                count += 1
        return count

    async def run_internal(self, cancel_event: Optional[asyncio.Event] = None):
        """
        cancel_event: if provided, will be used to signal cancellation.
        """
        report = {}

        try:
            with open(PROGRAM_PATTERNS_FILE_PATH, "r", encoding="utf-8") as f:
                in_json_root = json.load(f)

            # Parse valueB range
            valueB_range_min = -1
            valueB_range_max = -1

            valueBs_obj = in_json_root.get("valueBs")
            if isinstance(valueBs_obj, dict):
                if "min" in valueBs_obj and isinstance(valueBs_obj["min"], int):
                    valueB_range_min = valueBs_obj["min"]
                if "max" in valueBs_obj and isinstance(valueBs_obj["max"], int):
                    valueB_range_max = valueBs_obj["max"]

            known_engineering_releases = in_json_root.get("knownValueCs", []) or []
            known_engineering_releases = [ str(x) for x in known_engineering_releases ]

            # Parse valueDPatterns (regex strings)
            valueD_patterns_raw = in_json_root.get("valueDPatterns", []) or []
            valueD_patterns = [ re.compile(str(p)) for p in valueD_patterns_raw ]

            self._throw_if_cancelled(cancel_event)

            # ---- Local nested functions matching your C# structure ----

            async def try_match_all(program_code_folder: str) -> List[StructA]:
                results: List[StructA] = []
                await try_match_valueBs(program_code_folder, results)
                return results

            async def try_match_valueBs(program_code_folder: str, results: List[StructA],):
                async for subfolder in self.aws.get_subfolders(self.s3_endpoint, self.s3_bucket, program_code_folder, recursive=False):
                    name = self.aws.get_s3_folder_name(self.s3_endpoint, self.s3_bucket, subfolder)
                    try:
                        valueB_value = int(name)
                    except ValueError:
                        valueB_value = None

                    if valueB_value is not None and valueB_range_min <= valueB_value <= valueB_range_max:
                        progress = StructA()  # fresh copy per match
                        progress.valueA = self.aws.get_s3_folder_name(self.s3_endpoint, self.s3_bucket, program_code_folder)
                        progress.valueB = valueB_value
                        await try_match_engineering_releases(subfolder, progress, results)

                    self._throw_if_cancelled(cancel_event)

            async def try_match_engineering_releases(valueB_folder: str, progress: StructA, results: List[StructA]):
                async for subfolder in self.aws.get_subfolders(self.s3_endpoint, self.s3_bucket, valueB_folder, recursive=False):
                    name = self.aws.get_s3_folder_name(self.s3_endpoint, self.s3_bucket, subfolder)
                    if name in known_engineering_releases:
                        progress_er = StructA(
                            valueA=progress.valueA,
                            valueB=progress.valueB,
                            valueC=name,
                            valueD=progress.valueD,
                        )
                        await try_match_valueD_names(subfolder, progress_er, results)

                    self._throw_if_cancelled(cancel_event)

            async def try_match_valueD_names(engineering_release_folder: str, progress: StructA, results: List[StructA]):
                async for subfolder in self.aws.get_subfolders(self.s3_endpoint, self.s3_bucket, engineering_release_folder, recursive=False):
                    name = self.aws.get_s3_folder_name(self.s3_endpoint, self.s3_bucket, subfolder)
                    for r in valueD_patterns:
                        m = r.search(name)
                        if m:
                            # In C#, adding struct (value-type) -> copy.
                            # Here, explicitly copy via new StructA.
                            valueD = StructA(
                                valueA=progress.valueA,
                                valueB=progress.valueB,
                                valueC=progress.valueC,
                                valueD=m.group(0),
                            )
                            results.append(valueD)
                            break

                    self._throw_if_cancelled(cancel_event)

            # ---- Main traversal ----

            program_lookup: Dict[str, ProgramIDInfo] = {}
            async for subfolder in self.aws.get_subfolders(self.s3_endpoint, self.s3_bucket, self.s3_parent_path, recursive=False):
                found_valueDs = await try_match_all(subfolder)

                for valueD in found_valueDs:
                    out_valueD = StructB.from_valueD(valueD)
                    folder_path = valueD.get_path()

                    # NOTE: S3 folder paths must end with "/"
                    out_valueD.jtFileCount = await self._count_files_by_extension(f"{folder_path}/jt/", ".jt")
                    out_valueD.glbFileCount = await self._count_files_by_extension(f"{folder_path}/glb/", ".glb")
                    out_valueD.drcFileCount = await self._count_files_by_extension(f"{folder_path}/drc/", ".drc")

                    some_pattern = re.compile(re.escape(out_valueD.valueD) + r"_some_file\.glb")
                    out_valueD.hasSomeFile = await self._count_files_by_regex(f"{folder_path}/some_file/", some_pattern) >= 1

                    key = f"{valueD.valueA}/{valueD.valueB}/{valueD.valueC}"
                    prog = program_lookup.get(key, ProgramIDInfo(valueD.valueA, valueD.valueB, valueD.valueC))
                    prog.valueDs.append(out_valueD)
                    program_lookup[key] = prog

                self._throw_if_cancelled(cancel_event)

            # ---- Build final JSON ----

            # Sort programs by key
            sorted_programs = [ program_lookup[k] for k in sorted(program_lookup.keys()) ]
            programs_array = []
            for prog in sorted_programs:
                # Convert dataclasses → nested dict (ProgramIDInfo + StructB)
                prog_dict = asdict(prog)
                programs_array.append(prog_dict)

            report["s3Endpoint"] = self.s3_endpoint
            report["s3Bucket"] = self.s3_bucket
            report["s3ParentPath"] = self.s3_parent_path
            report["programs"] = programs_array

        except asyncio.CancelledError:
            # Mirror OperationCanceledException behavior
            raise
        except Exception as e:
            logger.exception(f"Error listing objects.")
            raise
        finally:
            # Write report JSON to disk (pretty-printed)
            os.makedirs(DATA_REPORTS_OUTPUT_FOLDER, exist_ok=True)
            with open(self.output_file_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=4)
                f.write("\n")

    @staticmethod
    def _throw_if_cancelled(cancel_event: Optional[asyncio.Event]):
        if cancel_event is not None and cancel_event.is_set():
            raise asyncio.CancelledError()

async def main():
    try:
        from dotenv import load_dotenv
        _env_path = Path(__file__).parent / ".env"
        load_dotenv(_env_path)
    except ImportError:
        pass

    aws = AWSCloudSystem()
    aws.load_endpoints_from_env()

    for i, ep in enumerate(aws.endpoints):
        logger.info(f"Endpoint {i}: {ep.endpoint_url}, buckets =\n    {"\n    ".join(str(x) for x in ep.buckets)}")
    total_time = 0
    total_buckets = 0
    logger.info("Beginning reports...")
    for endpoint in aws.endpoints:
        for bucket in endpoint.buckets:
            start = time.perf_counter()
            try:
                report = S3TKVReport(
                    s3_endpoint=endpoint.endpoint_url,
                    s3_bucket=bucket,
                    s3_parent_path="",
                    aws=aws,
                )
                await report.run_internal()
            except Exception as e:
                logger.exception(f"An exception occurred during execution of {endpoint.endpoint_url}, bucket {bucket}")
            elapsed = time.perf_counter() - start
            total_time += elapsed
            total_buckets += 1
            logger.info(f"Completed {endpoint.endpoint_url}, bucket {bucket} in {elapsed:.3f} sec!")
    logger.info(f"Total time to iterate through {len(aws.endpoints)} endpoints and {total_buckets} buckets: {total_time:.3f}sec.")

asyncio.run(main())
