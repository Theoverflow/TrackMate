/**
 * Realistic Java multithreaded job processing file data.
 * 
 * Business Scenario:
 * - Parent job spawns 20+ subjobs (threads)
 * - Each subjob processes 1MB file data
 * - Tasks take ~1 minute average (simulated)
 * - Full monitoring via HTTP API
 */

import java.io.*;
import java.net.URI;
import java.net.http.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;
import java.util.stream.Collectors;

public class JavaMultithreadJob {
    
    private static final String SIDECAR_URL = 
        System.getenv().getOrDefault("SIDECAR_URL", "http://localhost:17000");
    private static final int FILE_SIZE_MB = 1;
    private static final long PROCESSING_TIME_MS = 1000; // 1 sec for testing (60000 for production)
    
    static class JobResult {
        boolean success;
        int subjobId;
        Map<String, Object> result;
        String error;
        
        JobResult(boolean success, int subjobId) {
            this.success = success;
            this.subjobId = subjobId;
            this.result = new HashMap<>();
        }
    }
    
    static class MonitoringClient {
        private final HttpClient client;
        private final String baseUrl;
        
        MonitoringClient(String baseUrl) {
            this.baseUrl = baseUrl;
            this.client = HttpClient.newBuilder()
                .connectTimeout(java.time.Duration.ofSeconds(5))
                .build();
        }
        
        void sendEvent(String siteId, String appName, String entityType, 
                      String businessKey, String eventKind, String status,
                      Map<String, Object> metrics, String parentJobId) throws Exception {
            
            Map<String, Object> event = new HashMap<>();
            event.put("site_id", siteId);
            
            Map<String, Object> app = new HashMap<>();
            app.put("app_id", UUID.randomUUID().toString());
            app.put("name", appName);
            app.put("version", "1.0.0");
            event.put("app", app);
            
            Map<String, Object> entity = new HashMap<>();
            entity.put("type", entityType);
            entity.put("id", UUID.randomUUID().toString());
            entity.put("business_key", businessKey);
            event.put("entity", entity);
            
            Map<String, Object> eventData = new HashMap<>();
            eventData.put("kind", eventKind);
            eventData.put("status", status);
            eventData.put("at", Instant.now().toString());
            eventData.put("metrics", metrics);
            
            if (parentJobId != null) {
                Map<String, Object> metadata = new HashMap<>();
                metadata.put("parent_job_id", parentJobId);
                eventData.put("metadata", metadata);
            }
            
            event.put("event", eventData);
            
            String json = new com.google.gson.Gson().toJson(event);
            
            HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(baseUrl + "/v1/event"))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(json))
                .build();
            
