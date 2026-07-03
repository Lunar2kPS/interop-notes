using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using UnityEngine;

#if UNITY_EDITOR
    using UnityEditor;
#endif

using Object = UnityEngine.Object;

namespace Carlos {
    [Serializable]
    public class CameraSystem : ICameraSystem {
        [Serializable]
        private enum CameraAngleType {
            Interior = 0,
            Exterior = 1,
            ExteriorQuadrant = 2
        }

        //NOTE: For now as-written, only local-space, OR world-space rotation is supported, not both simultaneously.
        [Serializable]
        private struct CameraAngleData {
            public string name;
            public CameraAngleType type;
            public float distanceMultiplier;

            public Vector3 interiorWorldRotationOffset;
            public Vector3 exteriorViewRotation;
            public Vector3[] quadrantViewRotations;

            public bool HasWorldRotationOffset => interiorWorldRotationOffset.sqrMagnitude >= 0.0001f;
        }

        [SerializeField] private Vector3 normalizedAABBCenter = new(0.5f, 0.75f, 0.5f);
        [SerializeField] private CameraAngleData[] angles = { };
        [SerializeField] private Vector3 vehicleForward = new(1, 0, 0);

        [SerializeField] private Camera cameraPrefab;
        [SerializeField] private bool recenterX = true;
        [SerializeField] private bool recenterY = true;

        [Header("Debug")]
        [SerializeField] private bool useDebugSequence;
        [SerializeField] private int debugAngleCount = 145;

        [Tooltip("For debugging purposes, if you wish to prevent parallelization for the calculation of camera angles, set this to true.\n" +
            "This will allow you to deterministically view the gizmos for the last camera angle, and help in debugging.")]
        [SerializeField] private bool serialCalculation = false;

        [Tooltip("For debugging purposes, this prevents us from setting hide flags and persistenting the camera.\n" +
            "This allows Unity to render out SceneView previews of the camera.")]
        [SerializeField] private bool bypassPersistence = false;

        private Vector3[] gizmoCorners;
        private Matrix4x4 lastCameraToWorld;
        private Bounds lastLocalBounds;

        private Camera renderCamera;
        public Camera RenderCamera {
            get {
                if (renderCamera == null)
                    CreateRenderCamera();
                return renderCamera;
            }
        }

        public void OnSystemAwake() {
            CreateRenderCamera();
        }

        public void OnSystemDestroy() {
            if (renderCamera != null) {
                IUnityUnifier unifier = ServiceLocator.Default.GetSystem<IUnityUnifier>();
                if (unifier != null)
                    unifier.DestroyGameObject(renderCamera.gameObject);
            }
        }

        private void CreateRenderCamera() {
            if (cameraPrefab != null) {
                renderCamera = Component.Instantiate(cameraPrefab);
                if (!bypassPersistence) {
                    IUnityUnifier unifier = ServiceLocator.Default.GetSystem<IUnityUnifier>();
                    unifier.PersistGameObject(renderCamera.gameObject, false);
                }
            }
            renderCamera.gameObject.name = "[TEMP] " + cameraPrefab.name;
            renderCamera.enabled = false;
            renderCamera.cullingMask = ~0;
        }

        public Task<byte[]> RenderToJPG(Camera camera, int quality = 90) {
            int width = 1920;
            int height = 1080;
            RenderTexture rt = new(width, height, 24, RenderTextureFormat.ARGB32);
            // Ensure camera clears to a visible background so transparent shell blends correctly
            camera.targetTexture = rt;
            camera.Render(); // First render: flush any deferred material/GPU updates

            TaskCompletionSource<byte[]> tcs = new();
            byte[] bytes = null;
#if UNITY_EDITOR
            if (!Application.isPlaying) {
                EditorApplication.QueuePlayerLoopUpdate();
                EditorApplication.Step();
            }
            EditorApplication.delayCall += () => {
#endif
                camera.Render(); // Second render: capture
                RenderTexture.active = rt;
                Texture2D tex = new(width, height, TextureFormat.RGBA32, false);
                tex.ReadPixels(new Rect(0, 0, width, height), 0, 0);
                tex.Apply();
                bytes = tex.EncodeToJPG(quality);
                RenderTexture.active = null;
                camera.targetTexture = null;
                Object.DestroyImmediate(rt);
                Object.DestroyImmediate(tex);

#if UNITY_EDITOR
                try {
                    tcs.TrySetResult(bytes);
                } catch (Exception e) {
                    tcs.TrySetException(e);
                    throw;
                }
            };
            return tcs.Task;
#else
            return Task.FromResult(bytes);
#endif
        }

