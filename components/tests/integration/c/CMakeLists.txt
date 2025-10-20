cmake_minimum_required(VERSION 3.15)
project(c_integration_tests C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Find required packages
find_package(CURL REQUIRED)
find_package(Threads REQUIRED)

# Add executable
add_executable(c_multiprocess_job
    ${CMAKE_SOURCE_DIR}/c_multiprocess_job.c
)

# Link libraries
target_link_libraries(c_multiprocess_job
    PRIVATE
    ${CURL_LIBRARIES}
    Threads::Threads
)

# Include directories
target_include_directories(c_multiprocess_job
    PRIVATE
    ${CURL_INCLUDE_DIRS}
)

# Compiler flags
target_compile_options(c_multiprocess_job
    PRIVATE
    -Wall
    -Wextra
    -Wpedantic
    -O2
)

# Enable testing
enable_testing()

# Add test
add_test(
    NAME c_multiprocess_test
    COMMAND ${CMAKE_SOURCE_DIR}/test_c_integration.sh
    WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
)

