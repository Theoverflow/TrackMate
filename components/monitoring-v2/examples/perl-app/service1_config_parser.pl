#!/usr/bin/env perl

# Service 1: Config Parser
# Reads configuration file, parses it, and stores in memory

use strict;
use warnings;
use v5.10;
use FindBin qw($RealBin);
use lib "$RealBin/../../sdk/perl/lib";

use MonitoringSDK;
use Time::HiRes qw(sleep time);

say "=== Service 1: Config Parser ===\n";

# Initialize monitoring
my $mon = MonitoringSDK->new(
    source   => 'config-service',
    tcp_host => 'localhost',
    tcp_port => 17000,
    debug    => 1
);

# Simulate config file path
my $config_file = $ENV{CONFIG_FILE} || '/etc/app/config.ini';

$mon->log_event('info', 'Config service starting', {
    config_file => $config_file
});

# Simulate reading config file
say "Reading config file: $config_file";
sleep(0.5);

$mon->log_event('info', 'Reading config file', {
    file => $config_file
});

# Simulate parsing
say "Parsing configuration...";
sleep(1.0);

# Simulate config content
my $config_content = <<'EOF';
[database]
host = localhost
port = 5432
name = production_db

[queue]
host = queue.example.com
port = 5672

[files]
input_dir = /data/input
output_dir = /data/output
EOF

# Log config size metric
my $config_size = length($config_content);
$mon->log_metric('config_size_bytes', $config_size, 'bytes');
$mon->log_metric('config_size_kb', $config_size / 1024, 'kilobytes');

say "Config parsed successfully!";
$mon->log_event('info', 'Config loaded successfully', {
    lines => scalar(split /\n/, $config_content),
    size_bytes => $config_size
});

# Simulate config validation
say "Validating configuration...";
sleep(0.5);

my $is_valid = 1;  # Simulate validation result
if ($is_valid) {
    $mon->log_event('info', 'Config validation passed');
    $mon->log_metric('config_valid', 1, 'boolean');
} else {
    $mon->log_event('error', 'Config validation failed');
    $mon->log_metric('config_valid', 0, 'boolean');
}

# Service stays running (in real app)
say "\nService 1 completed. Config in memory.";
say "Stats: " . join(', ', map { "$_=${\$mon->get_stats->{$_}}" } keys %{$mon->get_stats});

$mon->close();
say "\nConfig service finished.\n";

