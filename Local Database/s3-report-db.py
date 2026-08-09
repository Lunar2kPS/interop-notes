import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pg8000

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv not installed; use system/env vars (Ex: in container)

def get_connection():
    return pg8000.connect(
        host = os.environ["POSTGRES_HOST"],
        port = int(os.environ["POSTGRES_PORT"]),
        database = os.environ["POSTGRES_DATABASE"],
        user = os.environ["POSTGRES_USER"],
        password = os.environ["POSTGRES_PASSWORD"],
    )

UPSERT_SQL = """
INSERT INTO s3analysis.program_tkv_stats (
    s3_endpoint,
    s3_bucket,
    s3_parent_path,
    program_code,
    model_year,
    engineering_release,
    tkv,
    jt_file_count,
    glb_file_count,
    drc_file_count,
    parts_of_interest_glb_count,
    parts_of_interest_drc_count,
    vehicle_shell_all_glb_count,
    vehicle_body_all_glb_count,
    has_final_vehicle_shell,
    has_final_vehicle_body,
    last_updated_at
) VALUES (
    %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s
)
ON CONFLICT (
    s3_endpoint,
    s3_bucket,
    s3_parent_path,
    program_code,
    model_year,
    engineering_release,
    tkv
) DO UPDATE SET
    jt_file_count               = EXCLUDED.jt_file_count,
    glb_file_count              = EXCLUDED.glb_file_count,
    drc_file_count              = EXCLUDED.drc_file_count,
    parts_of_interest_glb_count = EXCLUDED.parts_of_interest_glb_count,
    parts_of_interest_drc_count = EXCLUDED.parts_of_interest_drc_count,
    vehicle_shell_all_glb_count = EXCLUDED.vehicle_shell_all_glb_count,
    vehicle_body_all_glb_count  = EXCLUDED.vehicle_body_all_glb_count,
    has_final_vehicle_shell     = EXCLUDED.has_final_vehicle_shell,
    has_final_vehicle_body      = EXCLUDED.has_final_vehicle_body,
    last_updated_at             = EXCLUDED.last_updated_at;
"""


def load_scan_file(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def flatten_scan(scan_json) -> list[dict[str, Any]]:
    """
    Turn the nested JSON into a list of flat dicts, one per TKV.
    """
    s3_endpoint = scan_json.get("s3Endpoint", "")
    s3_bucket = scan_json.get("s3Bucket", "")
    s3_parent_path = scan_json.get("s3FolderPath", "") or ""

    rows = []
    now = datetime.now(timezone.utc)

    for program in scan_json.get("programs", []):
        program_code = program.get("programCode")
        model_year = program.get("year")
        engineering_release = program.get("engineeringRelease")

        for tkv in program.get("tkvs", []):
            row = {
                "s3_endpoint": s3_endpoint,
                "s3_bucket": s3_bucket,
                "s3_parent_path": s3_parent_path,
                "program_code": program_code,
                "model_year": model_year,
                "engineering_release": engineering_release,
                "tkv": tkv.get("tkv"),

                "jt_file_count": tkv.get("jtFileCount", 0),
                "glb_file_count": tkv.get("glbFileCount", 0),
                "drc_file_count": tkv.get("drcFileCount", 0),
                "parts_of_interest_glb_count": tkv.get("partsOfInterestGLBCount", 0),
                "parts_of_interest_drc_count": tkv.get("partsOfInterestDRCCount", 0),
                "vehicle_shell_all_glb_count": tkv.get("vehicleShellAllGLBCount", 0),
                "vehicle_body_all_glb_count": tkv.get("vehicleBodyAllGLBCount", 0),
                "has_final_vehicle_shell": tkv.get("hasFinalVehicleShell", False),
                "has_final_vehicle_body": tkv.get("hasFinalVehicleBody", False),

                "last_updated_at": now,
            }
            rows.append(row)

    return rows

def upsert_rows(conn, rows):
    with conn.cursor() as cur:
        for row in rows:
            params = (
                row["s3_endpoint"],
                row["s3_bucket"],
                row["s3_parent_path"],
                row["program_code"],
                row["model_year"],
                row["engineering_release"],
                row["tkv"],
                row["jt_file_count"],
                row["glb_file_count"],
                row["drc_file_count"],
                row["parts_of_interest_glb_count"],
                row["parts_of_interest_drc_count"],
                row["vehicle_shell_all_glb_count"],
                row["vehicle_body_all_glb_count"],
                row["has_final_vehicle_shell"],
                row["has_final_vehicle_body"],
                row["last_updated_at"],
            )
            cur.execute(UPSERT_SQL, params)
    conn.commit()

def main():
    parser = argparse.ArgumentParser(description="Load S3 scan JSON into Postgres.")
    parser.add_argument(
        "path",
        help="Path to a single JSON file or a folder containing JSON files",
    )
    args = parser.parse_args()

    p = Path(args.path)
    if p.is_file():
        files = [p]
    elif p.is_dir():
        files = sorted(p.glob("*.json"))
    else:
        parser.error(f"Path not found: {p}")

    if not files:
        print("No JSON files found to process.")
        return

    conn = get_connection()
    try:
        total_rows = 0
        for path in files:
            try:
                file_name = path.name
                scan_json = load_scan_file(str(path))
                rows = flatten_scan(scan_json)
                upsert_rows(conn, rows)
                total_rows += len(rows)
                print(f"Upserted {len(rows)} rows from {file_name}")
            except Exception as e:
                print(f"Failed to load and upsert data for file: {file_name}")
                print(f"{e}")
        print(f"\nUpserted a total of {total_rows} rows into s3analysis.program_tkv_stats.")
    finally:
        conn.close()

main()
