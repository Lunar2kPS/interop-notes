using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.SceneManagement;
using GLTFast;

#if UNITY_EDITOR
    using UnityEditor.SceneManagement;
#endif

using Object = UnityEngine.Object;

namespace Carlos {
    [Serializable]
    public class ModelLoadingSystem : IModelLoadingSystem {
        private struct ModelLoadResultInternal {
            public ModelLoadResult publicResult;
            public GltfImport importer;
            public List<Object> unityObjects;
        }

        /// <summary>Scene used as template: lighting, camera rig. Loaded additively; content is created under SyntheticContent.</summary>
        [SerializeField] private string renderScenePath = "Assets/Scenes/Render Scene.unity";

        [SerializeField] private bool logEmptyGLBWarnings = true;
        [SerializeField] private bool includeLoadingAABBs = true;

        private object syncRoot = new();
        private int nextID = 1;
        private Dictionary<int, ModelLoadResultInternal> loadedModels = new();
        private IGizmosVisualizer gizmos;

        public IEnumerable<ModelLoadResult> AllLoadedModels => loadedModels.Values.Select(i => i.publicResult);

        public void OnSystemEnable() {
            gizmos = ServiceLocator.Default.GetSystem<IGizmosVisualizer>();
            if (gizmos != null)
                gizmos.AddGizmosCallback(DrawLoadedModelGizmos);
        }

        public void OnSystemDisable() {
            if (gizmos != null)
                gizmos.RemoveGizmosCallback(DrawLoadedModelGizmos);

            foreach (int key in new List<int>(loadedModels.Keys))
                DisposeModel(key);
            loadedModels.Clear();
        }

        private void DrawLoadedModelGizmos() {
            Color prevColor = Gizmos.color;
            try {
                Gizmos.color = Color.cyan;
                foreach (ModelLoadResult model in AllLoadedModels) {
                    if (model.boundsTask != null && model.boundsTask.IsCompleted) {
                        Bounds bounds = model.boundsTask.Result;
                        Vector3 size = bounds.size;
                        float centerRadius = Mathf.Min(size.x, size.y, size.y) * 0.05f;
                        float centerLineRadius = 2 * centerRadius;
                        Gizmos.DrawWireCube(bounds.center, size);
                        Gizmos.DrawSphere(bounds.center, centerRadius);
                        for (int i = 0; i < 3; i++) {
                            Vector3 axis = new();
                            axis[i] = 1;
                            Gizmos.DrawLine(bounds.center - centerLineRadius * axis, bounds.center + centerLineRadius * axis);
                        }
                    }
                }
            } finally {
                Gizmos.color = prevColor;
            }
        }

        private async Task<byte[]> DownloadBytesFromUrlAsync(string url) {
            using (UnityWebRequest request = UnityWebRequest.Get(url)) {
                request.downloadHandler = new DownloadHandlerBuffer();
                await request.SendWebRequest();
                if (request.result != UnityWebRequest.Result.Success) {
                    Debug.LogWarning("Download failed: " + url + " " + request.error);
                    return null;
                }
                return request.downloadHandler?.data;
            }
        }

        public async Task<ModelLoadResult> LoadModelAsync(string filePath, bool supportS3 = false, Transform parent = null, bool combineMeshes = false, Action<ModelLoadResult> onGameObjectsLoaded = null, CancellationToken cancelToken = default) {
            ModelLoadResult result = new();
            if (supportS3) {
                IAWSCloudSystem aws = ServiceLocator.Default.GetSystem<IAWSCloudSystem>();
                if (aws.TryParseBucketAndKey(filePath, out string bucket, out string key))
                    return await LoadModelS3Async(key, parent, combineMeshes, onGameObjectsLoaded, cancelToken);
            }
            if (Regex.IsMatch(filePath, "^http(s?)://"))
                result.bytes = await DownloadBytesFromUrlAsync(filePath);
            else if (File.Exists(filePath))
                result.bytes = await File.ReadAllBytesAsync(filePath, cancelToken);
            if (result.bytes == null)
                return result;
            result = await LoadBytesToGameObject(result, parent, new ModelLoadOptions() {
                combineAll = combineMeshes,
                onGameObjectsLoaded = onGameObjectsLoaded
            }, cancelToken);
            return result;
        }

        public async Task<ModelLoadResult> LoadModelS3Async(string s3FileKey, Transform parent = null, bool combineMeshes = false, Action<ModelLoadResult> onGameObjectsLoaded = null, CancellationToken cancelToken = default) {
            ModelLoadResult result = new();

            IAWSCloudSystem aws = ServiceLocator.Default.GetSystem<IAWSCloudSystem>();
            try {
                byte[] data = await aws.DownloadFileAsync(s3FileKey, cancelToken);
                if (data != null || data.Length > 0) {
                    result.bytes = data;
                } else {
                    Debug.LogWarning("[S3] GetObject returned no data (empty response) for key: " + s3FileKey);
                }
            } catch (Exception) {
                throw;
            }
            if (result.bytes != null)
                result = await LoadBytesToGameObject(result, parent, new ModelLoadOptions() {
                    combineAll = combineMeshes,
                    onGameObjectsLoaded = onGameObjectsLoaded
                }, cancelToken);
            return result;
        }

