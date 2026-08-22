public class CSharpTCPUTF8Example {
    private const string DLLName = "ProcessStarter.dll";
    private const CallingConvention DefaultCC = CallingConvention.Cdecl;

    [DllImport(DLLName, CallingConvention = DefaultCC)]
    private static extern int startProcess(out int immediateExitCode, out IntPtr processHandle, out int processID);

    [DllImport(DLLName, CallingConvention = DefaultCC)]
    private static extern bool isStillRunning(IntPtr processHandle);

    [DllImport(DLLName, CallingConvention = DefaultCC)]
    private static extern bool killProcess(IntPtr processHandle);

    [DllImport(DLLName, CallingConvention = DefaultCC)]
    private static extern void closeHandle(IntPtr processHandle);

    private TcpListener tcpServer;
    private TcpClient tcpClient;
    private int csPort = -1; //NOTE: This corresponds to the tcpServer.
    private int pythonPort = -1; //NOTE: This corresponds to the tcpClient.
    private StreamReader tcpReader;
    private StreamWriter tcpWriter;
    private Task readLoop;
    private IntPtr pythonProcessHandle = IntPtr.Zero;
    private int pythonProcessID = -1;

    private int GetFreeLocalPort() {
        TcpListener server = new(IPAddress.Loopback, 0);
        server.Start();
        try {
            return ((IPEndPoint) server.LocalEndpoint).Port;
        } finally {
            server.Stop();
        }
    }

    private async Task StartTCP() {
        try {
            await ShutdownTCP();
            csPort = GetFreeLocalPort();
            tcpServer = new TcpListener(IPAddress.Loopback, csPort);
            tcpServer.Start();
            JObject j = new(
                new JProperty("csPort", csPort)
            );
            await File.WriteAllTextAsync("./scripts/svg-generator/cs-tcp.json", await j.WriteToPrettyStringAsync());
            Task<TcpClient> waitTask = tcpServer.AcceptTcpClientAsync();

            Debug.Log("Launching Python process for SVG generation...");
            startProcess(out int immediateExitCode, out pythonProcessHandle, out pythonProcessID);
            if (immediateExitCode != 0) {
                Debug.LogError("C++ returned from " + nameof(startProcess) + " with a non-zero exit code error: Exit Code " + immediateExitCode + ".\nCheck the Unity log for more details from wcout.");
                await ShutdownTCP();
                return;
            } else {
                Debug.Log("Python process started! (PID " + pythonProcessID + ")");
            }
            SetProgressMessage("Waiting for Python TCP Client...");
            tcpClient = await waitTask;
            pythonPort = ((IPEndPoint) tcpClient.Client.RemoteEndPoint).Port;
            Debug.Log("ACCEPTED PYTHON CLIENT ON PORT " + pythonPort + "!");
            NetworkStream stream = tcpClient.GetStream();

            UTF8Encoding utf8WithoutBOM = new(encoderShouldEmitUTF8Identifier: false);
            tcpReader = new StreamReader(stream, utf8WithoutBOM);
            tcpWriter = new StreamWriter(stream, utf8WithoutBOM) { AutoFlush = true };
            readLoop = TCPReadLoop();
        } catch (Exception e) {
            Debug.LogError("An error occurred while starting up TCP for C# ←→ Python communication.");
            Debug.LogException(e);
        }
    }

    private async Task<bool> ShutdownTCP() {
        try {
            if (tcpWriter != null)
                await SendPythonExit();
            bool stoppedClient = false;
            bool stoppedServer = false;
            if (tcpWriter != null) {
                tcpWriter.Dispose();
                tcpWriter = null;
            }
            if (tcpReader != null) {
                tcpReader.Dispose();
                tcpReader = null;
            }
            if (tcpClient != null) {
                stoppedClient = true;
                tcpClient.Dispose(); //NOTE: This includes disposing of the underlying NetworkStream from .GetStream().
                tcpClient = null;
                pythonPort = -1;
            }
            if (tcpServer != null) {
                stoppedServer = true;
                tcpServer.Stop();
                tcpServer = null;
                csPort = -1;
            }
            return stoppedClient || stoppedServer;
        } catch (Exception e) {
            Debug.LogError("Failed to gracefully shutdown TCP communication with Python.");
            Debug.LogException(e);
            return true;
        }
    }

    private async Task TCPReadLoop() {
        while (tcpReader != null) {
            string message = await tcpReader.ReadLineAsync();
            if (message == null)
                break;
            Debug.Log("Python: \"" + message + "\"");
            if (message == "complete")
                break;
        }
    }

    private async Task SendPythonExit() {
        if (tcpClient == null || tcpWriter == null) {
            Debug.LogError("Failed to send Python the exit message through TCP: No TCP client and/or TCP write stream set for Python.");
            return;
        }
        Debug.Log("Sending exit to Python...");
        await tcpWriter.WriteLineAsync("exit");
        if (readLoop != null) {
            int maxMS = 6500;
            Task maxDelay = Task.Delay(maxMS);
            Task completed = await Task.WhenAny(maxDelay, readLoop);
            if (completed == maxDelay)
                Debug.LogWarning("Python did not send the complete message after " + ((float) maxMS / 1000).ToString("F1") + "sec.");
        }

        //NOTE: For some reason, we have to wait a little bit of additional time to let the program fully finish cleaning up, despite the wait above.
        await Task.Delay(2000);

        if (pythonProcessHandle != IntPtr.Zero) {
            if (isStillRunning(pythonProcessHandle)) {
                Debug.LogWarning("Terminating the Python process to ensure it doesn't leak.");
                if (!killProcess(pythonProcessHandle))
                    Debug.LogWarning("Unable to terminate the Python process.");
            }
            closeHandle(pythonProcessHandle);
        }
        
        pythonProcessHandle = IntPtr.Zero;
        pythonProcessID = -1;
    }
}
