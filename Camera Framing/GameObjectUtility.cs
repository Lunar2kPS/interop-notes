using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using UnityEngine;

namespace Carlos {
    public static class GameObjectUtility {
        /// <summary>
        /// Compute world-space bounds of all renderers under <paramref name="root"/>.
        /// </summary>
        /// <remarks>
        /// This function gathers all matrices and vertices on the Unity main thread immediately, and then runs the calculation on all vertices and transforms to world-space on a background thread, and asynchronously returns the result.
        /// </remarks>
        public static Task<Bounds> CalculateBoundsByVertices(Transform root) => MeshCacheSet.CreateSnapshot(root).CalculateBounds();

        public static Bounds TransformBounds(Bounds bounds, Matrix4x4 transform) {
            using (IEnumerator<Vector3> enumerator = Get8Corners(bounds).GetEnumerator()) {
                enumerator.MoveNext();
                Bounds worldBounds = new(transform.MultiplyPoint3x4(enumerator.Current), new Vector3(0, 0, 0));
                while (enumerator.MoveNext())
                    worldBounds.Encapsulate(transform.MultiplyPoint3x4(enumerator.Current));
                return worldBounds;
            }
        }

        public static IEnumerable<Vector3> Get8Corners(Bounds bounds) {
            Vector3 min = bounds.min;
            Vector3 max = bounds.max;
            yield return new Vector3(min.x, min.y, min.z);
            yield return new Vector3(max.x, min.y, min.z);
            yield return new Vector3(min.x, max.y, min.z);
            yield return new Vector3(max.x, max.y, min.z);
            yield return new Vector3(min.x, min.y, max.z);
            yield return new Vector3(max.x, min.y, max.z);
            yield return new Vector3(min.x, max.y, max.z);
            yield return new Vector3(max.x, max.y, max.z);
        }
    }
}
