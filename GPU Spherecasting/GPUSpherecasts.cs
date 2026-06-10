using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Unity.Collections;
using UnityEngine;
using UnityEngine.Rendering;

namespace Carlos {
    [Serializable]
    public struct GPUSpherecastResults {
        public bool success;
        public CachedSpherecastMeshData meshData;
        public GPUSpherecastHit[] hits;
        public List<List<int>> triangleGroups;
    }

    [Serializable]
    public struct GPUSpherecastHit {
        public Transform transform;
        public float distance;
        public Vector3 point;
        public Vector3 normal;
        public Vector2 uv;
        public int triangleIndex;
        public Vector3 barycentricCoordinates;
    }

    [Serializable]
    public struct CachedSpherecastMeshData {
        public Vector3[] vertices;
        public int[] tris;
        public Vector3[] normals;
        public Vector2[] uvs;
    }

    public static class GPUSpherecasts {
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

        private const int MaxHitResults = 16777216;
        private static readonly int LocalToWorldMatrixID;
        private static readonly int MaxLocalDistanceID;
        private static readonly int LocalRadiusID;
        private static readonly int LocalRayOriginID;
        private static readonly int LocalRayDirectionID;
        private static readonly int MeshTrianglesCountID;
        private static readonly int MeshTrianglesID;
        private static readonly int HitInfoID;

        private static ComputeShader computeShader;
        private static int kernel = -1;
        private static Mesh currentMesh;
        private static ComputeBuffer triangleBuffer;

        static GPUSpherecasts() {
            LocalToWorldMatrixID = Shader.PropertyToID("localToWorldMatrix");
            MaxLocalDistanceID = Shader.PropertyToID("maxLocalDistance");
            LocalRadiusID = Shader.PropertyToID("localRadius");
            LocalRayOriginID = Shader.PropertyToID("localRayOrigin");
            LocalRayDirectionID = Shader.PropertyToID("localRayDirection");
            MeshTrianglesCountID = Shader.PropertyToID("meshTrianglesCount");
            MeshTrianglesID = Shader.PropertyToID("meshTriangles");
            HitInfoID = Shader.PropertyToID("hitInfo");
            ReloadComputeShader();
        }

        public static void ReloadComputeShader() {
            string resourcesPath = "Compute Shaders/GPU Spherecast";
            computeShader = Resources.Load<ComputeShader>(resourcesPath);
            if (computeShader != null)
                kernel = computeShader.FindKernel("sphereIntersection");
            else
                Debug.LogWarning("Unable to find compute shader at: " + resourcesPath);
        }

        private static async Task<int> GetAppendBufferCount(ComputeBuffer appendBuffer) {
            ComputeBuffer countBuffer = new(1, sizeof(int), ComputeBufferType.IndirectArguments);
            try {
                ComputeBuffer.CopyCount(appendBuffer, countBuffer, 0);
                AsyncGPUReadbackRequest request = await AsyncGPUReadback.RequestAsync(countBuffer);
                if (request.hasError)
                    return 0;
                return request.GetData<int>()[0];
            } finally {
                countBuffer.Release();
            }
        }

        public static async Task<List<List<int>>> ConvertTrianglesToVertexGroups(int vertexCount, int[] tris, GPUSpherecastHit[] hits) {
            List<List<int>> vertexGroups = new() {
                new List<int>(vertexCount), //List of vertices that were NOT hit.
                new List<int>(vertexCount)  //List of vertices that WERE hit.
            };

            int taskCount = Environment.ProcessorCount;
            Task[] tasks = new Task[taskCount];
            int approxVerticesPerTask = vertexCount / taskCount;
            for (int t = 0; t < taskCount; t++) {
                int taskID = t;
                int minVertexIndex = taskID * approxVerticesPerTask;                                                        //Inclusive
                int maxVertexIndex = (taskID == taskCount - 1) ? vertexCount : minVertexIndex + approxVerticesPerTask;      //Exclusive

                tasks[taskID] = Task.Run(() => {
                    int wasHit;
                    for (int vertexIndex = minVertexIndex; vertexIndex < maxVertexIndex; vertexIndex++) {
                        wasHit = 0;
                        for (int j = 0; j < hits.Length; j++) {
                            int triIndex = hits[j].triangleIndex;
                            if (tris[triIndex] == vertexIndex ||
                                tris[triIndex + 1] == vertexIndex ||
                                tris[triIndex + 2] == vertexIndex) {
                                wasHit = 1;
                                break;
                            }
                        }
                        if (vertexIndex % 100000 == 0)
                            if (vertexIndex >= vertexCount)
                                Debug.LogWarning("vertexIndex is " + vertexIndex + "/" + vertexCount + "???");
                        lock (vertexGroups)
                            vertexGroups[wasHit].Add(vertexIndex);
                    }
                });
            }
            await Task.WhenAll(tasks);
            return vertexGroups;
        }

