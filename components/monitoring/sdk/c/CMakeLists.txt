cmake_minimum_required(VERSION 3.15)
project(monitoring_sdk VERSION 0.3.0 LANGUAGES C)

# C Standard
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Compiler flags
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wall -Wextra -Wpedantic")
set(CMAKE_C_FLAGS_DEBUG "${CMAKE_C_FLAGS_DEBUG} -g -O0 -DDEBUG")
set(CMAKE_C_FLAGS_RELEASE "${CMAKE_C_FLAGS_RELEASE} -O3 -DNDEBUG")

# Find dependencies
find_package(CURL REQUIRED)
find_package(Threads REQUIRED)

# Include directories
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${CURL_INCLUDE_DIRS}
)

# Source files
set(SDK_SOURCES
    src/monitoring.c
    src/backends/http_backend.c
    src/backends/file_backend.c
)

# Shared library
add_library(monitoring SHARED ${SDK_SOURCES})
target_link_libraries(monitoring 
    ${CURL_LIBRARIES}
    Threads::Threads
)

# Static library
add_library(monitoring_static STATIC ${SDK_SOURCES})
set_target_properties(monitoring_static PROPERTIES OUTPUT_NAME monitoring)
target_link_libraries(monitoring_static
    ${CURL_LIBRARIES}
    Threads::Threads
)

# Set library properties
set_target_properties(monitoring PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION ${PROJECT_VERSION_MAJOR}
    PUBLIC_HEADER "include/monitoring.h"
)

# Installation
install(TARGETS monitoring monitoring_static
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    PUBLIC_HEADER DESTINATION include
)

# Install backend headers
install(FILES
    src/backends/http_backend.h
    src/backends/file_backend.h
    DESTINATION include/monitoring/backends
)

# Examples
option(BUILD_EXAMPLES "Build example programs" ON)
if(BUILD_EXAMPLES)
    add_subdirectory(examples)
endif()

# Tests
option(BUILD_TESTS "Build test programs" ON)
if(BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()

# pkg-config file
configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/monitoring.pc.in
    ${CMAKE_CURRENT_BINARY_DIR}/monitoring.pc
    @ONLY
)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/monitoring.pc
    DESTINATION lib/pkgconfig
)

# Print summary
message(STATUS "")
message(STATUS "=== Monitoring SDK Configuration ===")
message(STATUS "Version: ${PROJECT_VERSION}")
message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "C Compiler: ${CMAKE_C_COMPILER}")
message(STATUS "Install prefix: ${CMAKE_INSTALL_PREFIX}")
message(STATUS "Build examples: ${BUILD_EXAMPLES}")
message(STATUS "Build tests: ${BUILD_TESTS}")
message(STATUS "====================================")
message(STATUS "")

