using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.Rendering;

namespace Carlos {
    public static class MeshUtility {
        /// <summary>
        /// Returns a list of connected vertex groups.
        /// Each inner list contains vertex indices that are connected by triangle edges.
        /// </summary>
        /// <remarks>Note that this task is runnable on background threads in parallel to the Unity main thread.</remarks>
        public static List<List<int>> CalculateConnectedVertexGroups(Vector3[] vertices, int[] triangles, float overlapThreshold = 0.0001f) {
            int vertexCount = vertices.Length;

            //Adjacency graph: for each vertex, this lets us know which other vertices are directly connected to it.
            List<HashSet<int>> adjacency = new(vertexCount);
            for (int i = 0; i < vertexCount; i++)
                adjacency.Add(new HashSet<int>());

            for (int i = 0; i < triangles.Length; i += 3) {
                int a = triangles[i];
                int b = triangles[i + 1];
                int c = triangles[i + 2];

                //NOTE: This adds undirected edges for each triangle.
                //  In graph terms, this means the connection works both ways (aka, a ←→ b).
                //  If it were *directed* edges, then the connection would only work ONE way (aka, a → b, but it would NOT automatically mean b → a).
                adjacency[a].Add(b);
                adjacency[a].Add(c);

                adjacency[b].Add(a);
                adjacency[b].Add(c);

                adjacency[c].Add(a);
                adjacency[c].Add(b);
            }

            if (overlapThreshold > 0)
                CombineOverlappingVerticesToAdjacencyGraph(vertices, adjacency, overlapThreshold);

            //NOTE: This is a BFS (Breadth-First Search) -- a standard graph traversal algorithm.
            //  BFS explores outward in "rings" from the start node using a queue.
            List<List<int>> vertexGroups = new();
            bool[] visited = new bool[vertexCount];
            Queue<int> queue = new();
            for (int start = 0; start < vertexCount; start++) {
                if (visited[start])
                    continue;

                //NOTE: We skip completely unused vertices
                if (adjacency[start].Count == 0) {
                    visited[start] = true;
                    continue;
                }

                List<int> group = new();
                queue.Clear();
                queue.Enqueue(start);
                visited[start] = true;

                while (queue.Count > 0) {
                    int current = queue.Dequeue();
                    group.Add(current);

                    foreach (int neighbor in adjacency[current]) {
                        if (visited[neighbor])
                            continue;
                        visited[neighbor] = true;
                        queue.Enqueue(neighbor);
                    }
                }

                vertexGroups.Add(group);
            }

            return vertexGroups;
        }

        private static void CombineOverlappingVerticesToAdjacencyGraph(Vector3[] vertices, List<HashSet<int>> adjacency, float overlapThreshold) {
            int vertexCount = vertices.Length;
            float sqrThreshold = overlapThreshold * overlapThreshold;

            // Spatial hash: quantize vertex positions into cells of size overlapThreshold
            Dictionary<Vector3Int, List<int>> cellToVertexIndices = new Dictionary<Vector3Int, List<int>>();

            Vector3Int GetCell(Vector3 v) {
                return new Vector3Int(
                    Mathf.FloorToInt(v.x / overlapThreshold),
                    Mathf.FloorToInt(v.y / overlapThreshold),
                    Mathf.FloorToInt(v.z / overlapThreshold)
                );
            }

            // Put every vertex into a spatial cell
            for (int i = 0; i < vertexCount; i++) {
                Vector3Int cell = GetCell(vertices[i]);

                if (!cellToVertexIndices.TryGetValue(cell, out List<int> list)) {
                    list = new List<int>();
                    cellToVertexIndices[cell] = list;
                }

                list.Add(i);
            }

            // For each vertex, compare only against vertices in its own cell and neighboring cells
            for (int i = 0; i < vertexCount; i++) {
                Vector3 v = vertices[i];
                Vector3Int baseCell = GetCell(v);

                for (int dx = -1; dx <= 1; dx++) {
                    for (int dy = -1; dy <= 1; dy++) {
                        for (int dz = -1; dz <= 1; dz++) {
                            Vector3Int neighborCell = new Vector3Int(
                                baseCell.x + dx,
                                baseCell.y + dy,
                                baseCell.z + dz
                            );

                            if (!cellToVertexIndices.TryGetValue(neighborCell, out List<int> candidates))
                                continue;

                            for (int c = 0; c < candidates.Count; c++) {
                                int j = candidates[c];

                                if (j <= i)
                                    continue;

                                if ((vertices[i] - vertices[j]).sqrMagnitude <= sqrThreshold) {
                                    adjacency[i].Add(j);
                                    adjacency[j].Add(i);
                                }
                            }
                        }
                    }
                }
            }
        }

