using System;
using System.Collections.Generic;
using UnityEngine;

namespace Carlos {
    [Serializable]
    public class GizmosVisualizer : IGizmosVisualizer {
        private class GizmosVisualizerBehaviour : MonoBehaviour {
            public event Action onDrawGizmos;
            private void OnDrawGizmos() {
                onDrawGizmos?.Invoke();
            }
        }

        [SerializeField] private bool drawGizmos = true;

        private GizmosVisualizerBehaviour behaviour;
        private List<Action> callbacks = new();
        private IUnityUnifier unifier;

        public void OnSystemAwake() {
            unifier = ServiceLocator.Default.GetSystem<IUnityUnifier>();
            if (behaviour == null) {
                behaviour = new GameObject("[TEMP] Gizmos Visualizer").AddComponent<GizmosVisualizerBehaviour>();
                unifier.PersistGameObject(behaviour.gameObject, false);
                behaviour.gameObject.hideFlags |= HideFlags.NotEditable; //NOTE: We cannot use HideFlags.HideXXX because then our Gizmos callbacks will not be called by Unity!
            }
            behaviour.onDrawGizmos += OnDrawGizmos;
        }

        public void OnSystemDestroy() {
            if (unifier != null && behaviour != null)
                unifier.DestroyGameObject(behaviour.gameObject);
        }

        private void OnDrawGizmos() {
            if (drawGizmos)
                foreach (Action c in callbacks)
                    c();
        }

        public void AddGizmosCallback(Action callback) {
            if (callback == null)
                throw new ArgumentNullException(nameof(callback));
            callbacks.Add(callback);
        }

        public bool RemoveGizmosCallback(Action callback) {
            if (callback == null)
                throw new ArgumentNullException(nameof(callback));
            return callbacks.Remove(callback);
        }

        public void ClearAll() {
            callbacks.Clear();
        }
    }
}
