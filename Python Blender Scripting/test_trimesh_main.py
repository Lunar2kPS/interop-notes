import sys
from pathlib import Path

import trimesh

def count_scene_geometry(glb_path: str):
    """
    Load a .glb/.gltf file and return total vertices and triangles
    across all mesh geometry in the scene.
    """
    scene_or_mesh = trimesh.load(glb_path, force="scene")

    total_vertices = 0
    total_triangles = 0

    # scene.geometry contains all mesh objects in the model
    for name, geom in scene_or_mesh.geometry.items():
        if not isinstance(geom, trimesh.Trimesh):
            continue

        total_vertices += len(geom.vertices)
        total_triangles += len(geom.faces)

    return total_vertices, total_triangles

def main():
    if len(sys.argv) != 2:
        print(f"Usage: python {Path(sys.argv[0]).name} model.glb")
        sys.exit(1)

    glb_file = sys.argv[1]
    vertices, triangles = count_scene_geometry(glb_file)

    print(f"File: {glb_file}")
    print(f"Total vertices: {vertices}")
    print(f"Total triangles: {triangles}")

main()
