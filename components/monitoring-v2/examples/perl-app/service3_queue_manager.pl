#!/usr/bin/env perl

# Service 3: Queue Manager
# Manages job queue and calls DB loader script

use strict;
use warnings;
use v5.10;
use FindBin qw($RealBin);
use lib "$RealBin/../../sdk/perl/lib";

use MonitoringSDK;
use Time::HiRes qw(sleep time);

say "=== Service 3: Queue Manager ===\n";

# Initialize monitoring
my $mon = MonitoringSDK->new(
    source   => 'queue-service',
    tcp_host => 'localhost',
    tcp_port => 17000,
    debug    => 1
);

$mon->log_event('info', 'Queue manager service starting');

# Simulate job queue
my @queue = (
    {id => 'job-1001', file => 'data_001.csv'},
    {id => 'job-1002', file => 'data_002.csv'},
    {id => 'job-1003', file => 'data_003.csv'},
);

say "Queue contains " . scalar(@queue) . " jobs";
$mon->log_metric('queue_size', scalar(@queue), 'count');

foreach my $job (@queue) {
    say "\nProcessing job: $job->{id}";
    
    # Set trace ID for correlation
    $mon->set_trace_id($job->{id});
    
    # Start span for this job
    my $span_id = $mon->start_span('process_job', $job->{id});
    
    $mon->log_event('info', 'Job dequeued', {
        job_id => $job->{id},
        file => $job->{file}
    });
    
    # Log progress: started
    $mon->log_progress($job->{id}, 0, 'started');
    
    # Call DB loader script
    say "  Calling DB loader...";
    $mon->log_event('info', 'Calling DB loader', {
        job_id => $job->{id},
        file => $job->{file}
    });
    
    # Simulate calling script (pass trace_id as env var)
    $ENV{TRACE_ID} = $job->{id};
    my $cmd = "perl $RealBin/script_db_loader.pl $job->{file}";
    my $exit_code = system($cmd);
    
    if ($exit_code == 0) {
        say "  ✓ DB loader completed successfully";
        $mon->log_progress($job->{id}, 100, 'completed');
        $mon->end_span($span_id, 'success');
        $mon->log_metric('jobs_succeeded', 1, 'count');
    } else {
        say "  ✗ DB loader failed";
        $mon->log_event('error', 'DB loader failed', {
            job_id => $job->{id},
            exit_code => $exit_code >> 8
        });
        $mon->log_progress($job->{id}, 100, 'failed');
        $mon->end_span($span_id, 'error');
        $mon->log_metric('jobs_failed', 1, 'count');
    }
    
    sleep(0.5);
}

say "\nAll jobs processed.";
$mon->log_metric('queue_size', 0, 'count');  # Queue empty
say "Stats: " . join(', ', map { "$_=${\$mon->get_stats->{$_}}" } keys %{$mon->get_stats});

$mon->close();
say "\nQueue manager finished.\n";

