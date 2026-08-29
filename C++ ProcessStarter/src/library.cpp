#include "library.h"

#if defined(WINDOWS)
    #include <Windows.h>
#elif defined(LINUX)
    #include <sys/types.h>
    #include <sys/wait.h>
    #include <signal.h>
    #include <fcntl.h>
    #include <unistd.h>
    #include <spawn.h>
    #include <cerrno>
    #include <cstring>

    using std::strerror;

    extern char** environ;
#endif

#include <iostream>
#include <string>
#include <fstream>
#include <filesystem>

using std::wcout;
using std::wcerr;
using std::cout;
using std::endl;
using std::string;
using std::wstring;
namespace filesystem = std::filesystem;

IMPLEMENTATION_C_EXPORT(void) startProcess(int* immediateExitCode, void** processHandle, int* processID) {
    wcout << L"Starting Python process from C++..." << endl;
    *immediateExitCode = 0;
    *processHandle = nullptr;
    *processID = -1;

    filesystem::create_directories(L"./scripts/svg-generator/logs");

    #if defined(WINDOWS)
        wstring commandLine = L"python ./main.py --watch-mode";
        wstring childWorkingDirectory = L"./scripts/svg-generator";

        SECURITY_ATTRIBUTES security = { };
        security.nLength = sizeof(security);
        security.bInheritHandle = TRUE; //NOTE: This is required for redirecting stdout + stderr
        security.lpSecurityDescriptor = NULL;
        HANDLE outputFile = CreateFileW(
            L"./scripts/svg-generator/logs/python-output.txt",
            GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            &security,
            CREATE_ALWAYS,
            FILE_ATTRIBUTE_NORMAL,
            NULL
        );

        if (outputFile == INVALID_HANDLE_VALUE) {
            wcout << L"Failed to create Python output file. Error Code: " << GetLastError() << L"." << endl;
            *immediateExitCode = 1;
            return;
        }

        STARTUPINFOW startInfo = { };
        startInfo.cb = sizeof(startInfo);
        startInfo.dwFlags = STARTF_USESTDHANDLES; //NOTE: This is required for redirecting stdout + stderr
        startInfo.hStdOutput = outputFile;
        startInfo.hStdError = outputFile;
        PROCESS_INFORMATION processInfo = { };
        BOOL created = CreateProcessW(
            NULL,
            commandLine.data(),
            NULL,
            NULL,
            TRUE,
            0,
            NULL,
            childWorkingDirectory.c_str(),
            &startInfo,
            &processInfo
        );

        if (!created) {
            wcout << L"CreateProcessW failed: Error Code " << GetLastError() << endl;
            CloseHandle(outputFile);
            *immediateExitCode = 2;
            return;
        }

        CloseHandle(processInfo.hThread);
        CloseHandle(outputFile);
        wcout << L"Process started successfully with PID " << processInfo.dwProcessId << "." << endl;

        *processHandle = processInfo.hProcess;
        *processID = static_cast<int>(processInfo.dwProcessId);
    #elif defined(LINUX)
        //Digit     Permissions     Meaning
        //    0        - - -        None
        //    1        - - x        Execute
        //    2        - w -        Write
        //    3        - w x        Write + execute
        //    4        r - -        Read
        //    5        r - x        Read + execute
        //    6        r w -        Read + write
        //    7        r w x        Read + write + execute
        int outputFile = open(
            "./scripts/svg-generator/logs/python-output.txt",
            O_WRONLY | O_CREAT | O_TRUNC,
            0644
        );

        if (outputFile < 0) {
            cout << "Failed to create Python output file: "
                 << strerror(errno) << endl;
            *immediateExitCode = 1;
            return;
        }

        posix_spawn_file_actions_t fileActions = { };
        posix_spawn_file_actions_init(&fileActions);

        posix_spawn_file_actions_adddup2(
            &fileActions,
            outputFile,
            STDOUT_FILENO
        );

        posix_spawn_file_actions_adddup2(
            &fileActions,
            outputFile,
            STDERR_FILENO
        );

        posix_spawn_file_actions_addclose(
            &fileActions,
            outputFile
        );

        //NOTE: We would use `int actionResult = posix_spawn_file_actions_addchdir_np(&fileActions, "./scripts/svg-generator")`
        //  to set the working directory, but it is Ubuntu/glibc-specific, so we'll skip using it to be more portable across Linux OS's.
        // if (actionResult != 0) {
        //     cout << "Failed to set child working directory: "
        //          << strerror(actionResult) << endl;
        //     posix_spawn_file_actions_destroy(&fileActions);
        //     close(outputFile);
        //     *immediateExitCode = 2;
        //     return;
        // }

        char* arguments[] = {
            "python3",
            "./scripts/svg-generator/main.py",
            "--watch-mode",
            nullptr
        };

        pid_t childProcessID = -1;
        int spawnResult = posix_spawnp(
            &childProcessID,
            python,
            &fileActions,
            nullptr,
            arguments,
            environ
        );

        close(outputFile);
        posix_spawn_file_actions_destroy(&fileActions);

        if (spawnResult != 0) {
            cout << "posix_spawnp failed: " << strerror(spawnResult) << endl;
            *immediateExitCode = 3;
            return;
        }

        cout << "Process started successfully with PID " << childProcessID << "." << endl;
        *processHandle = new pid_t(childProcessID);
        *processID = static_cast<int>(childProcessID);
    #endif
}

IMPLEMENTATION_C_EXPORT(bool) isStillRunning(void* processHandle) {
    #if defined(WINDOWS)
        return WaitForSingleObject(processHandle, 0) == WAIT_TIMEOUT;
    #elif defined(LINUX)
        pid_t processID = *static_cast<pid_t*>(processHandle);
        int status = 0;

        pid_t result = waitpid(processID, &status, WNOHANG);
        return result == 0;
    #else
        return false;
    #endif
}

IMPLEMENTATION_C_EXPORT(bool) killProcess(void* processHandle) {
    bool success = false;
    #if defined(WINDOWS)
        if (WaitForSingleObject(processHandle, 0) == WAIT_TIMEOUT) {
            success = TerminateProcess(processHandle, 5);
            if (!success) {
                wcout << L"TerminateProcess failed: Error Code " << GetLastError() << endl;
            }

            //NOTE: This waits until termination is complete.
            WaitForSingleObject(processHandle, INFINITE);
        }
    #elif defined(LINUX)
        pid_t processID = *static_cast<pid_t*>(processHandle);
        if (kill(processID, SIGTERM) == 0) {
            int status = 0;
            success = waitpid(processID, &status, 0) == processID;
        }
    #endif
    return success;
}

IMPLEMENTATION_C_EXPORT(void) closeHandle(void* processHandle) {
    if (processHandle == nullptr)
        return;
    #if defined(WINDOWS)
        CloseHandle(processHandle);
    #elif defined(LINUX)
        delete static_cast<pid_t*>(processHandle);
    #endif
}
