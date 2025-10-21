#!/usr/bin/env perl

# Script: DB Loader
# Loads file data into database

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

# Set trace ID if provided (for correlation)
$mon->set_trace_id($trace_id) if $trace_id;

# Start span
my $span_id = $mon->start_span('load_data', $trace_id);

$mon->log_event('info', 'DB loader starting', {
    file => $filename,
    trace_id => $trace_id
});

# Simulate loading data
my $rows_to_load = int(rand(9000)) + 1000;  # 1000-10000 rows

$mon->log_event('info', 'Connecting to database');
sleep(0.3);

$mon->log_event('info', 'Loading data', {
    file => $filename,
    rows => $rows_to_load
});

# Simulate loading with progress
for (my $i = 0; $i < 5; $i++) {
    sleep(0.2);
    my $percent = int(($i + 1) * 20);
    my $rows_loaded = int($rows_to_load * $percent / 100);
}

# Completed
$mon->log_event('info', 'Data loaded successfully', {
    file => $filename,
    rows => $rows_to_load
});

# Log metrics
$mon->log_metric('rows_loaded', $rows_to_load, 'count', {
    file => $filename
});

# Log resource usage (automatically collected)
$mon->log_resource();  # SDK automatically collects CPU, memory, disk, network metrics

# End span
$mon->end_span($span_id, 'success');

$mon->close();
exit(0);

