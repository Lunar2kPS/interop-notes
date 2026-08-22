#include "exports.h"

//NOTE: Would be nice to eventually pass in string values via P/Invoke'd from C#.
HEADER_C_EXPORT void startProcess(int* immediateExitCode, void** processHandle, int* processID);
HEADER_C_EXPORT bool isStillRunning(void* processHandle);
HEADER_C_EXPORT bool killProcess(void* processHandle);
HEADER_C_EXPORT void closeHandle(void* processHandle);
