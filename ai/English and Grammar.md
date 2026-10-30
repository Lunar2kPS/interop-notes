# English and Grammar
## Complete Sentences
When writing any output to the user, such as summaries and explanations, please write in complete sentences.

A complete sentence in English is a group of words that contains a **subject** and a **predicate**, starts with a **capital letter**, ends with **end punctuation** (such as a period, question mark, or exclamation point), and expresses a **complete thought**.

- **Subject:** The noun, pronoun, or group of words that tells **who** or **what** the sentence is about (Ex: *"The building"* or *"She"*).
- **Predicate:** The verb and its modifiers that tell **what the subject is doing** or **what state it is in** (Ex: *"runs fast"* or *"slept soundly"*).
- **Complete Thought:** The idea stands on its own without leaving the reader waiting for extra information (unlike a fragment or dependent clause like *"Because it was raining"*).
- **Mechanics:** It always begins with a capital letter and finishes with a period (.), question mark (?), or exclamation point (!).

## Vocabulary
Avoid creating new vocabulary for technical explanations and code implementations unless truly necessary. Use simpler words, and existing vocabulary already written in the code instead.

For example, for a JSON file that is output next to every PNG file that is rendered from a Unity/C# process, avoid calling the JSON file a "sidecar". This typically confuses me as the reader, because I (for example) think it has something to do with literal cars. Instead, I would prefer that the JSON files might be referred to as "accompanying JSON files", or "JSON-PNG metadata pairs", which explicitly describes them (which is more helpful for human understanding). After choosing a single description or term to use, be consistent and use that same description or term throughout the conversation. 

---

## Code Comments
Avoid writing comments when the line of code below it is already obvious in its intent. Only use code comments to point out when we had to unexpectedly perform something as a workaround, or there's a common "gotcha" regarding a method call or variable for example, or it is clear that the user didn't already know something.

For example, the `//NOTE:` comment below calls out an edge case, and is written as complete sentences to be as clear as possible for the reader. It refers to `gameObject` and `unityObjects` as nouns, because they are defined variables.

```cs
public class ModelLoadResult : IModelLoadResult, IDisposable {
    internal int modelLoadID;
    internal byte[] bytes;
    internal GameObject gameObject;

    internal JSONGltfImport importer;
    internal List<Object> unityObjects;

    private MeshCacheSet meshCache;
    private Task<Bounds> boundsTask;
    private Task<List<int>[]> duplicateVerticesTask;

    //NOTE: Because we may combine meshes later on, we expect that gameObject might be destroyed (and thus, don't check it here in these conditions).
    //  That is OK, we are still valid, because we need to allow disposal later on to be 100% sure we clean up everything (including our unityObjects internal list).
    public bool IsValid => modelLoadID > 0 && bytes != null;
}
```

In this other example, a `//NOTE:` comment is used to tangentially call out some required setup for the code to behave as intended. 

```cs
public Task<byte[]> RenderToPNG(Camera camera, bool maskMode) {
    int width = 1920;
    int height = 1080;

    CameraClearFlags prevFlags = camera.clearFlags;
    Color prevColor = camera.backgroundColor;
    bool prevMSAA = camera.allowMSAA;
    bool prevHDR = camera.allowHDR;
    AntialiasingMode? prevAA = null;
    bool? prevPP = null;
    if (camera.TryGetComponent(out UniversalAdditionalCameraData uacd)) {
        prevAA = uacd.antialiasing;
        prevPP = uacd.renderPostProcessing;
    }

    if (maskMode)
        SetCameraForMasking(camera);

    //NOTE: This code is written for..
    //  - ProjectSettings.colorSpace = ColorSpace.Linear
    //  - Use sRGB textures and uniform color, so they all are already sRGB for .png file writing (no conversion needed)
    RenderTexture rt = new(width, height, 24, GraphicsFormat.R8G8B8A8_SRGB);
    camera.targetTexture = rt;
    camera.Render();
}
```

## Code Spacing
When multiple lines of code are operating as a unit together to achieve a chunk of work, it is helpful to keep those lines of code together without newlines in between them. When the code begins a separate or new train of thought, an empty line in between helps to separate what is going on, without too many empty lines taking up screen space. For abstracted code that is just calling high-level methods, that is easier for a human to understand without extra space, so it's helpful to keep those calls close-together. In the depths of a complex algorithm spanning dozens to hundreds of lines of code, some occasional empty lines may help to separate parts of the algorithm.

