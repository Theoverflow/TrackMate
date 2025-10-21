#!/usr/bin/env perl

# Service 2: File Receiver
# Receives data files, validates them, and queues for processing

use strict;
use warnings;
use v5.10;
use FindBin qw($RealBin);
use lib "$RealBin/../../sdk/perl/lib";

use MonitoringSDK;
use Time::HiRes qw(sleep time);

say "=== Service 2: File Receiver ===\n";

# Initialize monitoring
my $mon = MonitoringSDK->new(
    source   => 'file-receiver',
    tcp_host => 'localhost',
    tcp_port => 17000,
    debug    => 1
);

$mon->log_event('info', 'File receiver service starting');

# Simulate receiving files
my @files = qw(
    data_2025-10-20_001.csv
    data_2025-10-20_002.csv
    data_2025-10-20_003.csv
);

say "Waiting for files...";
sleep(1);

foreach my $filename (@files) {
    # Generate job ID for this file
    my $job_id = "job-" . time() . "-" . int(rand(10000));
    
    # Set trace ID for correlation
    $mon->set_trace_id($job_id);
    
    say "\nReceived file: $filename";
    $mon->log_event('info', 'File received', {
        filename => $filename,
        job_id => $job_id
    });
    
    # Simulate file size check
    my $file_size = int(rand(5000)) + 1000;  # Random size 1-6 MB
    $mon->log_metric('file_size_kb', $file_size, 'kilobytes', {
        filename => $filename
    });
    
    # Simulate validation
    say "  Validating file...";
    sleep(0.3);
    
    my $is_valid = (rand() > 0.1);  # 90% valid
    
    if ($is_valid) {
        say "  ✓ File valid";
        $mon->log_event('info', 'File validation passed', {
            filename => $filename,
            job_id => $job_id
        });
        $mon->log_metric('file_valid', 1, 'boolean', {
            filename => $filename
        });
        
        # Queue for processing
        say "  Queueing for processing...";
        $mon->log_event('info', 'File queued', {
            filename => $filename,
            job_id => $job_id,
            queue => 'processing'
        });
        
        $mon->log_metric('files_queued', 1, 'count');
        
    } else {
        say "  ✗ File invalid";
        $mon->log_event('error', 'File validation failed', {
            filename => $filename,
            job_id => $job_id,
            reason => 'Invalid format'
        });
        $mon->log_metric('file_valid', 0, 'boolean', {
            filename => $filename
        });
        $mon->log_metric('files_rejected', 1, 'count');
    }
    
    sleep(0.5);
}

say "\nAll files processed.";
say "Stats: " . join(', ', map { "$_=${\$mon->get_stats->{$_}}" } keys %{$mon->get_stats});

$mon->close();
say "\nFile receiver finished.\n";

