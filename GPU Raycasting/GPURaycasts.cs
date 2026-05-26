using System;
using UnityEngine;

namespace Carlos {
    [Serializable]
    public struct GPURaycastHit {
        public Transform transform;
        public float distance;
        public Vector3 point;
        public Vector3 normal;
        public Vector2 uv;
        public int triangleIndex;
        public Vector3 barycentricCoordinates;
    }

    public static class GPURaycasts {
        [Serializable]
        private struct Triangle {
            public int triangleIndex;

            public Vector3 a;
            public Vector3 b;
            public Vector3 c;
            public Vector3 normalA;
            public Vector3 normalB;
            public Vector3 normalC;
            public Vector2 uvA;
            public Vector2 uvB;
            public Vector2 uvC;
        }

        [Serializable]
        private struct HitInfo {
            public int hitRegistered;
            public float distance;
            public Vector3 hitPoint;
            public int triangleIndex;
            public Vector3 barycentricCoordinates;
            public Vector3 normal;
            public Vector2 uv;
        }

        private const int MaxHitResults = 64;
        private static readonly int LocalToWorldMatrixID;
        private static readonly int MaxLocalDistanceID;
        private static readonly int LocalRayOriginID;
        private static readonly int LocalRayDirectionID;
        private static readonly int MeshTrianglesCountID;
        private static readonly int MeshTrianglesID;
        private static readonly int HitInfoID;

        private static ComputeShader computeShader;
        private static int kernel = -1;
        private static Mesh currentMesh;
        private static ComputeBuffer triangleBuffer;

        static GPURaycasts() {
            LocalToWorldMatrixID = Shader.PropertyToID("localToWorldMatrix");
            MaxLocalDistanceID = Shader.PropertyToID("maxLocalDistance");
            LocalRayOriginID = Shader.PropertyToID("localRayOrigin");
            LocalRayDirectionID = Shader.PropertyToID("localRayDirection");
            MeshTrianglesCountID = Shader.PropertyToID("meshTrianglesCount");
            MeshTrianglesID = Shader.PropertyToID("meshTriangles");
            HitInfoID = Shader.PropertyToID("hitInfo");
            ReloadComputeShader();
        }

        public static void ReloadComputeShader() {
            computeShader = Resources.Load<ComputeShader>("Compute Shaders/GPU Raycast");
            if (computeShader != null)
                kernel = computeShader.FindKernel("rayIntersection");
        }

        private static int GetAppendBufferCount(ComputeBuffer appendBuffer) {
            ComputeBuffer countBuffer = new(1, sizeof(int), ComputeBufferType.IndirectArguments);
            try {
                countBuffer.SetData(new int[] { 1 });
                ComputeBuffer.CopyCount(appendBuffer, countBuffer, 0);
                int[] countArray = new int[1];
                countBuffer.GetData(countArray);
                return countArray[0];
            } finally {
                countBuffer.Release();
            }
        }

        public static bool Raycast(Ray worldRay, MeshFilter meshFilter, float maxDistance, out GPURaycastHit hit) => RayIntersectionGPU(worldRay, meshFilter.transform, meshFilter.sharedMesh, maxDistance, out hit);
        public static bool RayIntersectionGPU(Ray worldRay, Transform transform, Mesh mesh, out GPURaycastHit hit) => RayIntersectionGPU(worldRay, transform, mesh, float.MaxValue, out hit);
        public static bool RayIntersectionGPU(Ray worldRay, Transform transform, Mesh mesh, float maxDistance, out GPURaycastHit hit) {
            hit = new GPURaycastHit();
            if (computeShader == null)
                ReloadComputeShader();
            if (computeShader == null)
                return false;

            Ray localRay = new(transform.InverseTransformPoint(worldRay.origin), transform.InverseTransformDirection(worldRay.direction));
            float maxLocalDistance = Vector3.Magnitude(transform.InverseTransformVector(maxDistance * worldRay.direction));

            Vector3[] vertices = mesh.vertices;
            int[] tris = mesh.triangles;
            Vector3[] normals = mesh.normals;
            Vector2[] uvs = mesh.uv;

            int numberOfTris = tris.Length / 3;
            if (numberOfTris < 1)
                return false;

            computeShader.SetMatrix(LocalToWorldMatrixID, transform.localToWorldMatrix);
            computeShader.SetFloat(MaxLocalDistanceID, maxLocalDistance);
            computeShader.SetVector(LocalRayOriginID, localRay.origin);
            computeShader.SetVector(LocalRayDirectionID, localRay.direction);

            bool triangleUpdateRequired = triangleBuffer == null || currentMesh != mesh || numberOfTris != triangleBuffer.count;
            if (triangleUpdateRequired) {
                if (triangleBuffer != null)
                    triangleBuffer.Release();

                Triangle[] meshTriangles = new Triangle[numberOfTris];
                int triIndex = 0;
                for (int i = 0; i < meshTriangles.Length; i++) {
                    Triangle triangle = new() {
                        triangleIndex = triIndex,
                        a = vertices[tris[triIndex]],
                        b = vertices[tris[triIndex + 1]],
                        c = vertices[tris[triIndex + 2]],
                        normalA = normals[tris[triIndex]],
                        normalB = normals[tris[triIndex + 1]],
                        normalC = normals[tris[triIndex + 2]]
                    };

                    if (uvs.Length > 0) {
                        triangle.uvA = uvs[tris[triIndex]];
                        triangle.uvB = uvs[tris[triIndex + 1]];
                        triangle.uvC = uvs[tris[triIndex + 2]];
                    }

                    meshTriangles[i] = triangle;
                    triIndex += 3;
                }
                computeShader.SetInt(MeshTrianglesCountID, meshTriangles.Length);
                triangleBuffer = new ComputeBuffer(numberOfTris, 100);
                triangleBuffer.SetData(meshTriangles);
                computeShader.SetBuffer(kernel, MeshTrianglesID, triangleBuffer);
            }
            currentMesh = mesh;

            ComputeBuffer hitInfoAppendBuffer = new(MaxHitResults, 56, ComputeBufferType.Append);
            hitInfoAppendBuffer.SetCounterValue(0);

            HitInfo[] hitResults = new HitInfo[MaxHitResults];
            hitInfoAppendBuffer.SetData(hitResults);
            computeShader.SetBuffer(kernel, HitInfoID, hitInfoAppendBuffer);

            int threadsPerGroup = 512;
            int threadGroups = Mathf.CeilToInt((float) numberOfTris / threadsPerGroup);
            computeShader.Dispatch(kernel, threadGroups, 1, 1);

            int hitCount = GetAppendBufferCount(hitInfoAppendBuffer);
            if (hitCount > 0) {
                hitInfoAppendBuffer.GetData(hitResults);
                int indexOfClosestHit = 0;

                for (int i = 1; i < hitCount; i++) {
                    if (hitResults[i].distance < hitResults[indexOfClosestHit].distance)
                        indexOfClosestHit = i;
                }

                HitInfo closestHit = hitResults[indexOfClosestHit];
                hit = new GPURaycastHit() {
                    transform = transform,
                    distance = closestHit.distance,
                    point = closestHit.hitPoint,
                    normal = closestHit.normal,
                    uv = closestHit.uv,
                    triangleIndex = closestHit.triangleIndex,
                    barycentricCoordinates = closestHit.barycentricCoordinates
                };
            }
            hitInfoAppendBuffer.Release();
            return hitCount > 0;
        }
    }
}
