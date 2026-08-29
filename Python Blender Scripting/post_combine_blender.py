import argparse
import logging
import sys
import gc

from pathlib import Path

import bpy

class SimpleBlenderProcessor:
    def __init__(self):
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        self.logger.info("NAME = " + self.__class__.__name__)

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

    def join_all(self, mesh_name: str) -> bool:
        self.logger.info("Preparing to join all meshes...")

        # Ensure Object mode for object-level operations.
        if bpy.context.object and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        scene_objects = list(bpy.context.scene.objects)
        self.logger.info(f"Found {len(scene_objects)} scene objects.")

        # 1. Delete all empty and 0-vertex objects.
        empty_objects = [
            obj
            for obj in scene_objects
            if obj.type == "EMPTY"
            or (obj.type == "MESH" and len(obj.data.vertices) == 0)
        ]
        if empty_objects:
            self.logger.info(f"Deleting {len(empty_objects)} empty transform object(s)...")
            bpy.ops.object.select_all(action="DESELECT")
            for obj in empty_objects:
                obj.select_set(True)
            bpy.context.view_layer.objects.active = empty_objects[0]
            bpy.ops.object.delete()

        self.logger.info(f"We found {len(empty_objects)} empty objects.")

        # 2. Join meshes.
        mesh_objects = [
            obj for obj in bpy.context.scene.objects
            if obj.type == "MESH"
        ]
        self.logger.info("Applying transformations and setting to world-origin pivots on all mesh objects before joining...")
        bpy.ops.object.select_all(action="DESELECT")
        for obj in mesh_objects:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = mesh_objects[0]

        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        bpy.context.scene.cursor.location = (0, 0, 0)
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR')

        self.logger.info(f"Joining {len(bpy.context.selected_objects)} non-empty mesh object(s)...")
        bpy.ops.object.join()

        joined_obj = bpy.context.view_layer.objects.active
        joined_obj.name = mesh_name
        if joined_obj.data is not None:
            joined_obj.data.name = mesh_name
        self.logger.info(f"Joined mesh name: {joined_obj.name}")

        # NOTE: This is at a point where memory usually spikes.
        self.logger.info("Reducing memory usage...")
        bpy.data.orphans_purge()
        gc.collect()

        return True


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

    logger = logging.getLogger(__name__)
    try:
        logger.info("Starting (Helper Program) Blender Post-Decimation Combine Helper Program.")
        parser = argparse.ArgumentParser(description="(Helper Program) Blender Post-Decimation Combine Worker")
        parser.add_argument("--input-folder",
                            help="Optional: process all .glb files in this folder (non-recursive).")
        parser.add_argument("--output-file",
                            help="Where to write the output .glb file to. This will overwrite if the file already exists.")
        args = parser.parse_args(parse_script_args(sys.argv))


        has_input_and_output = bool(args.input_folder and args.output_file)
        if not has_input_and_output:
            parser.error("Provide both --input-folder and --output-file.")
            sys.exit(1)
        input_folder = Path(args.input_folder)
        if not input_folder.is_dir():
            logger.error("--input-folder is not a directory: %s", input_folder.as_posix())
            sys.exit(1)

        logger.info("Turning off Blender's global undo to save on memory...")
        bpy.context.preferences.edit.use_global_undo = False
        processor = SimpleBlenderProcessor()

        def process_one(input_folder: Path, out_path: Path):
            try:
                logger.info("Processing %s -> %s", input_folder.as_posix(), out_path.as_posix())
                out_path.parent.mkdir(parents=True, exist_ok=True)
                processor.clear_scene()

                for p in sorted(input_folder.iterdir()):
                    if p.is_file() and p.suffix.lower() == ".glb":
                        processor.import_glb(p)
                if processor.join_all(out_path.stem):
                    processor.export_glb(out_path)
                    logger.info("Output to: %s", out_path.as_posix())
                else:
                    logger.error("Unable to join meshes and export (did you input a file that has only empty objects?).")
                    sys.exit(1)
            except Exception as e:
                logger.exception("Failed processing %s: %s", input_folder.as_posix(), e)
                raise

        process_one(input_folder, Path(args.output_file))
        return 0
    except Exception as e:
        logger.exception("An error occurred during the Blender Python post-decimation combine step.")
        sys.exit(1)

if __name__ == "__main__":
    main()
