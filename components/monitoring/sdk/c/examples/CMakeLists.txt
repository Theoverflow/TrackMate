cmake_minimum_required(VERSION 3.15)

# Simple job example
add_executable(simple_job simple_job.c)
target_link_libraries(simple_job monitoring)

# Multiprocess job example
add_executable(multiprocess_job multiprocess_job.c)
target_link_libraries(multiprocess_job monitoring)

# Error handling example
add_executable(error_example error_example.c)
target_link_libraries(error_example monitoring)

# Direct mode example
add_executable(direct_mode direct_mode.c)
target_link_libraries(direct_mode monitoring)

# Install examples
install(TARGETS simple_job multiprocess_job error_example direct_mode
    RUNTIME DESTINATION bin/examples
)

