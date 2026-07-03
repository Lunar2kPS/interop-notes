using UnityEngine;

namespace Carlos {
    public static class GizmosUtility {
        //NOTE: Expects the order to match GameObjectUtility.Get8Corners(...)
        public static void DrawCubeTransformed(Vector3[] corners) {
            // Bottom face (z = min)
            Gizmos.DrawLine(corners[0], corners[1]);
            Gizmos.DrawLine(corners[1], corners[3]);
            Gizmos.DrawLine(corners[3], corners[2]);
            Gizmos.DrawLine(corners[2], corners[0]);

            // Top face (z = max)
            Gizmos.DrawLine(corners[4], corners[5]);
            Gizmos.DrawLine(corners[5], corners[7]);
            Gizmos.DrawLine(corners[7], corners[6]);
            Gizmos.DrawLine(corners[6], corners[4]);

            // Vertical edges
            Gizmos.DrawLine(corners[0], corners[4]);
            Gizmos.DrawLine(corners[1], corners[5]);
            Gizmos.DrawLine(corners[2], corners[6]);
            Gizmos.DrawLine(corners[3], corners[7]);
        }
    }
}
