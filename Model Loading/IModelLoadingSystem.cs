using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.SceneManagement;

using Object = UnityEngine.Object;

namespace Carlos {
    public interface IModelLoadingSystem : ISystem {
        public IEnumerable<ModelLoadResult> AllLoadedModels { get; }

        public Task<ModelLoadResult> LoadModelAsync(string filePath, bool supportS3 = false, Transform parent = null, bool combineMeshes = false, Action<ModelLoadResult> onGameObjectsLoaded = null, CancellationToken cancelToken = default);
        public Task<ModelLoadResult> LoadModelS3Async(string url, Transform parent = null, bool combineMeshes = false, Action<ModelLoadResult> onGameObjectsLoaded = null, CancellationToken cancelToken = default);

        public bool RegisterObjectWithModel(int id, Object obj);

        public bool DisposeModel(int id);
        public bool DisposeModel(in ModelLoadResult loadedModel) => DisposeModel(loadedModel.modelLoadID);

        public Task<Scene> TryLoadRenderScene();
    }

    /// <summary>
    /// Represents a loaded 3D model from the <see cref="IModelLoadingSystem"/>.<br />
    /// It remains in-memory until <see cref="IModelLoadingSystem.DisposeModel(in ModelLoadResult)"/> is called.
    /// </summary>
    public struct ModelLoadResult : IDisposable {
        public int modelLoadID;
        public byte[] bytes;
        public GameObject gameObject;

        private MeshCacheSet meshCache;
        internal Task<Bounds> boundsTask;

        //NOTE: Because we may combine meshes later on, we expect that gameObject might be destroyed (and thus, don't check it here in these conditions).
        //  That is OK, we are still valid, because we need to allow disposal later on to be 100% sure we clean up everything (including our unityObjects internal list).
        public bool IsValid => modelLoadID > 0 && bytes != null;

        public bool HasGameObject => gameObject != null;

        //NOTE: This always checks to update the bounds if-needed, then returns the Task whether it's completed already or still running:
        public Task<Bounds> GetBoundsAsync() {
            //NOTE: Even if a boundsTask is in-progress, if we've detected that the matrices have changed at all,
            //  we must restart the calculation from the beginning to make sure we always have the latest, up-to-date
            //TODO: Ability to cancel previously-running bounds task. This would be a nice-to-have, for performance.
            if (InitializeMeshCacheIfNeeded() || meshCache.UpdateMatrices())
                boundsTask = meshCache.CalculateBounds();
            else if (boundsTask == null)
                boundsTask = Task.FromResult(default(Bounds));
            return boundsTask;
        }
        private bool InitializeMeshCacheIfNeeded() {
            if (meshCache == null) {
                if (!HasGameObject) {
                    Debug.LogError("Attempted to take a mesh snapshot with no valid " + nameof(GameObject) + "!");
                    return false;
                } else if (!IsValid) {
                    Debug.LogError("Attempted to take a mesh snapshot with an unloaded model load result!");
                    return false;
                }
                meshCache = MeshCacheSet.CreateSnapshot(gameObject.transform); //TODO: Null check, but it has more implications..
                return true;
            }
            return false;
        }

        public MeshCacheSet CopyMeshCacheWith(Func<Transform, Matrix4x4> getMatrixFunc, Func<Vector4, Vector3> postProcessPoint) {
            InitializeMeshCacheIfNeeded();
            return meshCache.CopyWith(getMatrixFunc, postProcessPoint);
        }

        public void Dispose() {
            IModelLoadingSystem modelLoading = ServiceLocator.Default.GetSystem<IModelLoadingSystem>();
            if (modelLoading != null)
                modelLoading.DisposeModel(modelLoadID);
        }
    }
}
