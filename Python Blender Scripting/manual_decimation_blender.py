"""
Manual Blender Decimation Helper Program (BLENDER PORTION)

This script is expected to be run indirectly, with `blender --background --python ./helpers/manual_decimation_blender.py -- --input-file PATH --output-file PATH`, for example.
This already happens from manual_decimation_main.py, so this script is called from there.

Currently, I am testing with the following alternative to 10% COLLAPSE decimation,
    which may reduce more triangles, and have a better distribution of detail vs. lack of detail:
1. Degenerate Dissolve, with a threshold of 0.001, which is 10x higher than the default 0.0001,
2. Merge (Vertices) by Distance, with a threshold of 0.001, which is 10x higher than the default 0.0001,
3. Decimation (Modifier) using Planar decimation type (decimate_type="DISSOLVE"), with a 15° Angle Limit,
    which should know that flatter planes/surfaces can be really (more) decimated heavily than curved parts of the mesh.

"""

import argparse
import logging
import math
import sys

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

    # NOTE: These were somewhat of a 2nd iteration of decimation, but the Planar ("DISSOLVE") type of Decimate Modifier did NOT do quite what we wanted:
    # 10% COLLAPSE decimation:
    # decimate_modifier.decimate_type = "COLLAPSE"
    # decimate_modifier.ratio = 0.2
    # bpy.ops.object.modifier_apply(modifier=decimate_modifier.name)

    # Extra, in case we wanted to triangulate:
    # triangulate_modifier = obj.modifiers.new(name="Triangulate", type="TRIANGULATE")

    # ALTERNATIVE to 10% COLLAPSE decimation:
    # bpy.ops.object.mode_set(mode="EDIT")
    # bpy.ops.mesh.dissolve_degenerate(threshold=0.001)               # Mesh → Clean Up → Degenerate Dissolve
    # bpy.ops.mesh.remove_doubles(use_centroid=True, threshold=0.001) # Mesh → Clean Up → Merge by Distance
    # bpy.ops.object.mode_set(mode='OBJECT')

    # decimate_modifier = obj.modifiers.new(name="Decimate", type="DECIMATE")
    # decimate_modifier.decimate_type = "DISSOLVE"
    # decimate_modifier.angle_limit = 15 * (math.pi / 180) # 15° Angle limit
    # bpy.ops.object.modifier_apply(modifier=decimate_modifier.name)
    # --- --- ---

    def apply_decimation(self, mesh_name: str):
        self.logger.info("Applying decimation... (apply_decimation)")

        # Ensure Object mode for object-level ops
        if bpy.context.object and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        scene_objects = list(bpy.context.scene.objects)
        self.logger.info(f"Found {len(scene_objects)} scene objects.")

        # 1) Delete empty transform objects
        empty_objects = [obj for obj in scene_objects if obj.type == "EMPTY"]
        if empty_objects:
            self.logger.info(f"Deleting {len(empty_objects)} empty transform object(s)...")
            bpy.ops.object.select_all(action="DESELECT")
            for obj in empty_objects:
                obj.select_set(True)
            bpy.context.view_layer.objects.active = empty_objects[0]
            bpy.ops.object.delete()

        self.logger.info(f"We found {len(empty_objects)} empty objects.")

        # Refresh after deletion
        scene_objects = list(bpy.context.scene.objects)

        # 2) Delete empty meshes, keep only non-empty meshes
        empty_meshes = []
        mesh_objects = []
        for obj in scene_objects:
            if obj.type != "MESH":
                continue

            if obj.data is None or len(obj.data.vertices) == 0:
                empty_meshes.append(obj)
            else:
                mesh_objects.append(obj)
        self.logger.info(f"We found {len(empty_meshes)} empty meshes.")

        if empty_meshes:
            self.logger.info(f"Deleting {len(empty_meshes)} empty mesh object(s)...")
            bpy.ops.object.select_all(action="DESELECT")
            for obj in empty_meshes:
                obj.select_set(True)
            bpy.context.view_layer.objects.active = empty_meshes[0]
            bpy.ops.object.delete()

        if not mesh_objects:
            self.logger.warning("No non-empty mesh objects found in scene after cleanup.")
            return {}

        # 3) Add per-mesh vertex groups and build mapping
        object_to_group_id = {}

        bpy.ops.object.select_all(action="DESELECT")

        for i, obj in enumerate(mesh_objects):
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)

            vg = obj.vertex_groups.new(name=f"Group {i}")
            all_vertex_indices = [v.index for v in obj.data.vertices]
            if all_vertex_indices:
                vg.add(all_vertex_indices, 1.0, "REPLACE")

            object_to_group_id[obj.name] = i
            self.logger.info(f"Vertex group mapping: {obj.name} -> Group {i}")

            obj.select_set(False)

        # 4) Join remaining meshes
        bpy.ops.object.select_all(action="DESELECT")
        for obj in mesh_objects:
            obj.select_set(True)

        bpy.context.view_layer.objects.active = mesh_objects[0]

        # TODO: We must figure out what pivot point we want to use for the combined mesh...
        self.logger.info(f"Joining {len(mesh_objects)} non-empty mesh object(s)...")
        bpy.ops.object.join()

        joined_obj = bpy.context.view_layer.objects.active
        joined_obj.name = mesh_name
        if joined_obj.data is not None:
            joined_obj.data.name = mesh_name
        self.logger.info(f"Joined mesh name: {joined_obj.name}")

        # 5) Run cleanup/decimation once on final mesh
        try:
            self.logger.info(f"Selected all {len(joined_obj.data.vertices)} vertices (total {len(bpy.context.scene.objects)} objects in scene).")
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")

            # NOTE: For some reason, Delete Loose deselects all vertices in Blender! We must reselect them after performing Delete Loose.
            #   And to be safe, I made us re-select all vertices after EACH decimation operation, regardless!

            bpy.ops.mesh.dissolve_degenerate(threshold=0.0001)                          # Mesh → Clean Up → Degenerate Dissolve
            bpy.ops.mesh.select_all(action="SELECT")

            bpy.ops.mesh.remove_doubles(use_centroid=True, threshold=0.0001)            # Mesh → Clean Up → Merge by Distance
            bpy.ops.mesh.select_all(action="SELECT")

            bpy.ops.mesh.delete_loose(use_verts=True, use_edges=True, use_faces=True)   # Mesh → Clean Up → Delete Loose
            bpy.ops.mesh.select_all(action="SELECT")

            bpy.ops.mesh.dissolve_limited(angle_limit=2 * (math.pi / 180))              # Mesh → Clean Up → Limited Dissolve
            bpy.ops.mesh.select_all(action="SELECT")

            bpy.ops.mesh.decimate(ratio=0.3)                                            # Mesh → Clean Up → Decimate Geometry
            bpy.ops.mesh.select_all(action="SELECT")

            # IMPORTANT: After decimation, there are a ton of loose triangles and duplicate vertices.
            #   Let's apply a 2nd pass of removing doubles/merge by distance:
            bpy.ops.mesh.remove_doubles(use_centroid=True, threshold=0.0001)            # Mesh → Clean Up → Merge by Distance
            bpy.ops.mesh.select_all(action="SELECT")
        except Exception as e:
            self.logger.error(f"Failed to apply mesh decimation: {e}")
            raise
        finally:
            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.select_all(action="SELECT")
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            self.logger.info(f"Finished decimation with {len(joined_obj.data.vertices)} vertices.")

        try:
            # Also for mesh normals, let's clear custom split normals, sharp faces,
            for attribute_name in ("custom_normal", "sharp_face"):
                attr = joined_obj.data.attributes.get(attribute_name)
                if attr is not None:
                    joined_obj.data.attributes.remove(attr)

            bpy.ops.mesh.customdata_custom_splitnormals_clear()

            # And just do an auto-smooth by angle:
            bpy.ops.object.shade_auto_smooth(use_auto_smooth=True, angle=60 * (math.pi / 180))
            bpy.ops.object.modifier_apply(modifier="Smooth by Angle")
            self.logger.info(f"Finished normals cleanup with {len(joined_obj.data.vertices)} vertices.")
        except Exception as e:
            self.logger.exception("Failed to clean up normals on %s.", joined_obj.name)
            raise

        self.logger.info(f"Final object/group mapping: {object_to_group_id}")
        return object_to_group_id

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

    parser = argparse.ArgumentParser(description="(Helper Program) Blender Python Mesh Decimation Worker")
    parser.add_argument("--input-file",
                        help="The input .glb file to process.")
    parser.add_argument("--output-file",
                        help="Where to write the output .glb file to. This will overwrite if the file already exists.")
    parser.add_argument("--input-folder",
                        help="Optional: process all .glb files in this folder (non-recursive).")
    parser.add_argument("--output-folder",
                        help="Optional: output folder for files when using --input-folder.")
    args = parser.parse_args(parse_script_args(sys.argv))

    logger = logging.getLogger(__name__)
    logger.info("Starting (Helper Program) Blender Python Mesh Decimation.")

    # Validate inputs: require either a file pair or a folder pair (or both)
    has_file_pair = bool(args.input_file and args.output_file)
    has_folder_pair = bool(args.input_folder and args.output_folder)
    if not has_file_pair and not has_folder_pair:
        parser.error("Provide either --input-file and --output-file, or --input-folder and --output-folder.")
        return 1

    processor = SimpleBlenderProcessor()

    def process_one(in_path: Path, out_path: Path):
        try:
            logger.info("Processing %s -> %s", in_path.as_posix(), out_path.as_posix())
            out_path.parent.mkdir(parents=True, exist_ok=True)
            processor.clear_scene()
            processor.import_glb(in_path)
            processor.apply_decimation(in_path.stem)
            processor.export_glb(out_path)
            logger.info("Output to: %s", out_path.as_posix())
        except Exception as e:
            logger.exception("Failed processing %s: %s", in_path.as_posix(), e)
            raise

    # If file pair provided, process it once
    if has_file_pair:
        process_one(Path(args.input_file), Path(args.output_file))

    # If folder pair provided, iterate non-recursively over *.glb
    if has_folder_pair:
        input_folder = Path(args.input_folder)
        output_folder = Path(args.output_folder)
        if not input_folder.is_dir():
            logger.error("--input-folder is not a directory: %s", input_folder.as_posix())
        else:
            for p in sorted(input_folder.iterdir()):
                if p.is_file() and p.suffix.lower() == ".glb":
                    out_p = output_folder / p.name
                    process_one(p, out_p)

if __name__ == "__main__":
    main()
