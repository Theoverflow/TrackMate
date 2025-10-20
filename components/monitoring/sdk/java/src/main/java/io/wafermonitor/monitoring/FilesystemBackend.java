package io.wafermonitor.monitoring;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.FileWriter;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Map;

/**
 * Backend that writes events to the filesystem as JSONL files.
 */
class FilesystemBackend implements Backend {
    private static final Logger logger = LoggerFactory.getLogger(FilesystemBackend.class);
    
    private final Path outputDir;
    private final String filenamePrefix;
    private final ObjectMapper objectMapper;
    
    public FilesystemBackend(Map<String, Object> config) {
        String dirPath = (String) config.getOrDefault("output_dir", "./monitoring_events");
        this.outputDir = Paths.get(dirPath);
        this.filenamePrefix = (String) config.getOrDefault("filename_prefix", "events");
        this.objectMapper = new ObjectMapper();
        
        // Create directory if it doesn't exist
        try {
            Files.createDirectories(outputDir);
        } catch (IOException e) {
            logger.error("Failed to create output directory: {}", outputDir, e);
        }
    }
    
    @Override
    public void sendEvent(MonitoringEvent event) {
        try {
            long timestamp = System.currentTimeMillis();
            long pid = ProcessHandle.current().pid();
            String filename = String.format("%s_%d_%d.jsonl", filenamePrefix, timestamp, pid);
            Path filePath = outputDir.resolve(filename);
            
            String jsonLine = objectMapper.writeValueAsString(event) + "\n";
            
            try (FileWriter writer = new FileWriter(filePath.toFile(), true)) {
                writer.write(jsonLine);
            }
            
            logger.debug("Event written to {}", filePath);
            
        } catch (IOException e) {
            logger.error("Failed to write event to file", e);
        }
    }
    
    @Override
    public void close() {
        // Nothing to close for filesystem backend
    }
}

