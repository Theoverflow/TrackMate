#!/usr/bin/env perl

# Script: DB Loader with Job Analysis
# Loads file data into database with comprehensive monitoring

use strict;
use warnings;
use v5.10;
use FindBin qw($RealBin);
use lib "$RealBin/../../sdk/perl/lib";

use MonitoringSDK;
use Time::HiRes qw(sleep time);

my $filename = $ARGV[0] or die "Usage: $0 <filename>\n";
my $trace_id = $ENV{TRACE_ID};  # Get trace ID from parent

# Initialize monitoring
my $mon = MonitoringSDK->new(
    source   => 'db-loader',
    tcp_host => 'localhost',
    tcp_port => 17000,
    debug    => 0  # Less verbose for script
);

# Start job analysis for this script
my $job_id = $mon->start_job_analysis('db_loader_script', 'main');
$mon->set_trace_id($job_id);

# Start span
my $span_id = $mon->start_span('load_data', $job_id);

$mon->log_event('info', 'DB loader starting', {
    file => $filename,
    job_id => $job_id
});

# Track subjobs for different phases
my $connect_subjob = $mon->track_subjob('connect_database', 'task');
my $load_subjob = $mon->track_subjob('load_data', 'task');
my $validate_subjob = $mon->track_subjob('validate_data', 'task');

# Simulate loading data
my $rows_to_load = int(rand(9000)) + 1000;  # 1000-10000 rows

# Phase 1: Connect to database
$mon->log_event('info', 'Connecting to database');
sleep(0.3);
$mon->end_subjob($connect_subjob, 'completed');

# Phase 2: Load data
$mon->log_event('info', 'Loading data', {
    file => $filename,
    rows => $rows_to_load
});

# Simulate loading with progress
for (my $i = 0; $i < 5; $i++) {
    sleep(0.2);
    my $percent = int(($i + 1) * 20);
    my $rows_loaded = int($rows_to_load * $percent / 100);
    
    # Log progress
    $mon->log_progress($job_id, $percent, 'loading');
    
    # Log resource usage with job analysis
    $mon->log_resource();  # Includes job analysis metrics
}

$mon->end_subjob($load_subjob, 'completed');

# Phase 3: Validate data
$mon->log_event('info', 'Validating loaded data');
sleep(0.1);
$mon->end_subjob($validate_subjob, 'completed');

# Completed
$mon->log_event('info', 'Data loaded successfully', {
    file => $filename,
    rows => $rows_to_load,
    job_id => $job_id
});

# Log metrics
$mon->log_metric('rows_loaded', $rows_to_load, 'count', {
    file => $filename,
    job_id => $job_id
});

# Log final resource usage
$mon->log_resource();  # Final job analysis metrics

# Complete job
$mon->log_progress($job_id, 100, 'completed');

# End span
$mon->end_span($span_id, 'success');

# End job analysis
$mon->end_job_analysis('completed');

$mon->close();
exit(0);

