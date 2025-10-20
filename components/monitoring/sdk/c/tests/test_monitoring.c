/**
 * @file test_monitoring.c
 * @brief Unit tests for C monitoring SDK
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "monitoring.h"

#define TEST_PASSED() printf("  ✓ %s\n", __func__)
#define TEST_FAILED(msg) do { \
    fprintf(stderr, "  ✗ %s: %s\n", __func__, msg); \
    exit(1); \
} while(0)

/* Test: SDK version */
void test_version() {
    const char* version = monitoring_version();
    assert(version != NULL);
    assert(strlen(version) > 0);
    TEST_PASSED();
}

/* Test: Error strings */
void test_error_strings() {
    const char* str = monitoring_error_string(MONITORING_OK);
    assert(str != NULL);
    assert(strcmp(str, "Success") == 0);
    
    str = monitoring_error_string(MONITORING_ERROR);
    assert(str != NULL);
    
    str = monitoring_error_string(MONITORING_INVALID_PARAM);
    assert(str != NULL);
    
    TEST_PASSED();
}

/* Test: Initialize and shutdown */
void test_init_shutdown() {
    monitoring_config_t config = {
        .mode = MONITORING_MODE_SIDECAR,
        .app_name = "test-app",
        .app_version = "1.0.0",
        .site_id = "test-site",
        .instance_id = "test-001",
        .sidecar_url = "http://localhost:17000",
        .timeout = 5.0,
        .max_retries = 3,
        .num_backends = 0
    };
    
    /* Test initialization */
    monitoring_error_t err = monitoring_init(&config);
    assert(err == MONITORING_OK);
    
    /* Check initialized state */
    assert(monitoring_is_initialized() == true);
    
    /* Test double initialization (should fail) */
    err = monitoring_init(&config);
    assert(err == MONITORING_ALREADY_INIT);
    
    /* Test shutdown */
    err = monitoring_shutdown();
    assert(err == MONITORING_OK);
    
    /* Check not initialized */
    assert(monitoring_is_initialized() == false);
    
    TEST_PASSED();
}

/* Test: Context API */
void test_context_api() {
    monitoring_config_t config = {
        .mode = MONITORING_MODE_SIDECAR,
        .app_name = "test-app",
        .app_version = "1.0.0",
        .site_id = "test-site",
        .instance_id = "test-001",
        .sidecar_url = "http://localhost:17000",
        .timeout = 5.0,
        .max_retries = 3,
        .num_backends = 0
    };
    
    monitoring_init(&config);
    
    /* Test context creation */
    monitoring_context_t ctx = monitoring_start("test-job", "job-001");
    assert(ctx != NULL);
    
    /* Test adding metrics */
    monitoring_error_t err = monitoring_add_metric(ctx, "metric1", 123.45);
    assert(err == MONITORING_OK);
    
    err = monitoring_add_metric(ctx, "metric2", 67.89);
    assert(err == MONITORING_OK);
    
    /* Test adding metadata */
    err = monitoring_add_metadata(ctx, "key1", "value1");
    assert(err == MONITORING_OK);
    
    err = monitoring_add_metadata(ctx, "key2", "value2");
    assert(err == MONITORING_OK);
    
    /* Test progress */
    err = monitoring_progress(ctx, 50, "halfway");
    assert(err == MONITORING_OK);
    
    /* Test finish */
    err = monitoring_finish(ctx);
    assert(err == MONITORING_OK);
    
    monitoring_shutdown();
    TEST_PASSED();
}

/* Test: Error handling */
void test_error_handling() {
    monitoring_config_t config = {
        .mode = MONITORING_MODE_SIDECAR,
        .app_name = "test-app",
        .app_version = "1.0.0",
        .site_id = "test-site",
        .instance_id = "test-001",
        .sidecar_url = "http://localhost:17000",
        .timeout = 5.0,
        .max_retries = 3,
        .num_backends = 0
    };
    
    monitoring_init(&config);
    
    /* Test context with error */
    monitoring_context_t ctx = monitoring_start("test-error", "job-err-001");
    assert(ctx != NULL);
    
    monitoring_add_metadata(ctx, "error_type", "test_error");
    monitoring_error_t err = monitoring_error(ctx, "Test error message");
    assert(err == MONITORING_OK);
    
    monitoring_shutdown();
    TEST_PASSED();
}

/* Test: Cancel job */
void test_cancel() {
    monitoring_config_t config = {
        .mode = MONITORING_MODE_SIDECAR,
        .app_name = "test-app",
        .app_version = "1.0.0",
        .site_id = "test-site",
        .instance_id = "test-001",
        .sidecar_url = "http://localhost:17000",
        .timeout = 5.0,
        .max_retries = 3,
        .num_backends = 0
    };
    
    monitoring_init(&config);
    
    monitoring_context_t ctx = monitoring_start("test-cancel", "job-cancel-001");
    assert(ctx != NULL);
    
    monitoring_error_t err = monitoring_cancel(ctx);
    assert(err == MONITORING_OK);
    
    monitoring_shutdown();
    TEST_PASSED();
}

/* Test: NULL parameters */
void test_null_parameters() {
    monitoring_config_t config = {
        .mode = MONITORING_MODE_SIDECAR,
        .app_name = "test-app",
        .app_version = "1.0.0",
        .site_id = "test-site",
        .instance_id = "test-001",
        .sidecar_url = "http://localhost:17000",
        .timeout = 5.0,
        .max_retries = 3,
        .num_backends = 0
    };
    
    /* Test NULL config */
    monitoring_error_t err = monitoring_init(NULL);
    assert(err == MONITORING_INVALID_PARAM);
    
    /* Initialize properly */
    monitoring_init(&config);
    
    /* Test NULL context name */
    monitoring_context_t ctx = monitoring_start(NULL, "job-001");
    assert(ctx == NULL);
    
    /* Test NULL entity ID */
    ctx = monitoring_start("test", NULL);
    assert(ctx == NULL);
    
    /* Test operations on NULL context */
    err = monitoring_progress(NULL, 50, "test");
    assert(err == MONITORING_INVALID_PARAM);
    
    err = monitoring_add_metric(NULL, "metric", 123.0);
    assert(err == MONITORING_INVALID_PARAM);
    
    err = monitoring_finish(NULL);
    assert(err == MONITORING_INVALID_PARAM);
    
    monitoring_shutdown();
    TEST_PASSED();
}

/* Test: Utilities */
void test_utilities() {
    char id[64];
    char* result = monitoring_generate_id(id);
    assert(result != NULL);
    assert(strlen(id) > 0);
    
    time_t ts = monitoring_timestamp();
    assert(ts > 0);
    
    TEST_PASSED();
}

/* Main test runner */
int main() {
    printf("\n=== C SDK Unit Tests ===\n\n");
    
    printf("Running tests...\n");
    test_version();
    test_error_strings();
    test_init_shutdown();
    test_context_api();
    test_error_handling();
    test_cancel();
    test_null_parameters();
    test_utilities();
    
    printf("\n✓ All tests passed!\n\n");
    return 0;
}