        public static Task<GPUSpherecastResults> Spherecast(MeshFilter meshFilter, Ray ray, float radius, float maxDistance) {
            if (meshFilter == null) {
                GPUSpherecastResults results = new() {
                    hits = new GPUSpherecastHit[0],
                    meshData = new()
                };
                return Task.FromResult(results);
            }
            return Spherecast(meshFilter.transform, meshFilter.sharedMesh, ray, radius, maxDistance);
        }

        public static async Task<GPUSpherecastResults> Spherecast(Transform transform, Mesh mesh, Ray ray, float radius, float maxDistance) {
            GPUSpherecastResults results = new() {
                hits = new GPUSpherecastHit[0],
                meshData = new()
            };
            if (computeShader == null)
                ReloadComputeShader();
            if (computeShader == null)
                return results;

            Ray localRay = new(transform.InverseTransformPoint(ray.origin), transform.InverseTransformDirection(ray.direction));
            float maxLocalDistance = Vector3.Magnitude(transform.InverseTransformVector(maxDistance * ray.direction));
            Vector3 lossyScale = transform.lossyScale;
            float averageScale = (lossyScale.x + lossyScale.y + lossyScale.z) / 3;
            float localRadius = radius * averageScale;

            Vector3[] vertices = mesh.vertices;
            int[] tris = mesh.triangles;
            Vector3[] normals = mesh.normals;
            Vector2[] uvs = mesh.uv;
            results.meshData.vertices = vertices;
            results.meshData.tris = tris;
            results.meshData.normals = normals;
            results.meshData.uvs = uvs;

            int numberOfTris = tris.Length / 3;
            if (numberOfTris < 1)
                return results;

            computeShader.SetMatrix(LocalToWorldMatrixID, transform.localToWorldMatrix);
            computeShader.SetFloat(MaxLocalDistanceID, maxLocalDistance);
            computeShader.SetFloat(LocalRadiusID, localRadius);
            computeShader.SetVector(LocalRayOriginID, localRay.origin);
            computeShader.SetVector(LocalRayDirectionID, localRay.direction);

            bool triangleUpdateRequired = triangleBuffer == null || currentMesh != mesh || numberOfTris != triangleBuffer.count;
            if (triangleUpdateRequired) {
                Triangle[] meshTriangles = new Triangle[numberOfTris];
                await Task.Run(() => {
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
                });
                if (triangleBuffer != null)
                    triangleBuffer.Release();
                triangleBuffer = new ComputeBuffer(numberOfTris, 100);
                triangleBuffer.SetData(meshTriangles);
                computeShader.SetInt(MeshTrianglesCountID, meshTriangles.Length);
                computeShader.SetBuffer(kernel, MeshTrianglesID, triangleBuffer);
            }
            currentMesh = mesh;

            ComputeBuffer hitInfoAppendBuffer = new(MaxHitResults, 56, ComputeBufferType.Append);
            hitInfoAppendBuffer.SetCounterValue(0);
            computeShader.SetBuffer(kernel, HitInfoID, hitInfoAppendBuffer);

            int threadsPerGroup = 512;
            int threadGroups = Mathf.CeilToInt((float) numberOfTris / threadsPerGroup);
            computeShader.Dispatch(kernel, threadGroups, 1, 1);
            int hitCount = await GetAppendBufferCount(hitInfoAppendBuffer);

            if (hitCount > MaxHitResults) {
                Debug.LogWarning(hitCount + " results exceed the maximum " + MaxHitResults + ". Some results may be missing.");
                hitCount = MaxHitResults;
            }
            AsyncGPUReadbackRequest request = await AsyncGPUReadback.RequestAsync(hitInfoAppendBuffer);
            if (!request.hasError && hitCount > 0) {
                NativeArray<HitInfo> rawHits = request.GetData<HitInfo>();
                results.hits = new GPUSpherecastHit[hitCount];
                for (int i = 0; i < hitCount; i++) {
                    results.hits[i] = new GPUSpherecastHit() {
                        transform = transform,
                        distance = rawHits[i].distance,
                        point = rawHits[i].hitPoint,
                        normal = rawHits[i].normal,
                        uv = rawHits[i].uv,
                        triangleIndex = rawHits[i].triangleIndex,
                        barycentricCoordinates = rawHits[i].barycentricCoordinates
                    };
                }
            }
            hitInfoAppendBuffer.Release();
            results.success = hitCount > 0;
            return results;
        }
    }
}