        private struct ModelLoadOptions {
            public bool combineAll;
            public Action<ModelLoadResult> onGameObjectsLoaded;
        }
        private async Task<ModelLoadResultInternal> PostProcessModelLoad(ModelLoadResultInternal modelInternal, ModelLoadOptions options) {
            ModelLoadResultInternal modified = modelInternal;
            try {
                if (options.combineAll) {
                    GameObject original = modelInternal.publicResult.gameObject;
                    Transform rootTransform = original.transform;
                    Mesh combined = await MeshUtility.CombineAllMeshes(original.name, original.GetComponentsInChildren<MeshRenderer>(), original.transform);
                    if (combined != null) {
                        if (modified.unityObjects == null)
                            modified.unityObjects = new List<Object>();
                        modified.unityObjects.Add(combined);
                    }

                    {
                        if (original.TryGetComponent(out MeshRenderer prevRenderer))
                            Component.DestroyImmediate(prevRenderer);
                        if (original.TryGetComponent(out MeshFilter prevFilter))
                            Component.DestroyImmediate(prevFilter);
                    }
                    for (int i = rootTransform.childCount - 1; i >= 0; i--)
                        GameObject.DestroyImmediate(rootTransform.GetChild(i).gameObject);
                    MeshRenderer combinedRenderer = original.AddComponent<MeshRenderer>();
                    MeshFilter combinedFilter = original.AddComponent<MeshFilter>();
                    IMaterialSystem materials = ServiceLocator.Default.GetSystem<IMaterialSystem>();
                    materials.SetMaterialRecursively(original, materials.DefaultMaterial);
                    combinedFilter.sharedMesh = combined;
                }
                if (options.onGameObjectsLoaded != null)
                    options.onGameObjectsLoaded(modelInternal.publicResult);
                return modified;
            } catch (Exception e) {
                Debug.LogException(e);
                return modelInternal;
            }
        }

        public bool RegisterObjectWithModel(int id, Object obj) {
            if (loadedModels.TryGetValue(id, out ModelLoadResultInternal internalModel)) {
                if (internalModel.unityObjects == null)
                    internalModel.unityObjects = new List<Object>();
                internalModel.unityObjects.Add(obj);
                loadedModels[id] = internalModel;
                return true;
            }
            return false;
        }

