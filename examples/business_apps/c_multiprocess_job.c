/**
 * Realistic C multiprocess job processing file data.
 * 
 * Business Scenario:
 * - Parent job spawns 20+ subjobs (fork/processes)
 * - Each subjob processes 1MB file data
 * - Tasks take ~1 minute average (simulated)
 * - Full monitoring via HTTP API (libcurl)
 * 
 * Compile: gcc -o c_multiprocess_job c_multiprocess_job.c -lcurl -lssl -lcrypto -lpthread
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>
#include <sys/time.h>
#include <time.h>
#include <curl/curl.h>
#include <openssl/md5.h>
#include <openssl/sha.h>

#define FILE_SIZE_MB 1
#define PROCESSING_TIME_S 1  // 1 sec for testing (60 for production)
#define MAX_SUBJOBS 100

typedef struct {
    int subjob_id;
    int success;
    double processing_time_s;
    long file_size_bytes;
    char md5[33];
    char sha256[65];
    long byte_sum;
} SubjobResult;

// Generate random UUID (simplified)
void generate_uuid(char *uuid_str) {
    sprintf(uuid_str, "%08x-%04x-%04x-%04x-%012lx",
            rand(), rand() & 0xFFFF, rand() & 0xFFFF,
            rand() & 0xFFFF, ((long)rand() << 32) | rand());
}

// Convert bytes to hex string
void bytes_to_hex(unsigned char *bytes, int len, char *hex_str) {
    for (int i = 0; i < len; i++) {
        sprintf(hex_str + (i * 2), "%02x", bytes[i]);
    }
    hex_str[len * 2] = '\0';
}

// Send monitoring event via HTTP POST
int send_monitoring_event(const char *sidecar_url, const char *site_id,
                         const char *app_name, const char *entity_type,
                         const char *business_key, const char *event_kind,
                         const char *status, double duration_s,
                         const char *parent_job_id) {
    CURL *curl;
    CURLcode res;
    char url[512];
    char json[2048];
    char uuid[64];
    
    generate_uuid(uuid);
    
    snprintf(url, sizeof(url), "%s/v1/event", sidecar_url);
    
    // Build JSON payload
    if (parent_job_id) {
        snprintf(json, sizeof(json),
            "{"
            "\"site_id\":\"%s\","
            "\"app\":{\"app_id\":\"%s\",\"name\":\"%s\",\"version\":\"1.0.0\"},"
            "\"entity\":{\"type\":\"%s\",\"id\":\"%s\",\"business_key\":\"%s\"},"
            "\"event\":{\"kind\":\"%s\",\"status\":\"%s\",\"at\":\"%ld\","
            "\"metrics\":{\"duration_s\":%.2f},\"metadata\":{\"parent_job_id\":\"%s\"}}"
            "}",
            site_id, uuid, app_name, entity_type, uuid, business_key,
            event_kind, status, time(NULL), duration_s, parent_job_id);
    } else {
        snprintf(json, sizeof(json),
            "{"
            "\"site_id\":\"%s\","
            "\"app\":{\"app_id\":\"%s\",\"name\":\"%s\",\"version\":\"1.0.0\"},"
            "\"entity\":{\"type\":\"%s\",\"id\":\"%s\",\"business_key\":\"%s\"},"
            "\"event\":{\"kind\":\"%s\",\"status\":\"%s\",\"at\":\"%ld\","
            "\"metrics\":{\"duration_s\":%.2f}}"
            "}",
            site_id, uuid, app_name, entity_type, uuid, business_key,
            event_kind, status, time(NULL), duration_s);
    }
    
    curl = curl_easy_init();
    if (!curl) return -1;
    
    struct curl_slist *headers = NULL;
    headers = curl_slist_append(headers, "Content-Type: application/json");
    
    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, json);
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 5L);
    
    res = curl_easy_perform(curl);
    
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    
    return (res == CURLE_OK) ? 0 : -1;
}

// Generate test file
int generate_test_file(const char *file_path, int size_mb) {
    FILE *fp = fopen(file_path, "wb");
    if (!fp) return -1;
    
    unsigned char buffer[1024];
    for (int i = 0; i < size_mb * 1024; i++) {
        for (int j = 0; j < 1024; j++) {
            buffer[j] = rand() & 0xFF;
        }
        fwrite(buffer, 1, 1024, fp);
    }
    
    fclose(fp);
    return 0;
}

// Process file data
SubjobResult process_file_data(const char *file_path, int subjob_id,
                              const char *site_id, const char *sidecar_url,
                              const char *parent_job_id) {
    SubjobResult result = {0};
    result.subjob_id = subjob_id;
    result.success = 0;
    
    char business_key[64];
    snprintf(business_key, sizeof(business_key), "subjob-%03d", subjob_id);
    
    // Send start event
    send_monitoring_event(sidecar_url, site_id, "c-multiprocess-job",
                         "subjob", business_key, "started", "running",
                         0.0, parent_job_id);
    
    struct timeval start, end;
    gettimeofday(&start, NULL);
    
    // Read file
    FILE *fp = fopen(file_path, "rb");
    if (!fp) {
        send_monitoring_event(sidecar_url, site_id, "c-multiprocess-job",
                             "subjob", business_key, "finished", "failed",
                             0.0, parent_job_id);
        return result;
    }
    
    fseek(fp, 0, SEEK_END);
    long file_size = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    
    unsigned char *data = malloc(file_size);
    if (!data) {
        fclose(fp);
        return result;
    }
    
    fread(data, 1, file_size, fp);
    fclose(fp);
    
    result.file_size_bytes = file_size;
    
    // Compute MD5
    unsigned char md5_hash[MD5_DIGEST_LENGTH];
    MD5(data, file_size, md5_hash);
    bytes_to_hex(md5_hash, MD5_DIGEST_LENGTH, result.md5);
    
    // Compute SHA256
    unsigned char sha256_hash[SHA256_DIGEST_LENGTH];
    SHA256(data, file_size, sha256_hash);
    bytes_to_hex(sha256_hash, SHA256_DIGEST_LENGTH, result.sha256);
    
    // Compute byte sum (sample first 1000 bytes)
    result.byte_sum = 0;
    for (int i = 0; i < (file_size < 1000 ? file_size : 1000); i++) {
        result.byte_sum += data[i];
    }
    
    // Simulate processing time
    sleep(PROCESSING_TIME_S);
    
    free(data);
    
    gettimeofday(&end, NULL);
    result.processing_time_s = (end.tv_sec - start.tv_sec) +
                              (end.tv_usec - start.tv_usec) / 1000000.0;
    
    result.success = 1;
    
    // Send finish event
    send_monitoring_event(sidecar_url, site_id, "c-multiprocess-job",
                         "subjob", business_key, "finished", "succeeded",
                         result.processing_time_s, parent_job_id);
    
    return result;
}

int main(int argc, char *argv[]) {
    int num_subjobs = 20;
    const char *site_id = "site1";
    const char *data_dir = "/tmp/wafer-test-data-c";
    const char *sidecar_url = getenv("SIDECAR_URL");
    
    if (!sidecar_url) {
        sidecar_url = "http://localhost:17000";
    }
    
    // Parse arguments
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--num-subjobs") == 0 && i + 1 < argc) {
            num_subjobs = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--site-id") == 0 && i + 1 < argc) {
            site_id = argv[++i];
        }
    }
    
    if (num_subjobs > MAX_SUBJOBS) {
        num_subjobs = MAX_SUBJOBS;
    }
    
    srand(time(NULL));
    curl_global_init(CURL_GLOBAL_ALL);
    
    // Create data directory
    char cmd[512];
    snprintf(cmd, sizeof(cmd), "mkdir -p %s", data_dir);
    system(cmd);
    
    char parent_job_id[64];
    generate_uuid(parent_job_id);
    
    // Send parent job start event
    send_monitoring_event(sidecar_url, site_id, "c-multiprocess-job",
                         "job", "multiprocess-batch", "started", "running",
                         0.0, NULL);
    
    struct timeval job_start, job_end;
    gettimeofday(&job_start, NULL);
    
    // Generate test files
    printf("Generating %d test files (1MB each)...\n", num_subjobs);
    char file_paths[MAX_SUBJOBS][256];
    for (int i = 0; i < num_subjobs; i++) {
        snprintf(file_paths[i], sizeof(file_paths[i]),
                "%s/test_file_%03d.dat", data_dir, i);
        generate_test_file(file_paths[i], FILE_SIZE_MB);
    }
    
    // Spawn subjobs using fork
    printf("Spawning %d subjobs...\n", num_subjobs);
    pid_t pids[MAX_SUBJOBS];
    SubjobResult results[MAX_SUBJOBS];
    
    for (int i = 0; i < num_subjobs; i++) {
        pids[i] = fork();
        
        if (pids[i] == 0) {
            // Child process
            SubjobResult res = process_file_data(file_paths[i], i, site_id,
                                                sidecar_url, parent_job_id);
            exit(res.success ? 0 : 1);
        }
    }
    
    // Wait for all subjobs
    int successful = 0, failed = 0;
    for (int i = 0; i < num_subjobs; i++) {
        int status;
        waitpid(pids[i], &status, 0);
        if (WIFEXITED(status) && WEXITSTATUS(status) == 0) {
            successful++;
        } else {
            failed++;
        }
    }
    
    gettimeofday(&job_end, NULL);
    double job_elapsed = (job_end.tv_sec - job_start.tv_sec) +
                        (job_end.tv_usec - job_start.tv_usec) / 1000000.0;
    
    // Print summary
    printf("\n============================================================\n");
    printf("JOB SUMMARY\n");
    printf("============================================================\n");
    printf("Total Subjobs: %d\n", num_subjobs);
    printf("Successful: %d\n", successful);
    printf("Failed: %d\n", failed);
    printf("Total Elapsed: %.2fs\n", job_elapsed);
    printf("Total Data Processed: %.2f MB\n", (double)(num_subjobs * FILE_SIZE_MB));
    printf("Throughput: %.2f MB/s\n",
           (double)(num_subjobs * FILE_SIZE_MB) / job_elapsed);
    printf("============================================================\n");
    
    // Send parent job finish event
    send_monitoring_event(sidecar_url, site_id, "c-multiprocess-job",
                         "job", "multiprocess-batch", "finished", "succeeded",
                         job_elapsed, NULL);
    
    // Cleanup
    for (int i = 0; i < num_subjobs; i++) {
        unlink(file_paths[i]);
    }
    
    curl_global_cleanup();
    return 0;
}

