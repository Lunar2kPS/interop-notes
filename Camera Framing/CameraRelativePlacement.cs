using UnityEngine;

namespace Carlos {
    [ExecuteAlways]
    public class CameraRelativePlacement : MonoBehaviour {
        [SerializeField] private
#if UNITY_EDITOR
            new
#endif
            Camera camera;

        [Min(0)]
        [SerializeField] private float distance = 3;
        [SerializeField] private Vector2 frustumPlaneXY = new(0.5f, 0.5f);
        [SerializeField] private Vector3 forward = new(0, 0, 1);

        public Camera Camera {
            get { return camera; }
            set { camera = value; }
        }

        private void Update() {
            UpdatePlacement(Quaternion.LookRotation(forward, Vector3.up));
        }

        public void UpdatePlacement(Quaternion? worldRot = null) {
            if (camera != null) {
                //General Form: tanθ = y / x
                //  Camera Frustum Height: tan(θ_y / 2) = 1/2h / zDistance, where θ_y is the vertical FOV of the camera, equivalent to camera.fieldOfView.
                //      h = 2 * zDistance * tan(θ_y / 2)
                float height = 2 * distance * Mathf.Tan(camera.fieldOfView / 2 * Mathf.Deg2Rad);
                float width = height * camera.aspect;
                Vector3 right = camera.transform.right;
                Vector3 up = camera.transform.up;
                Vector3 forward = camera.transform.forward;
                Vector3 cameraPos = camera.transform.position;
                Vector3 center = cameraPos + distance * forward;
                Vector3 min = center - right * width / 2 - up * height / 2;
                Vector2 max = center + right * width / 2 + up * height / 2;
                Vector3 position = min + frustumPlaneXY.x * right * width + frustumPlaneXY.y * up * height; ;
                transform.position = position;

                Quaternion rot = (worldRot ?? Quaternion.identity);
                Vector3 arrowForward = rot * Vector3.forward;

                Vector3 cameraToArrowDir = Vector3.Normalize(transform.position - cameraPos);
                //float dot = Vector3.Dot(Vector3.up, -cameraToArrowDir);
                //float alignmentOfCameraAndArrow = Vector3.Dot(cameraToArrowDir, arrowForward);
                //float angleTowardsCamera = Mathf.Acos(dot) * Mathf.Rad2Deg;
                //transform.rotation = Quaternion.AngleAxis(-angleTowardsCamera, arrowForward);
                //transform.rotation = Quaternion.AngleAxis(-angleTowardsCamera, arrowForward) * Quaternion.Euler(60, 0, 0);
                //transform.rotation = Quaternion.LookRotation(center - position)

                //Best?
                Vector3 dir = arrowForward - Mathf.Clamp(Vector3.Dot(arrowForward, forward), -0.99f, 0.99f) * forward; //Projection (subtract away the camera's forward dir so the dir becomes parallel to the frustum plane)
                dir = (dir + Vector3.Lerp(-forward, forward, (Vector3.Dot(arrowForward, forward) + 1) / 2)) / 2; //Interpolate towards camera forward or backwards
                //dir = (dir + Vector3.Cross(-cameraToArrowDir, arrowForward)) / 2;
                transform.rotation = Quaternion.LookRotation(dir, -cameraToArrowDir) * Quaternion.Euler(-30 * Vector3.Dot(arrowForward, forward), 0, 0);

                //transform.rotation = Quaternion.LookRotation(preferredForward, Vector3.up);
            }
        }
    }
}