            client.send(request, HttpResponse.BodyHandlers.ofString());
        }
    }
    
    static class SubjobWorker implements Callable<JobResult> {
        private final int subjobId;
        private final Path filePath;
        private final String siteId;
        private final String parentJobId;
        private final MonitoringClient monitor;
        
        SubjobWorker(int subjobId, Path filePath, String siteId, 
                    String parentJobId, MonitoringClient monitor) {
            this.subjobId = subjobId;
            this.filePath = filePath;
            this.siteId = siteId;
            this.parentJobId = parentJobId;
            this.monitor = monitor;
        }
        
        @Override
        public JobResult call() {
            String businessKey = String.format("subjob-%03d", subjobId);
            JobResult result = new JobResult(true, subjobId);
            
            try {
                // Send start event
                monitor.sendEvent(siteId, "java-multithread-job", "subjob",
                    businessKey, "started", "running", new HashMap<>(), parentJobId);
                
                long startTime = System.currentTimeMillis();
                
                // Read file
                byte[] data = Files.readAllBytes(filePath);
                
                // Compute hash
                MessageDigest md5 = MessageDigest.getInstance("MD5");
                MessageDigest sha256 = MessageDigest.getInstance("SHA-256");
                
                byte[] md5Hash = md5.digest(data);
                byte[] sha256Hash = sha256.digest(data);
                
                // Simulate processing time
                Thread.sleep(PROCESSING_TIME_MS);
                
                // Compute byte sum (sample)
                long byteSum = 0;
                for (int i = 0; i < Math.min(1000, data.length); i++) {
                    byteSum += (data[i] & 0xFF);
                }
                
                long elapsed = System.currentTimeMillis() - startTime;
                
                // Store results
                result.result.put("file_size_bytes", data.length);
                result.result.put("file_size_mb", data.length / (1024.0 * 1024.0));
                result.result.put("md5", bytesToHex(md5Hash));
                result.result.put("sha256", bytesToHex(sha256Hash));
                result.result.put("byte_sum", byteSum);
                result.result.put("processing_time_ms", elapsed);
                
                // Send finish event
                Map<String, Object> metrics = new HashMap<>();
                metrics.put("duration_s", elapsed / 1000.0);
                metrics.put("mem_max_mb", 
                    (Runtime.getRuntime().totalMemory() - Runtime.getRuntime().freeMemory()) 
                    / (1024.0 * 1024.0));
                
                monitor.sendEvent(siteId, "java-multithread-job", "subjob",
                    businessKey, "finished", "succeeded", metrics, parentJobId);
                
                return result;
                
            } catch (Exception e) {
                result.success = false;
                result.error = e.getMessage();
                
                try {
                    monitor.sendEvent(siteId, "java-multithread-job", "subjob",
                        businessKey, "finished", "failed", new HashMap<>(), parentJobId);
                } catch (Exception ignored) {}
                
                return result;
            }
        }
        
        private static String bytesToHex(byte[] bytes) {
            StringBuilder sb = new StringBuilder();
            for (byte b : bytes) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        }
    }
    
    public static void generateTestFile(Path filePath, int sizeMb) throws IOException {
        try (OutputStream os = Files.newOutputStream(filePath)) {
            Random random = new Random();
            byte[] buffer = new byte[1024];
            
            for (int i = 0; i < sizeMb * 1024; i++) {
                random.nextBytes(buffer);
                os.write(buffer);
            }
        }
    }
    
    public static void main(String[] args) throws Exception {
        int numSubjobs = 20;
        String siteId = "site1";
        Path dataDir = Paths.get("/tmp/wafer-test-data-java");
        
        // Parse arguments
        for (int i = 0; i < args.length; i++) {
            if ("--num-subjobs".equals(args[i]) && i + 1 < args.length) {
                numSubjobs = Integer.parseInt(args[++i]);
            } else if ("--site-id".equals(args[i]) && i + 1 < args.length) {
                siteId = args[++i];
            }
        }
        
        // Create data directory
        Files.createDirectories(dataDir);
        
        MonitoringClient monitor = new MonitoringClient(SIDECAR_URL);
        String parentJobId = UUID.randomUUID().toString();
        
        // Send parent job start event
        monitor.sendEvent(siteId, "java-multithread-job", "job",
            "multithread-batch", "started", "running", new HashMap<>(), null);
        
        long jobStartTime = System.currentTimeMillis();
        
        // Generate test files
        System.out.println("Generating " + numSubjobs + " test files (1MB each)...");
        List<Path> filePaths = new ArrayList<>();
        for (int i = 0; i < numSubjobs; i++) {
            Path filePath = dataDir.resolve(String.format("test_file_%03d.dat", i));
            generateTestFile(filePath, FILE_SIZE_MB);
            filePaths.add(filePath);
        }
        
        // Spawn subjobs using thread pool
        System.out.println("Spawning " + numSubjobs + " subjobs...");
        ExecutorService executor = Executors.newFixedThreadPool(
            Math.min(numSubjobs, Runtime.getRuntime().availableProcessors())
        );
        
        List<Future<JobResult>> futures = new ArrayList<>();
        for (int i = 0; i < numSubjobs; i++) {
            SubjobWorker worker = new SubjobWorker(
                i, filePaths.get(i), siteId, parentJobId, monitor
            );
            futures.add(executor.submit(worker));
        }
        
        // Wait for all subjobs to complete
        List<JobResult> results = new ArrayList<>();
        for (Future<JobResult> future : futures) {
            results.add(future.get());
        }
        
        executor.shutdown();
        
        long jobElapsed = System.currentTimeMillis() - jobStartTime;
        
        // Analyze results
        long successful = results.stream().filter(r -> r.success).count();
        long failed = results.size() - successful;
        
        double avgProcessingTime = results.stream()
            .filter(r -> r.success)
            .mapToDouble(r -> ((Number) r.result.get("processing_time_ms")).doubleValue())
            .average()
            .orElse(0.0);
        
        double totalDataMb = results.stream()
            .filter(r -> r.success)
            .mapToDouble(r -> ((Number) r.result.get("file_size_mb")).doubleValue())
            .sum();
        
        // Print summary
        System.out.println("\n" + "=".repeat(60));
        System.out.println("JOB SUMMARY");
        System.out.println("=".repeat(60));
        System.out.println("Total Subjobs: " + numSubjobs);
        System.out.println("Successful: " + successful);
        System.out.println("Failed: " + failed);
        System.out.println("Total Elapsed: " + (jobElapsed / 1000.0) + "s");
        System.out.println("Avg Processing Time: " + (avgProcessingTime / 1000.0) + "s");
        System.out.println("Total Data Processed: " + String.format("%.2f", totalDataMb) + " MB");
        System.out.println("Throughput: " + 
            String.format("%.2f", totalDataMb / (jobElapsed / 1000.0)) + " MB/s");
        System.out.println("=".repeat(60));
        
        // Send parent job finish event
        Map<String, Object> metrics = new HashMap<>();
        metrics.put("duration_s", jobElapsed / 1000.0);
        metrics.put("subjobs_total", numSubjobs);
        metrics.put("subjobs_successful", successful);
        metrics.put("subjobs_failed", failed);
        
        monitor.sendEvent(siteId, "java-multithread-job", "job",
            "multithread-batch", "finished", "succeeded", metrics, null);
        
        // Cleanup
        for (Path filePath : filePaths) {
            Files.deleteIfExists(filePath);
        }
    }
}

