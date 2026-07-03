using System;
using System.Threading.Tasks;
using UnityEngine;

namespace Carlos {
    public struct MeshCache {
        public Matrix4x4 transform;
        public Vector3[] vertices;
    }

    public class MeshCacheSet {
        public Transform root;
        public MeshRenderer[] renderers;
        public MeshCache[] meshes;

        private Func<Transform, Matrix4x4> getMatrixFunc;
        private Func<Vector4, Vector3> postProcessPoint;

        public bool IsValid => renderers != null && meshes != null;

        public static MeshCacheSet CreateSnapshot(Transform root, Func<Transform, Matrix4x4> getMatrixFunc = null, Func<Vector4, Vector3> postProcessPoint = null) {
            MeshCacheSet cache = new();
            cache.Initialize(root, getMatrixFunc, postProcessPoint);
            return cache;
        }

        public MeshCacheSet CopyWith(Func<Transform, Matrix4x4> getMatrixFunc, Func<Vector4, Vector3> postProcessPoint) {
            MeshCacheSet clone = new();
            clone.root = root;
            clone.renderers = new MeshRenderer[renderers.Length];
            clone.meshes = new MeshCache[meshes.Length];
            clone.getMatrixFunc = (getMatrixFunc != null) ? getMatrixFunc : DefaultGetMatrixFunc;
            clone.postProcessPoint = postProcessPoint;
            for (int i = 0; i < renderers.Length; i++) {
                clone.renderers[i] = renderers[i];
                if (renderers[i] != null && renderers[i].TryGetComponent(out MeshFilter filter)) {
                    clone.meshes[i].transform = clone.getMatrixFunc(filter.transform);
                    clone.meshes[i].vertices = this.meshes[i].vertices; //IMPORTANT: This allows us to avoid re-retrieving large mesh vertex arrays!
                }
            }
            return clone;
        }

        private void Initialize(Transform root, Func<Transform, Matrix4x4> getMatrixFunc, Func<Vector4, Vector3> postProcessPoint) {
            renderers = root.GetComponentsInChildren<MeshRenderer>(true);
            this.root = root;
            meshes = new MeshCache[renderers.Length];
            this.getMatrixFunc = (getMatrixFunc != null) ? getMatrixFunc : DefaultGetMatrixFunc;
            this.postProcessPoint = postProcessPoint;

            for (int i = 0; i < renderers.Length; i++) {
                if (renderers[i].TryGetComponent(out MeshFilter filter)) {
                    meshes[i].transform = this.getMatrixFunc(filter.transform);
                    meshes[i].vertices = filter.sharedMesh.vertices;
                }
            }
        }

        private Matrix4x4 DefaultGetMatrixFunc(Transform transform) => transform != null ? transform.localToWorldMatrix : Matrix4x4.identity;
        public bool UpdateMatrices(Func<Transform, Matrix4x4> getMatrixFunc, Func<Vector4, Vector3> postProcessPoint) {
            this.getMatrixFunc = getMatrixFunc;
            this.postProcessPoint = postProcessPoint;
            return UpdateMatrices();
        }
        public bool UpdateMatrices() {
            bool anyMatricesChanged = false;
            for (int i = 0; i < renderers.Length; i++) {
                Matrix4x4 newMatrix = this.getMatrixFunc(renderers[i] != null ? renderers[i].transform : null);
                if (newMatrix != meshes[i].transform)
                    anyMatricesChanged = true;
                meshes[i].transform = newMatrix;
            }
            return anyMatricesChanged;
        }

        public async Task<Bounds> CalculateBounds() {
            if (renderers.Length > 0) {
                int first = 0;
                while (meshes[first].vertices == null && first < meshes.Length)
                    first++;
                if (first < meshes.Length) {
                    return await Task.Run(() => {
                        Vector3 GetPoint(in MeshCache mesh, Vector3 input) {
                            Vector4 output = mesh.transform * new Vector4(input.x, input.y, input.z, 1);
                            if (postProcessPoint != null)
                                output = postProcessPoint(output);
                            return output;
                        }
                        Bounds bounds = new(GetPoint(meshes[first], meshes[first].vertices[0]), new Vector3(0, 0, 0));
                        for (int v = 1; v < meshes[first].vertices.Length; v++)
                            bounds.Encapsulate(GetPoint(meshes[first], meshes[first].vertices[v]));

                        for (int m = first + 1; m < meshes.Length; m++) {
                            if (meshes[m].vertices == null)
                                continue;
                            for (int v = 0; v < meshes[m].vertices.Length; v++)
                                bounds.Encapsulate(GetPoint(meshes[m], meshes[m].vertices[v]));
                        }
                        return bounds;
                    });
                }
            }
            return new Bounds(root.position, new Vector3(0, 0, 0));
        }
    }
}
