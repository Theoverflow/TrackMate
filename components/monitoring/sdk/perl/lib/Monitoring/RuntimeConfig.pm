package Monitoring::RuntimeConfig;

use strict;
use warnings;
use v5.10;

use YAML::XS qw(LoadFile);
use JSON::PP;
use File::Spec;
use Time::HiRes qw(sleep time);

our $VERSION = '0.3.0';

=head1 NAME

Monitoring::RuntimeConfig - Runtime configuration with hot-reloading for Perl SDK

=head1 SYNOPSIS

    use Monitoring::RuntimeConfig;
    
    my $default_config = {
        mode => 'sidecar',
        app_name => 'my-perl-app',
        app_version => '1.0.0',
        site_id => 'fab1',
        sidecar_url => 'http://localhost:17000'
    };
    
    Monitoring::RuntimeConfig->init_with_runtime_config(
        config_file => 'monitoring_config.yaml',
        default_config => $default_config,
        auto_reload => 1,
        check_interval => 30,
        on_reload => sub {
            my ($success, $message) = @_;
            if ($success) {
                print "✓ Config reloaded: $message\n";
            } else {
                warn "✗ Config reload failed: $message\n";
            }
        },
        use_fallback => 1
    );

=head1 DESCRIPTION

Enables dynamic backend routing changes without restarting Perl applications.

Features:
- Load configuration from YAML or JSON files
- Auto-detection of file changes
- Hot-reload backends without restart
- Callback support for reload events
- Fallback to default configuration
- Thread-safe operations

=cut

# Runtime state
my $runtime_state = {
    initialized => 0,
    config_file => undef,
    check_interval => 30,
    auto_reload => 0,
    on_reload => undef,
    last_mtime => 0,
    last_reload_time => 0,
    last_reload_success => 0,
    watcher_pid => undef,
    stop_watcher => 0,
};

=head1 METHODS

=head2 init_with_runtime_config(%options)

Initialize SDK with runtime configuration.

Options:
- config_file: Path to YAML/JSON configuration file (required)
- default_config: Hashref with default configuration (fallback)
- auto_reload: Enable automatic config reloading (default: 1)
- check_interval: Check interval in seconds (default: 30)
- on_reload: Coderef callback for reload events
- use_fallback: Use default config if file not found (default: 1)

=cut

sub init_with_runtime_config {
    my ($class, %opts) = @_;
    
    if ($runtime_state->{initialized}) {
        die "Runtime config already initialized. Call shutdown_runtime_config() first.\n";
    }
    
    my $config_file = $opts{config_file} or die "config_file is required\n";
    my $default_config = $opts{default_config};
    my $auto_reload = $opts{auto_reload} // 1;
    my $check_interval = $opts{check_interval} // 30;
    my $on_reload = $opts{on_reload};
    my $use_fallback = $opts{use_fallback} // 1;
    
    # Store runtime options
    $runtime_state->{config_file} = $config_file;
    $runtime_state->{check_interval} = $check_interval;
    $runtime_state->{auto_reload} = $auto_reload;
    $runtime_state->{on_reload} = $on_reload;
    
    # Try to load config from file
    my $config = _load_config_from_file($config_file);
    
    if (!$config && $use_fallback && $default_config) {
        $config = $default_config;
        print STDERR "Using default config as fallback\n";
    } elsif (!$config) {
        die "Failed to load config and no fallback available\n";
    }
    
    # Initialize SDK with loaded config
    eval {
        require Monitoring;
        Monitoring->init(%$config);
        $runtime_state->{last_reload_time} = time();
        $runtime_state->{last_reload_success} = 1;
        print "✓ SDK initialized with runtime config from: $config_file\n";
    };
    if ($@) {
        $on_reload->(0, "Init failed: $@") if $on_reload;
        die $@;
    }
    
    # Get initial file mtime
    if (-f $config_file) {
        $runtime_state->{last_mtime} = (stat($config_file))[9];
    }
    
    # Start auto-reload watcher if enabled
    if ($auto_reload) {
        _start_file_watcher();
    }
    
    $runtime_state->{initialized} = 1;
    
    $on_reload->(1, "Initial configuration loaded") if $on_reload;
    
    return 1;
}

=head2 reload_runtime_config()

Manually reload configuration from file.

Returns 1 on success, 0 on failure.

=cut

sub reload_runtime_config {
    my ($class) = @_;
    
    if (!$runtime_state->{initialized}) {
        warn "Runtime config not initialized\n";
        return 0;
    }
    
    print "Manually reloading configuration...\n";
    return _reload_config();
}

=head2 get_runtime_status()

Get runtime configuration status information.

Returns hashref with status details.

=cut

sub get_runtime_status {
    my ($class) = @_;
    
    if (!$runtime_state->{initialized}) {
        return { initialized => 0 };
    }
    
    return {
        initialized => $runtime_state->{initialized},
        config_file => $runtime_state->{config_file},
        auto_reload => $runtime_state->{auto_reload},
        check_interval => $runtime_state->{check_interval},
        last_reload_time => $runtime_state->{last_reload_time},
        last_reload_success => $runtime_state->{last_reload_success},
    };
}

