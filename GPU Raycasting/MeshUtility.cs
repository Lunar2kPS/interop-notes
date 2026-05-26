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
            Mesh result = new();
            result.name = combinedName;
            if (renderers == null || renderers.Count == 0)
                return result;

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

            await Task.Run(() => {
                MeshData[] meshArray = meshList.ToArray();
                for (int i = 0; i < meshArray.Length; i++) {
                    int vertexOffset = combinedVertices.Count;
                    bool hasNormals = meshArray[i].normals != null && meshArray[i].normals.Length == meshArray[i].vertices.Length;
                    bool hasUV0 = meshArray[i].uvs != null && meshArray[i].uvs.Length == meshArray[i].vertices.Length;

                    if (!hasNormals)
                        anyMeshMissingNormals = true;

                    for (int j = 0; j < meshArray[i].vertices.Length; j++) {
                        combinedVertices.Add(meshArray[i].transform.MultiplyPoint3x4(meshArray[i].vertices[j]));

                        if (hasNormals)
                            combinedNormals.Add(meshArray[i].transform.MultiplyVector(meshArray[i].normals[j]).normalized);
                        else
                            combinedNormals.Add(Vector3.zero);

                        if (hasUV0)
                            combinedUV0s.Add(meshArray[i].uvs[j]);
                        else
                            combinedUV0s.Add(Vector2.zero);
                    }

                    // Merge all submeshes into one final index buffer
                    for (int submeshIndex = 0; submeshIndex < meshArray[i].trianglesBySubmesh.Length; submeshIndex++) {
                        if (meshArray[i].trianglesBySubmesh[submeshIndex] != null) {
                            for (int j = 0; j < meshArray[i].trianglesBySubmesh[submeshIndex].Length; j++) {
                                combinedIndices.Add(vertexOffset + meshArray[i].trianglesBySubmesh[submeshIndex][j]);
                            }
                        }
                    }
                }
            });

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
    }
}
