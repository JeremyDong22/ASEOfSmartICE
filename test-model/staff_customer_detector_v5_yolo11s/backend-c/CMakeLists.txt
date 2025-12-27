cmake_minimum_required(VERSION 3.18)
project(SmartICEBackend VERSION 1.0.0 LANGUAGES CXX)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Export compile commands for IDE integration
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Compiler flags
set(CMAKE_CXX_FLAGS_DEBUG "-g -O0 -Wall -Wextra")
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -DNDEBUG")

# Find threads
find_package(Threads REQUIRED)

# Find PkgConfig
find_package(PkgConfig REQUIRED)

# FFmpeg (video decoding)
pkg_check_modules(AVCODEC REQUIRED libavcodec)
pkg_check_modules(AVFORMAT REQUIRED libavformat)
pkg_check_modules(AVUTIL REQUIRED libavutil)
pkg_check_modules(SWSCALE REQUIRED libswscale)

# OpenCV (image processing)
find_package(OpenCV REQUIRED)

# PyTorch/libtorch (YOLO inference)
set(CMAKE_PREFIX_PATH "/home/smartice001/.local/lib/python3.12/site-packages/torch/share/cmake")
find_package(Torch REQUIRED)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${TORCH_CXX_FLAGS}")

# CUDA (optional)
find_package(CUDA QUIET)
if(CUDA_FOUND)
    message(STATUS "CUDA found: ${CUDA_VERSION}")
else()
    message(WARNING "CUDA not found - GPU support disabled")
endif()

# ============================================================================
# Main library
# ============================================================================

# Header files
set(HEADER_FILES
    include/http_server.h
    include/video_decoder.h
    include/inference_engine.h
    include/camera_manager.h
    include/thread_pool.h
    include/utils.h
)

# Source files
set(SOURCE_FILES
    src/http_server.cpp
    src/video_decoder.cpp
    src/inference_engine.cpp
    src/camera_manager.cpp
    src/thread_pool.cpp
    src/utils.cpp
)

# Create static library
add_library(smartice_backend STATIC
    ${SOURCE_FILES}
    ${HEADER_FILES}
)

# Include directories
target_include_directories(smartice_backend PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/nlohmann
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/spdlog/include
)

# Link libraries
target_link_libraries(smartice_backend PUBLIC
    Threads::Threads
    ${TORCH_LIBRARIES}
    ${OpenCV_LIBS}
    ${AVCODEC_LIBRARIES}
    ${AVFORMAT_LIBRARIES}
    ${AVUTIL_LIBRARIES}
    ${SWSCALE_LIBRARIES}
)

# Include directories for FFmpeg
target_include_directories(smartice_backend PUBLIC
    ${AVCODEC_INCLUDE_DIRS}
    ${AVFORMAT_INCLUDE_DIRS}
    ${AVUTIL_INCLUDE_DIRS}
    ${SWSCALE_INCLUDE_DIRS}
)

target_compile_definitions(smartice_backend PUBLIC HAS_FFMPEG)

if(CUDA_FOUND)
    target_include_directories(smartice_backend PUBLIC ${CUDA_INCLUDE_DIRS})
    target_compile_definitions(smartice_backend PUBLIC HAS_CUDA)
endif()

# ============================================================================
# Main executable
# ============================================================================

add_executable(smartice_server src/main.cpp)
target_link_libraries(smartice_server PRIVATE smartice_backend)

# ============================================================================
# Installation
# ============================================================================

install(TARGETS smartice_server smartice_backend
    RUNTIME DESTINATION bin
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
)

install(FILES ${HEADER_FILES} DESTINATION include/smartice)

# ============================================================================
# Summary
# ============================================================================

message(STATUS "")
message(STATUS "==================================================")
message(STATUS "SmartICE Backend Configuration Summary")
message(STATUS "==================================================")
message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "C++ standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "")
message(STATUS "Dependencies:")
message(STATUS "  FFmpeg:       ${AVCODEC_VERSION}")
message(STATUS "  OpenCV:       ${OpenCV_VERSION}")
message(STATUS "  PyTorch:      ${Torch_VERSION}")
message(STATUS "  CUDA:         ${CUDA_VERSION}")
message(STATUS "==================================================")
message(STATUS "")
