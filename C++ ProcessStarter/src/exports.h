#pragma once

#include "platforms.h"

#if defined(__cplusplus)
    #define EXPORT_LINKAGE_TYPE     extern "C"
#else
    #define EXPORT_LINKAGE_TYPE
#endif

#if defined(WINDOWS)
    #define CALLING_CONVENTION      __cdecl
    #define EXPORT_ATTRIBUTE        __declspec(dllexport)
#else
    #define CALLING_CONVENTION      __attribute__((cdecl))
    #define EXPORT_ATTRIBUTE        __attribute__((visibility("default")))
#endif

#define HEADER_C_EXPORT                         EXPORT_LINKAGE_TYPE EXPORT_ATTRIBUTE
#define IMPLEMENTATION_C_EXPORT(returnType)     EXPORT_LINKAGE_TYPE EXPORT_ATTRIBUTE returnType CALLING_CONVENTION