        private struct MeshData {
            public Matrix4x4 transform;
            public Vector3[] vertices;
            public Vector3[] normals;
            public Vector2[] uvs;
            public int[][] trianglesBySubmesh;
        }
        public static async Task<Mesh> CombineAllMeshes(string combinedName, IReadOnlyCollection<MeshRenderer> renderers, bool recalculateNormalsIfMissing = true) {
            Mesh CreateEmptyMesh() {
                Mesh result = new();
                result.name = combinedName;
                return result;
            }
            if (renderers == null || renderers.Count == 0)
                return CreateEmptyMesh();

            List<MeshData> meshList = new();
            List<Vector3> combinedVertices = new();
            List<Vector3> combinedNormals = new();
            List<Vector2> combinedUV0s = new();
            List<int> combinedIndices = new();

            bool anyMeshMissingNormals = false;
            foreach (MeshRenderer renderer in renderers) {
                if (renderer != null && renderer.TryGetComponent(out MeshFilter filter)) {
                    Mesh sharedMesh = filter.sharedMesh;
                    if (sharedMesh != null) {
                        MeshData data = new MeshData() {
                            transform = renderer.transform.localToWorldMatrix,
                            vertices = sharedMesh.vertices,
                            normals = sharedMesh.normals,
                            uvs = sharedMesh.uv,
                            trianglesBySubmesh = new int[sharedMesh.subMeshCount][]
                        };
                        for (int i = 0; i < data.trianglesBySubmesh.Length; i++) {
                            if (sharedMesh.GetTopology(i) == MeshTopology.Triangles)
                                data.trianglesBySubmesh[i] = sharedMesh.GetTriangles(i);
                        }
                        meshList.Add(data);
                    }
                }
            }

            Task[] tasks = new Task[3];
            MeshData[] meshArray = meshList.ToArray();
            tasks[0] = Task.Run(() => {
                for (int i = 0; i < meshArray.Length; i++) {
                    // Merge all submeshes into one final index buffer
                    int vertexOffset = combinedVertices.Count;
                    for (int j = 0; j < meshArray[i].vertices.Length; j++)
                        combinedVertices.Add(meshArray[i].transform.MultiplyPoint3x4(meshArray[i].vertices[j]));

                    for (int submeshIndex = 0; submeshIndex < meshArray[i].trianglesBySubmesh.Length; submeshIndex++) {
                        if (meshArray[i].trianglesBySubmesh[submeshIndex] != null) {
                            for (int j = 0; j < meshArray[i].trianglesBySubmesh[submeshIndex].Length; j++) {
                                combinedIndices.Add(vertexOffset + meshArray[i].trianglesBySubmesh[submeshIndex][j]);
                            }
                        }
                    }
                }
            });
            tasks[1] = Task.Run(() => {
                for (int i = 0; i < meshArray.Length; i++) {
                    bool hasNormals = meshArray[i].normals != null && meshArray[i].normals.Length == meshArray[i].vertices.Length;
                    if (!hasNormals)
                        anyMeshMissingNormals = true;

                    for (int j = 0; j < meshArray[i].vertices.Length; j++) {
                        if (hasNormals)
                            combinedNormals.Add(meshArray[i].transform.MultiplyVector(meshArray[i].normals[j]).normalized);
                        else
                            combinedNormals.Add(Vector3.zero);
                    }
                }
            });
            tasks[2] = Task.Run(() => {
                for (int i = 0; i < meshArray.Length; i++) {
                    bool hasUV0 = meshArray[i].uvs != null && meshArray[i].uvs.Length == meshArray[i].vertices.Length;

                    for (int j = 0; j < meshArray[i].vertices.Length; j++) {
                        if (hasUV0)
                            combinedUV0s.Add(meshArray[i].uvs[j]);
                        else
                            combinedUV0s.Add(Vector2.zero);
                    }
                }
            });
            await Task.WhenAll(tasks);

            //IMPORTANT: We create the Mesh HERE, because for some reason, if we create it too early, it'll Debug.Log(...) as `null` after awaiting our tasks.. Maybe Unity was automatically cleaning it up/destroying it?
            //  Note that REAL C# null values Debug.Log(...) as `Null`! This supports this theory... (`null` means Unity destruction, overriden == null operator, etc.)
            Mesh result = CreateEmptyMesh();
            result.indexFormat = IndexFormat.UInt32;
            result.SetVertices(combinedVertices);
            result.SetTriangles(combinedIndices, 0, false);
            result.SetUVs(0, combinedUV0s);

            if (!anyMeshMissingNormals) {
                result.SetNormals(combinedNormals);
            } else if (recalculateNormalsIfMissing) {
                result.RecalculateNormals();
            } else {
                result.SetNormals(combinedNormals);
            }

            result.RecalculateBounds();
            result.RecalculateTangents();
            return result;
        }