        private Vector3 GetCenter(Bounds bounds, Vector3 normalizedCenter) {
            Vector3 min = bounds.min;
            Vector3 max = bounds.max;
            Vector3 result = new();
            for (int i = 0; i < 3; i++)
                result[i] = Mathf.Lerp(min[i], max[i], normalizedCenter[i]);
            return result;
        }

        private void DebugGizmos() {
            gizmoCorners = GameObjectUtility.Get8Corners(lastLocalBounds).Select(c => lastCameraToWorld.MultiplyPoint(c)).ToArray();
            GizmosUtility.DrawCubeTransformed(gizmoCorners);
        }

        public async IAsyncEnumerable<CameraAngle> PrepareCameraAngles(Camera camera, ModelLoadResult focusPart, ModelLoadResult vehicleShell) {
            Bounds worldFocusPartBounds = await focusPart.GetBoundsAsync();
            Bounds worldShellBounds = (vehicleShell.IsValid && vehicleShell.HasGameObject) ? await vehicleShell.GetBoundsAsync() : worldFocusPartBounds;
            Vector3 weightedVehicleCenter = GetCenter(worldShellBounds, normalizedAABBCenter);
            Vector3? orbitalOffset = null;

            CameraAngleData[] angles;
            if (useDebugSequence) {
                angles = new CameraAngleData[debugAngleCount];
                for (int i = 0; i < angles.Length; i++) {
                    angles[i].name = i.ToString();
                    angles[i].type = CameraAngleType.Exterior;
                    angles[i].distanceMultiplier = 1;
                    angles[i].exteriorViewRotation = new Vector3(0, (float) i / (angles.Length - 1) * 360, 30);
                }
            } else {
                angles = this.angles;
            }

            async Task<CameraAngle> CalculateAngleAsync(int index) {
                CameraAngleData angle = angles[index];
                switch (angle.type) {
                    case CameraAngleType.Interior: {
                            camera.transform.position = weightedVehicleCenter;
                            Vector3 lookDirection = worldFocusPartBounds.center - weightedVehicleCenter;
                            if (lookDirection.sqrMagnitude <= 0.0001f) {
                                Debug.LogWarning("Defaulting look direction!" + (vehicleShell.IsValid && vehicleShell.HasGameObject ? " Maybe there was no primary focus part?" : "Maybe it's because of the lack of vehicle shell?"));
                                lookDirection.Set(-0.707107f, 0, -0.707107f);
                            }
                            Quaternion rotation = Quaternion.LookRotation(lookDirection, new Vector3(0, 1, 0));
                            Vector3 eulerAngles = rotation.eulerAngles;
                            eulerAngles.z = 0;
                            rotation = Quaternion.Euler(eulerAngles);

                            if (orbitalOffset == null) {
                                Vector3 worldPos = await CalculateFramingParams(camera, worldFocusPartBounds.center, rotation, focusPart);
                                orbitalOffset = worldPos - worldFocusPartBounds.center;
                            }
                            Quaternion worldRot = Quaternion.Euler(angle.interiorWorldRotationOffset);
                            return new CameraAngle() {
                                name = angle.name,
                                position = worldFocusPartBounds.center + angle.distanceMultiplier * (worldRot * orbitalOffset.Value),
                                rotation = worldRot * rotation //NOTE: Here, we left-multiply rotation because this is a world-space rotation transformation.
                            };
                            //Quaternion localRot = Quaternion.Euler(angle.localRotationOffset);
                            //Quaternion adjustedRotation = rotation * localRot; //NOTE: Here, we RIGHT-multiply rotation because this is in the local-space of rotation, for example, to make the camera look down from where it already is looking.
                        }
                    case CameraAngleType.Exterior: {
                            Quaternion worldRot = Quaternion.LookRotation(Quaternion.Euler(angle.exteriorViewRotation) * -vehicleForward, Vector3.up);
                            Vector3 worldPos = await CalculateFramingParams(camera, worldShellBounds.center, worldRot, vehicleShell);
                            return new CameraAngle() {
                                name = angle.name,
                                position = worldShellBounds.center + angle.distanceMultiplier * (worldPos - worldShellBounds.center),
                                rotation = worldRot
                            };
                        }
                    case CameraAngleType.ExteriorQuadrant: {
                            //NOTE: We would use sign.xz, but because vehicle forwards are +x in world-space (1, 0, 0), that means our right axis is -z, and forward is +x, so -ZX.
                            //  (-1, -1)    B5
                            //  ( 1, -1)    B6
                            //  (-1,  1)    B1
                            //  ( 1,  1)    B2
                            Vector3 sign = worldFocusPartBounds.center - weightedVehicleCenter;
                            for (int i = 0; i < 3; i++)
                                sign[i] = Mathf.Sign(sign[i]);
                            int quadrantIndex = 0;

                            //Vehicle right axis: -z
                            if (sign.z < 0)
                                quadrantIndex++;
                            //Vehicle forward axis: +x
                            if (sign.x > 0)
                                quadrantIndex += 2;

                            Quaternion worldRot = Quaternion.LookRotation(Quaternion.Euler(angle.quadrantViewRotations[quadrantIndex]) * -vehicleForward, Vector3.up);
                            Vector3 worldPos = await CalculateFramingParams(camera, worldShellBounds.center, worldRot, vehicleShell);
                            return new CameraAngle() {
                                name = angle.name,
                                position = worldShellBounds.center + angle.distanceMultiplier * (worldPos - worldShellBounds.center),
                                rotation = worldRot
                            };
                        }
                    default:
                        throw new NotSupportedException();
                }
            }

            if (serialCalculation) {
                for (int i = 0; i < angles.Length; i++)
                    yield return await CalculateAngleAsync(i);
            } else {
                Task<CameraAngle>[] tasks = new Task<CameraAngle>[angles.Length];
                for (int i = 0; i < angles.Length; i++) {
                    int index = i;
                    tasks[i] = CalculateAngleAsync(index);
                }
                for (int i = 0; i < tasks.Length; i++) {
                    await tasks[i];
                    yield return tasks[i].Result;
                }
            }
        }

