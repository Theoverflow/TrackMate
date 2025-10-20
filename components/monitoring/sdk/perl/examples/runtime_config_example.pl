#!/usr/bin/env perl

use strict;
use warnings;
use v5.10;

use FindBin qw($RealBin);
use lib "$RealBin/../lib";

use Monitoring::RuntimeConfig;
use Time::HiRes qw(sleep);

say "=== Perl SDK Runtime Configuration Example ===\n";

# Default configuration (fallback)
my $default_config = {
    mode => 'sidecar',
    app_name => 'runtime-config-perl-example',
    app_version => '1.0.0',
    site_id => 'fab1',
    instance_id => 'perl-runtime-001',
    sidecar_url => 'http://localhost:17000',
};

# Config file path
my $config_file = $ARGV[0] || 'monitoring_config_perl.yaml';
say "Using config file: $config_file\n";

# Reload callback
my $on_reload_callback = sub {
    my ($success, $message) = @_;
    if ($success) {
        say "✓ Config reloaded: $message";
    } else {
        warn "✗ Config reload failed: $message\n";
    }
};

# Initialize with runtime config
Monitoring::RuntimeConfig->init_with_runtime_config(
    config_file => $config_file,
    default_config => $default_config,
    auto_reload => 1,
    check_interval => 10,  # Check every 10 seconds
    on_reload => $on_reload_callback,
    use_fallback => 1,
);

say "✓ SDK initialized with runtime config";
say "✓ Config file: $config_file";
say "✓ Auto-reload: enabled (check every 10 seconds)\n";

say "Running application...";
say "Try editing '$config_file' while this runs!";
say "Add/remove backends and see them activated without restart.";
say "Press Ctrl+C to stop.\n";

# Simulate long-running application
my $event_count = 0;
my $running = 1;

# Setup signal handler
$SIG{INT} = sub {
    $running = 0;
    say "\n\nShutting down gracefully...";
};

# Run main loop
while ($running) {
    # Send periodic events
    $event_count++;
    my $entity_id = "event-$event_count";
    
    eval {
        require Monitoring;
        my $ctx = Monitoring->start('periodic-job', $entity_id);
        if ($ctx) {
            $ctx->progress(50, 'processing');
            $ctx->add_metric('event_number', $event_count);
            $ctx->finish();
            
            say "[$event_count] Sent event to active backends";
        }
    };
    if ($@) {
        warn "Failed to send event: $@\n";
    }
    
    # Display reload status
    my $status = Monitoring::RuntimeConfig->get_runtime_status();
    if ($status->{last_reload_time} && $status->{last_reload_time} > 0) {
        my $elapsed = time() - $status->{last_reload_time};
        printf("    Last reload: %d s ago (%s)\n",
               int($elapsed),
               $status->{last_reload_success} ? "success" : "failed");
    }
    
    sleep(5);  # Wait between events
}

say "\n✓ Shutting down...";
Monitoring::RuntimeConfig->shutdown_runtime_config();

say "✓ Application stopped\n";
say "Summary:";
say "  - Events sent: $event_count";
say "  - Config file: $config_file";
say "  - Final status: runtime config shut down\n";

