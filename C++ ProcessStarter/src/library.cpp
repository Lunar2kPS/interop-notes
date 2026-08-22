#include "library.h"

#include <Windows.h>
#include <iostream>
#include <string>
#include <fstream>
#include <filesystem>

using std::wcout;
using std::wcerr;
using std::endl;
using std::wstring;
namespace filesystem = std::filesystem;

IMPLEMENTATION_C_EXPORT(void) startProcess(int* immediateExitCode, void** processHandle, int* processID) {
    wcout << L"Starting Python process from C++..." << endl;
    *immediateExitCode = 0;
    *processHandle = nullptr;
    *processID = -1;

    wstring commandLine = L"python ./main.py --watch-mode";
    wstring childWorkingDirectory = L"./scripts/svg-generator";

    SECURITY_ATTRIBUTES security = { };
    security.nLength = sizeof(security);
    security.bInheritHandle = TRUE; //NOTE: This is required for redirecting stdout + stderr
    security.lpSecurityDescriptor = NULL;
    filesystem::create_directories(L"./scripts/svg-generator/logs");
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
}

IMPLEMENTATION_C_EXPORT(bool) isStillRunning(void* processHandle) {
    return WaitForSingleObject(processHandle, 0) == WAIT_TIMEOUT;
}

IMPLEMENTATION_C_EXPORT(bool) killProcess(void* processHandle) {
    bool success = false;
    if (WaitForSingleObject(processHandle, 0) == WAIT_TIMEOUT) {
        success = TerminateProcess(processHandle, 5);
        if (!success) {
            wcout << L"TerminateProcess failed: Error Code " << GetLastError() << endl;
        }

        //NOTE: This waits until termination is complete.
        WaitForSingleObject(processHandle, INFINITE);
    }
    return success;
}

IMPLEMENTATION_C_EXPORT(void) closeHandle(void* processHandle) {
    CloseHandle(processHandle);
}