        public static async void CombineAllSubmeshes(MeshRenderer renderer) {
            if (renderer == null)
                throw new ArgumentNullException(nameof(renderer));
            if (!renderer.TryGetComponent(out MeshFilter filter))
                throw new InvalidOperationException(renderer + " must have a " + nameof(MeshFilter) + " to operate on.");

            Mesh mesh = filter.sharedMesh;
            List<int> totalTris = new();
            List<int> buffer = new();
            for (int submeshIndex = 0; submeshIndex < mesh.subMeshCount; submeshIndex++) {
                buffer.Clear();
                mesh.GetTriangles(buffer, submeshIndex);
                totalTris.AddRange(buffer);
            }
            mesh.subMeshCount = 1;
            mesh.SetTriangles(totalTris, 0);

            renderer.sharedMaterials = new Material[1] { renderer.sharedMaterial };
        }

        public static void SplitMesh(Mesh target, List<List<int>> triangleGroups) {
            if (target.subMeshCount != 1)
                throw new ArgumentException("Cannot split mesh that already has more than 1 submesh!", nameof(target));
            target.subMeshCount = triangleGroups.Count;
            for (int groupIndex = 0; groupIndex < triangleGroups.Count; groupIndex++)
                target.SetTriangles(triangleGroups[groupIndex], groupIndex, false);
            target.RecalculateBounds();
        }

        public static async Task<List<List<int>>> ConvertVertexGroupsToTriangleGroups(int vertexCount, int[] triangles, List<List<int>> vertexGroups) {
            int[] vertexToGroup = new int[vertexCount];
            List<List<int>> triangleGroups = new List<List<int>>(vertexGroups.Count);
            for (int i = 0; i < triangleGroups.Count; i++)
                triangleGroups[i] = new List<int>();

            // 2) Build vertex -> group lookup
            for (int i = 0; i < vertexToGroup.Length; i++)
                vertexToGroup[i] = -1;

            int groupIndex = 0;
            foreach (List<int> group in vertexGroups) {
                foreach (int vertexIndex in group) {
                    if (vertexIndex < 0 || vertexIndex >= vertexToGroup.Length)
                        Debug.LogWarning("Trying to access vertexIndex " + vertexIndex + " failed! We have " + vertexToGroup.Length + " vertices.");
                    else
                        vertexToGroup[vertexIndex] = groupIndex;
                }
                groupIndex++;
            }

            // 3) Build triangle lists per group
            for (int triIndex = 0; triIndex < triangles.Length; triIndex += 3) {
                int a = triangles[triIndex];
                int b = triangles[triIndex + 1];
                int c = triangles[triIndex + 2];

                int groupA = vertexToGroup[a];
                int groupB = vertexToGroup[b];
                int groupC = vertexToGroup[c];

                // In a properly connected-component-partitioned mesh,
                // all three vertices of a triangle should belong to the same group.
                if (groupA != groupB || groupA != groupC) {
                    Debug.LogWarning($"Triangle ({a}, {b}, {c}) spans multiple groups unexpectedly. Skipping.");
                    continue;
                }

                if (groupA >= 0) {
                    if (groupA >= triangleGroups.Count)
                        Debug.LogWarning("Trying to access triangle group " + groupA + " out of " + triangleGroups.Count + " actually-available groups!");
                    else {
                        triangleGroups[groupA].Add(a);
                        triangleGroups[groupA].Add(b);
                        triangleGroups[groupA].Add(c);
                    }
                }
            }
            return triangleGroups;
        }

        public static async Task<List<List<int>>> ConvertSpherecastHitsToTriangleGroups(GPUSpherecastResults results) {
            return await Task.Run(() => {
                List<List<int>> triangleGroups = new() {
                    new List<int>(results.meshData.vertices.Length),
                    new List<int>(results.meshData.vertices.Length)
                };
                HashSet<int> hitTriangles = new(results.meshData.tris.Length);
                for (int i = 0; i < results.hits.Length; i++)
                    if (!hitTriangles.Add(results.hits[i].triangleIndex))
                        Debug.LogWarning("Duplicate hit triangle index " + results.hits[i].triangleIndex + "!");
                for (int triIndex = 0; triIndex < results.meshData.tris.Length; triIndex += 3) {
                    int a = results.meshData.tris[triIndex];
                    int b = results.meshData.tris[triIndex + 1];
                    int c = results.meshData.tris[triIndex + 2];

                    int submeshIndex = hitTriangles.Contains(triIndex) ? 1 : 0;
                    triangleGroups[submeshIndex].Add(a);
                    triangleGroups[submeshIndex].Add(b);
                    triangleGroups[submeshIndex].Add(c);
                }
                return triangleGroups;
            });
        }
    }
}
