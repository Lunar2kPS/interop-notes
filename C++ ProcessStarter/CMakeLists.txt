cmake_minimum_required(VERSION 3.20)
project(ProcessStarter VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED True)

file(GLOB_RECURSE SRC_FILES CONFIGURE_DEPENDS "src/*.cpp")
add_library("${PROJECT_NAME}" SHARED "${SRC_FILES}")
target_include_directories("${PROJECT_NAME}" PUBLIC "src")
target_compile_definitions("${PROJECT_NAME}" PUBLIC
    UNICODE     # NOTE: UNICODE is for Win32 headers.
    _UNICODE    # NOTE: _UNICODE is for CRT (C-Runtime) / MFC headers.
)