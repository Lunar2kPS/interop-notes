"""
Manual Blender Decimation Helper Program (BLENDER PORTION)

This script is expected to be run indirectly, with `blender --background --python ./helpers/manual_decimation_blender.py`, for example.
This already happens from manual_decimation_main.py, so this script is called from there.

Currently, I am testing with the following alternative to 10% COLLAPSE decimation,
    which may reduce more triangles, and have a better distribution of detail vs. lack of detail:
1. Degenerate Dissolve, with a threshold of 0.001, which is 10x higher than the default 0.0001,
2. Merge (Vertices) by Distance, with a threshold of 0.001, which is 10x higher than the default 0.0001,
3. Decimation (Modifier) using Planar decimation type (decimate_type="DISSOLVE"), with a 20° Angle Limit,
    which should know that flatter planes/surfaces can be really (more) decimated heavily than curved parts of the mesh.

"""

import argparse
import logging
import math
import sys

from pathlib import Path

import bpy


class SimpleBlenderProcessor:
    def __init__(self, decimation_ratio: float):
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        self.logger.info("NAME = " + self.__class__.__name__)
        self.decimation_ratio = decimation_ratio

    def clear_scene(self):
        self.logger.info("Clearing scene...")
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()

        for block in bpy.data.meshes:
            if block.users == 0:
                bpy.data.meshes.remove(block)
        for block in bpy.data.materials:
            if block.users == 0:
                bpy.data.materials.remove(block)
        for block in bpy.data.images:
            if block.users == 0:
                bpy.data.images.remove(block)

    def import_glb(self, file_path: Path):
        self.logger.info("Importing GLB...")
        bpy.ops.import_scene.gltf(filepath=str(file_path))

    def export_glb(self, file_path: Path):
        self.logger.info("Exporting GLB...")
        bpy.ops.export_scene.gltf(
            filepath=str(file_path),
            check_existing=False,
            export_format="GLB",
            use_selection=False,
            export_apply=True,
            export_animations=True,
            export_optimize_animation_size=True,

            export_draco_mesh_compression_enable=True,
            export_draco_mesh_compression_level=6,
            export_draco_position_quantization=14,
            export_draco_normal_quantization=10,
            export_draco_texcoord_quantization=12,
            export_draco_color_quantization=10,
            export_draco_generic_quantization=12
        )

    def apply_decimation(self):
        self.logger.info(f"Applying decimation (decimation_ratio = {self.decimation_ratio})...")
        for obj in bpy.context.scene.objects:
            if obj.type == "MESH":
                bpy.context.view_layer.objects.active = obj
                obj.select_set(True)

                try:
                    # ALTERNATIVE to 10% COLLAPSE decimation:
                    bpy.ops.object.mode_set(mode="EDIT")
                    bpy.ops.mesh.dissolve_degenerate(threshold=0.001)               # Mesh → Clean Up → Degenerate Dissolve
                    bpy.ops.mesh.remove_doubles(use_centroid=True, threshold=0.001) # Mesh → Clean Up → Merge by Distance
                    bpy.ops.object.mode_set(mode='OBJECT')

                    decimate_modifier = obj.modifiers.new(name="Decimate", type="DECIMATE")
                    decimate_modifier.decimate_type = "DISSOLVE"
                    decimate_modifier.angle_limit = 20 * (math.pi / 180) # 20° Angle limit
                    # --- --- ---

                    # 10% COLLAPSE decimation:
                    # decimate_modifier.decimate_type = "COLLAPSE"
                    # decimate_modifier.ratio = self.decimation_ratio

                    # Extra, in case we wanted to triangulate:
                    # triangulate_modifier = obj.modifiers.new(name="Triangulate", type="TRIANGULATE")

                    bpy.ops.object.modifier_apply(modifier=decimate_modifier.name)
                except Exception as exc:
                    self.logger.error(f"Failed to apply mesh decimation to {obj.name}: {exc}")

                obj.select_set(False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="(Helper Program) Blender Python Mesh Decimation Worker")
    parser.add_argument("--input-file",
                        help="The input .glb file to process.")
    parser.add_argument("--output-file",
                        help="Where to write the output .glb file to. This will overwrite if the file already exists.")
    parser.add_argument("--decimation-ratio", type=float, default=0.1,
                        help="Defines the amount of triangles to leave behind, expressed as a percentage between 0 and 1.")
    parser.add_argument("--input-folder",
                        help="Optional: process all .glb files in this folder (non-recursive).")
    parser.add_argument("--output-folder",
                        help="Optional: output folder for files when using --input-folder.")
    return parser


def parse_script_args(argv: list[str]) -> list[str]:
    if "--" in argv:
        return argv[argv.index("--") + 1:]
    return argv[1:]


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    args = build_parser().parse_args(parse_script_args(sys.argv))

    logger = logging.getLogger(__name__)
    logger.info("Starting (Helper Program) Blender Python Mesh Decimation.")

    # Validate inputs: require either a file pair or a folder pair (or both)
    has_file_pair = bool(args.input_file and args.output_file)
    has_folder_pair = bool(args.input_folder and args.output_folder)
    if not has_file_pair and not has_folder_pair:
        parser = build_parser()
        parser.error("Provide either --input-file and --output-file, or --input-folder and --output-folder.")

    processor = SimpleBlenderProcessor(args.decimation_ratio)

    def process_one(in_path: Path, out_path: Path):
        try:
            logger.info("Processing %s -> %s", in_path.as_posix(), out_path.as_posix())
            out_path.parent.mkdir(parents=True, exist_ok=True)
            processor.clear_scene()
            processor.import_glb(in_path)
            processor.apply_decimation()
            processor.export_glb(out_path)
            logger.info("Output to: %s", out_path.as_posix())
        except Exception as exc:
            logger.exception("Failed processing %s: %s", in_path.as_posix(), exc)

    # If file pair provided, process it once
    if has_file_pair:
        process_one(Path(args.input_file), Path(args.output_file))

    # If folder pair provided, iterate non-recursively over *.glb
    if has_folder_pair:
        input_folder = Path(args.input_folder)
        output_folder = Path(args.output_folder)
        if not input_folder.is_dir():
            logger.error("--input-folder is not a directory: %s", input_folder.as_posix())
            raise SystemExit(2)

        for p in sorted(input_folder.iterdir()):
            if p.is_file() and p.suffix.lower() == ".glb":
                out_p = output_folder / p.name
                process_one(p, out_p)


main()