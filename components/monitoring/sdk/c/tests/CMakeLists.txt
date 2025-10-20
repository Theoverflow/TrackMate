cmake_minimum_required(VERSION 3.15)

# Test executable
add_executable(test_monitoring test_monitoring.c)
target_link_libraries(test_monitoring monitoring)

# Add test to CTest
add_test(NAME monitoring_tests COMMAND test_monitoring)

# Install test executable
install(TARGETS test_monitoring
    RUNTIME DESTINATION bin/tests
)

