#!/usr/bin/env perl

use strict;
use warnings;
use v5.10;
use FindBin;
use lib "$FindBin::Bin/../lib";

use Monitoring;
use Time::HiRes qw(sleep);

say "=== Perl SDK Simple Job Example ===\n";

# Initialize SDK
Monitoring::init(
    mode         => 'sidecar',
    app_name     => 'example-perl-job',
    app_version  => '1.0.0',
    site_id      => 'fab1',
    sidecar_url  => 'http://localhost:17000',
);

say "✓ SDK initialized\n";

# Start monitored job
say "Starting monitored job...";
my $ctx = Monitoring::start('process-data', 'PERL-12345');

# Simulate work with progress updates
for my $i (1..5) {
    sleep(1);
    my $progress = $i * 20;
    my $message = sprintf("Processing step %d/5", $i);
    
    Monitoring::progress($ctx, $progress, $message);
    printf("  [%3d%%] %s\n", $progress, $message);
    
    # Add some metrics
    Monitoring::add_metric($ctx, 'temperature', 75.5 + $i);
    Monitoring::add_metric($ctx, 'pressure', 1013.25 - $i * 0.5);
}

# Add final metadata
Monitoring::add_metadata($ctx, 'operator', 'john.doe');
Monitoring::add_metadata($ctx, 'machine_id', 'WFR-001');

# Finish successfully
say "\n✓ Job completed successfully";
Monitoring::finish($ctx);

# Cleanup
Monitoring::shutdown();
say "✓ SDK shut down\n";