=head2 set_auto_reload($enabled)

Enable or disable auto-reload.

=cut

sub set_auto_reload {
    my ($class, $enabled) = @_;
    
    if (!$runtime_state->{initialized}) {
        warn "Runtime config not initialized\n";
        return;
    }
    
    if ($enabled && !$runtime_state->{auto_reload}) {
        _start_file_watcher();
        $runtime_state->{auto_reload} = 1;
        print "Auto-reload enabled\n";
    } elsif (!$enabled && $runtime_state->{auto_reload}) {
        _stop_file_watcher();
        $runtime_state->{auto_reload} = 0;
        print "Auto-reload disabled\n";
    }
}

=head2 shutdown_runtime_config()

Shutdown runtime configuration system.

=cut

sub shutdown_runtime_config {
    my ($class) = @_;
    
    return unless $runtime_state->{initialized};
    
    _stop_file_watcher();
    Monitoring->shutdown();
    
    $runtime_state->{initialized} = 0;
    $runtime_state->{config_file} = undef;
    
    print "✓ Runtime config shut down\n";
}

# ============================================================================
# Internal Functions
# ============================================================================

sub _load_config_from_file {
    my ($file_path) = @_;
    
    if (! -f $file_path) {
        warn "Config file not found: $file_path\n";
        return undef;
    }
    
    my $config;
    eval {
        if ($file_path =~ /\.ya?ml$/i) {
            # YAML file
            $config = LoadFile($file_path);
        } elsif ($file_path =~ /\.json$/i) {
            # JSON file
            open my $fh, '<', $file_path or die "Cannot open $file_path: $!\n";
            local $/;
            my $json_text = <$fh>;
            close $fh;
            $config = JSON::PP->new->decode($json_text);
        } else {
            # Try YAML by default
            $config = LoadFile($file_path);
        }
        print "Config loaded from: $file_path\n";
    };
    if ($@) {
        warn "Failed to load config file: $@\n";
        return undef;
    }
    
    return $config;
}

sub _reload_config {
    my $config = _load_config_from_file($runtime_state->{config_file});
    
    if (!$config) {
        $runtime_state->{last_reload_success} = 0;
        $runtime_state->{last_reload_time} = time();
        
        my $msg = "Failed to load config file";
        warn "$msg\n";
        $runtime_state->{on_reload}->(0, $msg) if $runtime_state->{on_reload};
        return 0;
    }
    
    eval {
        # Shutdown current SDK
        Monitoring->shutdown();
        
        # Re-initialize with new config
        Monitoring->init(%$config);
        
        $runtime_state->{last_reload_success} = 1;
        $runtime_state->{last_reload_time} = time();
        
        my $msg = "Configuration reloaded successfully";
        print "✓ $msg\n";
        $runtime_state->{on_reload}->(1, $msg) if $runtime_state->{on_reload};
    };
    if ($@) {
        $runtime_state->{last_reload_success} = 0;
        $runtime_state->{last_reload_time} = time();
        
        my $msg = "Failed to apply new config: $@";
        warn "$msg\n";
        $runtime_state->{on_reload}->(0, $msg) if $runtime_state->{on_reload};
        return 0;
    }
    
    return 1;
}

sub _check_file_changed {
    my $config_file = $runtime_state->{config_file};
    
    return 0 unless -f $config_file;
    
    my $current_mtime = (stat($config_file))[9];
    
    if ($current_mtime > $runtime_state->{last_mtime}) {
        # File was modified
        $runtime_state->{last_mtime} = $current_mtime;
        
        # Small delay to ensure file write is complete
        sleep(0.1);
        
        print "Config file changed, reloading...\n";
        _reload_config();
        
        return 1;
    }
    
    return 0;
}

sub _file_watcher_loop {
    while (!$runtime_state->{stop_watcher}) {
        _check_file_changed();
        sleep($runtime_state->{check_interval});
    }
}

sub _start_file_watcher {
    return if $runtime_state->{watcher_pid};  # Already running
    
    $runtime_state->{stop_watcher} = 0;
    
    # Fork a background process for file watching
    my $pid = fork();
    
    if (!defined $pid) {
        warn "Failed to fork file watcher: $!\n";
        return;
    }
    
    if ($pid == 0) {
        # Child process - run file watcher
        _file_watcher_loop();
        exit(0);
    } else {
        # Parent process - store PID
        $runtime_state->{watcher_pid} = $pid;
        print "File watcher started (PID: $pid, check interval: ",
              $runtime_state->{check_interval}, "s)\n";
    }
}

sub _stop_file_watcher {
    return unless $runtime_state->{watcher_pid};
    
    $runtime_state->{stop_watcher} = 1;
    
    # Kill watcher process
    kill 'TERM', $runtime_state->{watcher_pid};
    waitpid($runtime_state->{watcher_pid}, 0);
    
    $runtime_state->{watcher_pid} = undef;
    print "File watcher stopped\n";
}

1;

__END__

=head1 AUTHOR

Wafer Monitor Team

=head1 LICENSE

Copyright (c) 2025. All rights reserved.

=cut