        //WARNING: During this async method, the following is depended on:
        //  1. The active Scene not changing throughout the load process.
        //  2. If using a Transform parent, that no other code is actively modifying its children during the load process.
        private async Task<ModelLoadResult> LoadBytesToGameObject(ModelLoadResult model, Transform parent, ModelLoadOptions options = default, CancellationToken cancelToken = default) {
            Byte[] data = model.bytes;
            if (data == null || data.Length == 0)
                return model;

            //WARNING: GLTFast does NOT support loading with no set parent, so if parent == null, we must create one of our own!
            bool isTempParent = false;
            if (parent == null) {
                isTempParent = true;
                parent = new GameObject("Loading...").transform;
            }

            //NOTE: Use UninterruptedDeferAgent so we don't create glTF-StableFramerate (DontDestroyOnLoad), which is invalid in Editor/Edit mode.
            GltfImport gltf = new(null, new UninterruptedDeferAgent(), null, null);
            lock (syncRoot) {
                model.modelLoadID = nextID;
                nextID = (nextID + 1) % int.MaxValue; //NOTE: In case we're loading millions of parts over the course of one runtime, this will reset to 0 again after reaching 2147483646 (inclusive).
            }
            bool addToLookup = true;
            ModelLoadResultInternal modelInternal = default;
            try {
                bool ok = await gltf.Load(data, null);
                if (!ok) {
                    Debug.LogWarning("[" + nameof(ModelLoadingSystem) + "] gltf.Load failed for '" + parent.name + "'.");
                    return model;
                }
                int prevCount = parent.childCount;

                //NOTE: This spams the editor with "glTF has no (main) scene defined. No scene will be instantiated." warnings.
                //  It only logs those warnings #if DEBUG, but Unity does not reliably document or expose when we are in Release or Debug config for the C# solution/csprojs.
                //  Perhaps we should check out Blender GLB export process to see if we can set a main scene there?
                //ok = await gltf.InstantiateMainSceneAsync(parent, cancelToken);

                //For now, let's side-step it (and if absolutely necessary, with C# Reflection) to call a bit deeper into their logic, WITHOUT the annoying spamming warning...
                //NOTE: This logic is directly coming from GltfImport.cs:703-737 (approximately).
                {
                    GameObjectInstantiator instantiator = new(gltf, parent);
                    bool success;
                    if (!gltf.LoadingDone || gltf.LoadingError)
                        success = false;
                    else {
                        GLTFast.Schema.Root root = gltf.GetSourceRoot();
                        if (root.scene < 0)
                            success = true; //According to glTF sepcification, loading nothing is the correct behavior here.
                        else
                            success = await gltf.InstantiateSceneAsync(instantiator, root.scene, cancelToken);
                    }
                }

                //CASE: When glTF has no (main) scene defined, GLTFast returns true but instantiates nothing. Try scene 0, 1, 2... in that case too.
                bool gotChildren = parent.childCount > prevCount;
                if (!ok || !gotChildren) {
                    int sceneCount = gltf.SceneCount;
                    for (int i = 0; i < sceneCount && !gotChildren; i++) {
                        ok = await gltf.InstantiateSceneAsync(parent, i);
                        gotChildren = parent.childCount > prevCount;
                    }
                    if (!gotChildren)
                        ok = false;
                }

                if (logEmptyGLBWarnings) {
                    //CASE: GLTFast can report success even when the scene is empty (no root nodes). Treat that as failure.
                    bool emptyScene = ok && parent.childCount <= prevCount;
                    if (emptyScene) {
                        Debug.LogWarning("[" + nameof(ModelLoadingSystem) + "] GLB reported instantiated but added no nodes (empty scene?) for '" + parent.name + "'. Re-export with a default scene that has root nodes.");
                        ok = false;
                    } else if (!emptyScene)
                        Debug.LogWarning("[" + nameof(ModelLoadingSystem) + "] No scene instantiated for '" + parent.name + "'. Re-export GLB with a default scene or ensure at least one scene has mesh nodes.");
                }

                int finalCount = parent.childCount;
                if (finalCount > prevCount) {
                    GameObject firstResult = parent.GetChild(prevCount).gameObject;
                    if (isTempParent) {
                        for (int i = prevCount; i < finalCount; i++)
                            parent.GetChild(i).SetParent(null, false);
                    }
                    model.gameObject = firstResult;
                }
            } catch {
                gltf.Dispose();
                addToLookup = false;
                throw;
            } finally {
                modelInternal = new ModelLoadResultInternal() {
                    publicResult = model,
                    importer = gltf
                };
                if (addToLookup) {
                    modelInternal = await PostProcessModelLoad(modelInternal, options);
                    if (includeLoadingAABBs) {
                        await model.GetBoundsAsync();
                        modelInternal.publicResult = model;
                    }
                    loadedModels.Add(model.modelLoadID, modelInternal);
                }
                if (isTempParent && parent != null)
                    GameObject.DestroyImmediate(parent.gameObject);
            }
            return modelInternal.publicResult;
        }

        public bool DisposeModel(int id) {
            if (loadedModels.Remove(id, out ModelLoadResultInternal internalData)) {
                if (internalData.importer != null)
                    internalData.importer.Dispose();
                GameObject instance = internalData.publicResult.gameObject;
                if (instance != null) {
                    IUnityUnifier unifier = ServiceLocator.Default.GetSystem<IUnityUnifier>();
                    unifier.DestroyGameObject(instance);
                }
                if (internalData.unityObjects != null)
                    foreach (Object o in internalData.unityObjects)
                        if (o != null)
                            Object.DestroyImmediate(o);
                return true;
            }
            return false;
        }

        public async Task<Scene> TryLoadRenderScene() {
            try {
                if (!TryGetAlreadyLoadedScene(out Scene renderScene)) {
#if UNITY_EDITOR
                    if (Application.isPlaying) {
#endif
                        AsyncOperation operation = SceneManager.LoadSceneAsync(renderScenePath, LoadSceneMode.Additive);
                        await operation;
                        renderScene = SceneManager.GetSceneByPath(renderScenePath);
#if UNITY_EDITOR
                    } else {
                        renderScene = EditorSceneManager.OpenScene(renderScenePath, OpenSceneMode.Additive);
                    }
#endif
                    if (!renderScene.IsValid()) {
                        Debug.LogWarning("[Render] Failed to open scene at: \"" + renderScenePath + "\".");
                        return default;
                    }
                }
                SceneManager.SetActiveScene(renderScene);
                return renderScene;
            } catch (Exception ex) {
                Debug.LogWarning("[Render] Could not load " + renderScenePath + ": " + ex.Message);
                return default;
            } finally {
            }
        }

        private bool TryGetAlreadyLoadedScene(out Scene renderScene) {
            for (int i = 0; i < SceneManager.sceneCount; i++) {
                Scene s = SceneManager.GetSceneAt(i);
                string path = s.path.Replace('\\', '/');
                if (path == renderScenePath) {
                    renderScene = s;
                    return true;
                }
            }
            renderScene = default;
            return false;
        }
    }
}