        /// <summary>
        /// <para>
        /// Calculates the required distance along the camera's local -Z axis
        /// so that the entire <paramref name="bounds"/> fits inside the camera's viewing volume, assuming a perspective camera.
        /// </para>
        /// <para>
        /// Assumes the camera has the given <paramref name="cameraRotation"/>, which orients it to look at bounds.center with zero roll (rotation.z = 0).<br />
        /// This function does NOT take into account the camera's, nor the bounds' positions.
        /// </para>
        /// </summary>
        private async Task<Vector3> CalculateFramingParams(Camera camera, Vector3 centerPos, Quaternion cameraRot, ModelLoadResult model) {
            if (camera.orthographic)
                throw new NotSupportedException("This function currently only supports perspective cameras.");

            Vector3 worldPos = new();

            //ITERATION 1: Approximate framing based on world-space AABB.
            //  Camera transform starts off being centered at the world-space AABB center (centerPos).
            Matrix4x4 cameraToWorld = Matrix4x4.TRS(centerPos, cameraRot, new Vector3(1, 1, 1));
            Matrix4x4 worldToCamera = cameraToWorld.inverse;
            MeshCacheSet cameraCache = model.CopyMeshCacheWith(t => (t != null) ? worldToCamera * t.localToWorldMatrix : Matrix4x4.identity, null);
            Bounds localBounds = await cameraCache.CalculateBounds(); //NOTE: In camera local-space.
            Vector3 localCenterXY = new(localBounds.center.x, localBounds.center.y, 0);

            IGizmosVisualizer gizmos = ServiceLocator.Default.GetSystem<IGizmosVisualizer>();
            if (gizmos != null) {
                lastCameraToWorld = cameraToWorld;
                lastLocalBounds = localBounds;
                gizmos.RemoveGizmosCallback(DebugGizmos);
                gizmos.AddGizmosCallback(DebugGizmos);
            }

            float tanHalfY = Mathf.Tan(camera.fieldOfView / 2 * Mathf.Deg2Rad);
            float tanHalfX = tanHalfY * ((float) 1920 / 1080); //camera.aspect;
            float minDistance = 0;
            foreach (Vector3 corner in GameObjectUtility.Get8Corners(localBounds).Select(c => c - localCenterXY)) {
                //tanθ = opp / adj, where Z-axis distance is adj:
                //  → adj = opp / tanθ.
                //  Then, we subtract away the distance they already are from the camera, which is corner.z:
                float minDistFromCorner = Mathf.Max(
                    Mathf.Abs(corner.x) / tanHalfX - corner.z,
                    Mathf.Abs(corner.y) / tanHalfY - corner.z,
                    camera.nearClipPlane - corner.z //nearClipPlane constraint: For very close near-0, and also negative values of corner.z, we need to impose a distance minimum to push the camera back enough to not clip!
                );

                //HOWEVER, these are distances from each CORNER! We need to then project that along the camera's forward axis, to the center...
                //  +/- z-axis simply, because we're operating in camera local-space.
                minDistance = Mathf.Max(minDistance, minDistFromCorner);
            }
            Vector3 localPos = new Vector3(localCenterXY.x, localCenterXY.y, -minDistance);
            worldPos = cameraToWorld.MultiplyPoint(localPos);

            //ITERATION 2: Center xy framing in viewport space.
            //        M   *   V    *   P,   perspective divide      1/2x + 1/2
            //  Model → World → Camera → Clip         →      NDC     → Viewport
            if (recenterX || recenterY) {
                cameraToWorld = Matrix4x4.TRS(worldPos, cameraRot, new Vector3(1, 1, 1));
                worldToCamera = cameraToWorld.inverse;
                Matrix4x4 proj = camera.projectionMatrix;
                MeshCacheSet projCache = model.CopyMeshCacheWith(t => (t != null) ? proj * worldToCamera * t.localToWorldMatrix : Matrix4x4.identity, p => ((Vector3) p / p.w) / 2 + new Vector3(0.5f, 0.5f, 0));
                Bounds viewportBounds = await projCache.CalculateBounds();

                Vector2 deltaViewport = new Vector2(0.5f, 0.5f) - ((Vector2) viewportBounds.min + (Vector2) viewportBounds.max) / 2; //(targetCenter = 0.5, minus the average (center) of the target object's current center)
                Vector2 deltaNDC = 2 * deltaViewport;
                float fovX = 2 * Mathf.Atan(tanHalfX); //NOTE: This is in radians.

                Vector3 cameraCenter = worldToCamera.MultiplyPoint(model.boundsTask.Result.center);
                float referenceZ = cameraCenter.z;
                Vector2 delta = deltaNDC * referenceZ * Mathf.Tan(fovX / 2); //NOTE: In world-space, expected to be oriented along the camera's right x-axis, and up y-axis.

                if (recenterX)
                    worldPos += cameraToWorld.MultiplyVector(new Vector3(1, 0, 0)) * delta.x;
                if (recenterY)
                    worldPos += cameraToWorld.MultiplyVector(new Vector3(0, 1, 0)) * delta.y;
            }

            return worldPos;
        }
    }
}
