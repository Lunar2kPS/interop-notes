using System;
using UnityEngine;

namespace Carlos {
    [Serializable]
    public struct CameraAngle {
        public string name;
        public Vector3 position;
        public Quaternion rotation;

        public void ApplyTo(Camera camera) {
            camera.transform.position = position;
            camera.transform.rotation = rotation;
        }
    }
}
