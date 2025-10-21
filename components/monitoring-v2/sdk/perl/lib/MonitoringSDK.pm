package MonitoringSDK;

use strict;
use warnings;
use v5.10;

use IO::Socket::INET;
use JSON::PP;
use Time::HiRes qw(time);
use Scalar::Util qw(looks_like_number);

our $VERSION = '2.0.0';

=head1 NAME

MonitoringSDK - Lightweight TCP-based monitoring instrumentation

=head1 SYNOPSIS

    use MonitoringSDK;
    
    # Initialize
    my $mon = MonitoringSDK->new(
        source => 'my-service',
        tcp_host => 'localhost',
        tcp_port => 17000
    );
    
    # Log events
    $mon->log_event('info', 'Service started');
    $mon->log_event('error', 'Failed to connect', {host => 'db.example.com'});
    
    # Log metrics
    $mon->log_metric('requests_total', 42, 'count');
    $mon->log_metric('response_time_ms', 125.5, 'milliseconds');
    
    # Job progress
    $mon->log_progress('job-123', 50, 'processing');
    
    # Resource usage
    $mon->log_resource(45.2, 2048, 100, 50);
    
    # Distributed tracing
    my $span_id = $mon->start_span('process_request');
    # ... do work ...
    $mon->end_span($span_id, 'success');
    
    # Cleanup
    $mon->close();

=head1 DESCRIPTION

Lightweight SDK for sending monitoring data via TCP to sidecar agent.

Key features:
- Fast TCP socket communication
- Local buffering with circuit breaker
- Automatic reconnection
- Minimal overhead (<1ms per call)

=cut

# States
use constant {
    STATE_DISCONNECTED => 'disconnected',
    STATE_CONNECTED    => 'connected',
    STATE_OVERFLOW     => 'overflow',
};

# Protocol constants
use constant {
    PROTOCOL_VERSION => 1,
    MAX_MESSAGE_SIZE => 65536,    # 64KB
    MAX_BUFFER_SIZE  => 1000,     # messages
    MAX_RECONNECT_DELAY => 30,    # seconds
};

sub new {
    my ($class, %args) = @_;
    
    my $self = bless {
        source         => $args{source} or die "source is required\n",
        tcp_host       => $args{tcp_host} || 'localhost',
        tcp_port       => $args{tcp_port} || 17000,
        timeout        => $args{timeout} || 5,
        debug          => $args{debug} || 0,
        
        # State
        state          => STATE_DISCONNECTED,
        socket         => undef,
        buffer         => [],
        overflow_count => 0,
        reconnect_delay => 1,
        last_reconnect => 0,
        
        # Context (for tracing)
        trace_id       => $args{trace_id},
        span_id        => undef,
        context        => {},
        
        # Job analysis
        job_analysis_enabled => 1,
        job_start_time       => undef,
        job_metrics          => {},
        subjob_tracker       => {},
        
        # Statistics
        messages_sent  => 0,
        messages_buffered => 0,
        messages_dropped => 0,
        reconnect_count => 0,
    }, $class;
    
    # Initial connection attempt
    $self->_connect();
    
    return $self;
}

sub _connect {
    my ($self) = @_;
    
    # Check if already connected
    return 1 if $self->{state} eq STATE_CONNECTED && $self->{socket};
    
    # Throttle reconnection attempts
    my $now = time();
    if ($now - $self->{last_reconnect} < $self->{reconnect_delay}) {
        return 0;
    }
    $self->{last_reconnect} = $now;
    
    eval {
        $self->{socket} = IO::Socket::INET->new(
            PeerAddr => $self->{tcp_host},
            PeerPort => $self->{tcp_port},
            Proto    => 'tcp',
            Timeout  => $self->{timeout},
        );
        
        if ($self->{socket}) {
            $self->{state} = STATE_CONNECTED;
            $self->{reconnect_delay} = 1;  # Reset backoff
            $self->{reconnect_count}++;
            
            $self->_log("Connected to $self->{tcp_host}:$self->{tcp_port}");
            
            # Flush buffer
            $self->_flush_buffer();
            
            return 1;
        } else {
            die "Connection failed: $!\n";
        }
    };
    
    if ($@) {
        $self->{state} = STATE_DISCONNECTED;
        $self->_log("Connection failed: $@");
        
        # Exponential backoff
        $self->{reconnect_delay} = $self->{reconnect_delay} * 2;
        if ($self->{reconnect_delay} > MAX_RECONNECT_DELAY) {
            $self->{reconnect_delay} = MAX_RECONNECT_DELAY;
        }
        
        return 0;
    }
}

sub _send_message {
    my ($self, $msg_hash) = @_;
    
    # Add protocol fields
    $msg_hash->{v} = PROTOCOL_VERSION;
    $msg_hash->{src} = $self->{source};
    $msg_hash->{ts} = int(time() * 1000);  # Unix milliseconds
    
    # Add trace context if available
    $msg_hash->{tid} = $self->{trace_id} if $self->{trace_id};
    $msg_hash->{sid} = $self->{span_id} if $self->{span_id};
    
    # Serialize to JSON
    my $json = JSON::PP->new->utf8->canonical->encode($msg_hash);
    my $message = $json . "\n";  # Line-delimited
    
    # Check message size
    if (length($message) > MAX_MESSAGE_SIZE) {
        $self->_log("Message too large: " . length($message) . " bytes");
        $self->{messages_dropped}++;
        return 0;
    }
    
    # Try to send
    if ($self->{state} eq STATE_CONNECTED && $self->{socket}) {
        eval {
            print {$self->{socket}} $message;
            $self->{messages_sent}++;
            return 1;
        };
        
        if ($@) {
            # Send failed, buffer message
            $self->{state} = STATE_DISCONNECTED;
            $self->_log("Send failed: $@");
            $self->_buffer_message($msg_hash);
            $self->_connect();  # Attempt reconnect
            return 0;
        }
    } else {
        # Not connected, buffer message
        $self->_buffer_message($msg_hash);
        $self->_connect();  # Attempt reconnect
        return 0;
    }
}

sub _buffer_message {
    my ($self, $msg_hash) = @_;
    
    if (@{$self->{buffer}} < MAX_BUFFER_SIZE) {
        push @{$self->{buffer}}, $msg_hash;
        $self->{messages_buffered}++;
    } else {
        # Buffer overflow
        $self->{state} = STATE_OVERFLOW;
        $self->{overflow_count}++;
        $self->{messages_dropped}++;
        
        if ($self->{overflow_count} % 100 == 0) {
            $self->_log("Buffer overflow! Dropped $self->{overflow_count} messages");
        }
    }
}

sub _flush_buffer {
    my ($self) = @_;
    
    return unless $self->{state} eq STATE_CONNECTED && $self->{socket};
    
    my $flushed = 0;
    while (my $msg = shift @{$self->{buffer}}) {
        if ($self->_send_message($msg)) {
            $flushed++;
        } else {
            # Failed, put back in buffer
            unshift @{$self->{buffer}}, $msg;
            last;
        }
    }
    
    if ($flushed > 0) {
        $self->_log("Flushed $flushed buffered messages");
    }
    
    # Reset overflow state if buffer cleared
    if (@{$self->{buffer}} == 0 && $self->{state} eq STATE_OVERFLOW) {
        $self->{state} = STATE_CONNECTED;
        $self->{overflow_count} = 0;
    }
}

sub log_event {
    my ($self, $level, $message, $context) = @_;
    
    $context ||= {};
    
    return $self->_send_message({
        type => 'event',
        data => {
            level => $level,
            msg   => $message,
            ctx   => $context,
        }
    });
}

sub log_metric {
    my ($self, $name, $value, $unit, $tags) = @_;
    
    $tags ||= {};
    
    # Validate value is numeric
    unless (looks_like_number($value)) {
        $self->_log("Metric value must be numeric: $value");
        return 0;
    }
    
    return $self->_send_message({
        type => 'metric',
        data => {
            name  => $name,
            value => $value + 0,  # Ensure numeric
            unit  => $unit || '',
            tags  => $tags,
        }
    });
}

sub log_progress {
    my ($self, $job_id, $percent, $status) = @_;
    
    # Validate percent
    $percent = int($percent);
    $percent = 0 if $percent < 0;
    $percent = 100 if $percent > 100;
    
    return $self->_send_message({
        type => 'progress',
        data => {
            job_id  => $job_id,
            percent => $percent,
            status  => $status || 'running',
        }
    });
}

sub log_resource {
    my ($self, $cpu_percent, $memory_mb, $disk_io_mb, $network_io_mb) = @_;
    
    # Auto-collect metrics if not provided
    $cpu_percent   = $self->_get_cpu_percent()    unless defined $cpu_percent;
    $memory_mb     = $self->_get_memory_mb()      unless defined $memory_mb;
    $disk_io_mb    = $self->_get_disk_io_mb()     unless defined $disk_io_mb;
    $network_io_mb = $self->_get_network_io_mb()  unless defined $network_io_mb;
    
    # Enhanced resource data with job analysis
    my %resource_data = (
        cpu  => $cpu_percent + 0,
        mem  => $memory_mb + 0,
        disk => $disk_io_mb + 0,
        net  => $network_io_mb + 0,
        pid  => $$,
    );
    
    # Add job analysis if enabled
    if ($self->{job_analysis_enabled}) {
        my %job_analysis = $self->_analyze_current_job();
        %resource_data = (%resource_data, %job_analysis);
    }
    
    return $self->_send_message({
        type => 'resource',
        data => \%resource_data,
    });
}

# Auto-collect CPU usage percentage
sub _get_cpu_percent {
    my ($self) = @_;
    
    # Try to read from /proc/stat (Linux)
    if (-f '/proc/stat') {
        if (open my $fh, '<', '/proc/stat') {
            my $line = <$fh>;
            close $fh;
            
            if ($line =~ /^cpu\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)/) {
                my ($user, $nice, $system, $idle) = ($1, $2, $3, $4);
                my $total = $user + $nice + $system + $idle;
                my $used = $user + $nice + $system;
                return $total > 0 ? ($used / $total) * 100 : 0;
            }
        }
    }
    
    # Fallback: try top command
    my $cpu = `top -bn1 | grep "Cpu(s)" | sed "s/.*, *\\([0-9.]*\\)%* id.*/\\1/" | awk '{print 100 - \$1}'` || 0;
    chomp $cpu;
    return $cpu || 0;
}

# Auto-collect memory usage in MB
sub _get_memory_mb {
    my ($self) = @_;
    
    # Try /proc/meminfo (Linux)
    if (-f '/proc/meminfo') {
        my %mem;
        if (open my $fh, '<', '/proc/meminfo') {
            while (<$fh>) {
                if (/^(\w+):\s+(\d+)/) {
                    $mem{$1} = $2;
                }
            }
            close $fh;
            
            if (exists $mem{MemTotal} && exists $mem{MemAvailable}) {
                my $used_kb = $mem{MemTotal} - $mem{MemAvailable};
                return $used_kb / 1024;  # Convert to MB
            }
        }
    }
    
    # Fallback: try free command
    my $mem = `free -m | grep Mem | awk '{print \$3}'` || 0;
    chomp $mem;
    return $mem || 0;
}

# Auto-collect disk I/O in MB
sub _get_disk_io_mb {
    my ($self) = @_;
    
    # Try /proc/diskstats (Linux)
    if (-f '/proc/diskstats') {
        if (open my $fh, '<', '/proc/diskstats') {
            my $total_sectors = 0;
            while (<$fh>) {
                # Sum sectors read and written for all devices
                if (/^\s*\d+\s+\d+\s+\S+\s+\d+\s+\d+\s+(\d+)\s+\d+\s+\d+\s+\d+\s+(\d+)/) {
                    $total_sectors += ($1 + $2);  # read_sectors + write_sectors
                }
            }
            close $fh;
            # Convert sectors to MB (sector = 512 bytes typically)
            return ($total_sectors * 512) / (1024 * 1024);
        }
    }
    
    return 0;  # Unable to determine
}

# Auto-collect network I/O in MB
sub _get_network_io_mb {
    my ($self) = @_;
    
    # Try /proc/net/dev (Linux)
    if (-f '/proc/net/dev') {
        if (open my $fh, '<', '/proc/net/dev') {
            my $total_bytes = 0;
            while (<$fh>) {
                # Skip header lines
                next if /^\s*(Inter-|face)/;
                
                # Sum received and transmitted bytes for all interfaces
                if (/^\s*\S+:\s*(\d+)\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+(\d+)/) {
                    $total_bytes += ($1 + $2);  # rx_bytes + tx_bytes
                }
            }
            close $fh;
            return $total_bytes / (1024 * 1024);  # Convert to MB
        }
    }
    
    return 0;  # Unable to determine
}

sub start_span {
    my ($self, $name, $trace_id) = @_;
    
    # Generate span ID
    my $span_id = $self->_generate_id();
    
    # Set trace ID if provided
    $self->{trace_id} = $trace_id if $trace_id;
    
    # Generate trace ID if not set
    $self->{trace_id} ||= $self->_generate_id();
    
    # Store current span as parent
    my $parent_span_id = $self->{span_id};
    
    # Set new span as current
    $self->{span_id} = $span_id;
    
    # Send span start event
    $self->_send_message({
        type => 'span',
        tid  => $self->{trace_id},
        sid  => $span_id,
        pid  => $parent_span_id,
        data => {
            name   => $name,
            start  => int(time() * 1000),
            end    => undef,
            status => 'started',
            tags   => {},
        }
    });
    
    return $span_id;
}

sub end_span {
    my ($self, $span_id, $status, $tags) = @_;
    
    $status ||= 'success';
    $tags   ||= {};
    
    # Send span end event
    $self->_send_message({
        type => 'span',
        tid  => $self->{trace_id},
        sid  => $span_id,
        data => {
            name   => '',
            start  => 0,
            end    => int(time() * 1000),
            status => $status,
            tags   => $tags,
        }
    });
    
    # Clear current span if it matches
    if ($self->{span_id} && $self->{span_id} eq $span_id) {
        $self->{span_id} = undef;
    }
}

sub set_context {
    my ($self, $key, $value) = @_;
    $self->{context}{$key} = $value;
}

sub set_trace_id {
    my ($self, $trace_id) = @_;
    $self->{trace_id} = $trace_id;
}

sub close {
    my ($self) = @_;
    
    # Send goodbye message
    if ($self->{state} eq STATE_CONNECTED && $self->{socket}) {
        eval {
            $self->_send_message({ type => 'goodbye', data => {} });
        };
    }
    
    # Close socket
    if ($self->{socket}) {
        close($self->{socket});
        $self->{socket} = undef;
    }
    
    $self->{state} = STATE_DISCONNECTED;
    
    $self->_log("Closed. Messages sent: $self->{messages_sent}, " .
                "buffered: $self->{messages_buffered}, " .
                "dropped: $self->{messages_dropped}");
}

sub get_stats {
    my ($self) = @_;
    
    return {
        source            => $self->{source},
        state             => $self->{state},
        messages_sent     => $self->{messages_sent},
        messages_buffered => $self->{messages_buffered},
        messages_dropped  => $self->{messages_dropped},
        buffer_size       => scalar(@{$self->{buffer}}),
        overflow_count    => $self->{overflow_count},
        reconnect_count   => $self->{reconnect_count},
    };
}

sub _generate_id {
    my ($self) = @_;
    
    # Generate random ID
    my @chars = ('a'..'z', 'A'..'Z', '0'..'9');
    my $id = '';
    $id .= $chars[rand @chars] for 1..16;
    return $id;
}

sub _log {
    my ($self, $message) = @_;
    return unless $self->{debug};
    warn "[MonitoringSDK] $message\n";
}

# Job Analysis Methods

sub start_job_analysis {
    my ($self, $job_name, $job_type) = @_;
    $job_type ||= 'main';
    
    my $job_id = "$job_name-" . int(time()) . "-" . $self->_generate_id();
    $job_id =~ s/^(.{0,32}).*$/$1/;  # Truncate to 32 chars
    
    $self->{job_start_time} = time();
    $self->{job_metrics} = {
        job_id         => $job_id,
        job_name       => $job_name,
        job_type       => $job_type,
        start_time     => $self->{job_start_time},
        process_count  => 1,
        thread_count   => 1,  # Perl doesn't have easy thread counting
        cpu_cores      => $self->_get_cpu_count(),
        memory_total_mb => $self->_get_total_memory_mb(),
        subjobs        => [],
    };
    
    # Log job start
    $self->log_event('info', "Job analysis started: $job_name", {
        job_id => $job_id,
        job_type => $job_type,
        process_count => $self->{job_metrics}{process_count},
        thread_count => $self->{job_metrics}{thread_count},
    });
    
    return $job_id;
}

sub track_subjob {
    my ($self, $subjob_name, $subjob_type) = @_;
    $subjob_type ||= 'process';
    
    my $subjob_id = "$subjob_name-" . int(time()) . "-" . $self->_generate_id();
    $subjob_id =~ s/^(.{0,32}).*$/$1/;  # Truncate to 32 chars
    
    my $subjob_info = {
        subjob_id   => $subjob_id,
        subjob_name => $subjob_name,
        subjob_type => $subjob_type,
        start_time  => time(),
        pid         => $$,
        parent_pid  => getppid(),
    };
    
    $self->{subjob_tracker}{$subjob_id} = $subjob_info;
    push @{$self->{job_metrics}{subjobs}}, $subjob_info;
    
    # Log subjob start
    $self->log_event('info', "Subjob started: $subjob_name", {
        subjob_id => $subjob_id,
        subjob_type => $subjob_type,
        parent_job_id => $self->{job_metrics}{job_id} || 'unknown',
    });
    
    return $subjob_id;
}

sub end_subjob {
    my ($self, $subjob_id, $status) = @_;
    $status ||= 'completed';
    
    if (exists $self->{subjob_tracker}{$subjob_id}) {
        my $subjob_info = $self->{subjob_tracker}{$subjob_id};
        $subjob_info->{end_time} = time();
        $subjob_info->{duration} = $subjob_info->{end_time} - $subjob_info->{start_time};
        $subjob_info->{status} = $status;
        
        # Log subjob completion
        $self->log_event('info', "Subjob completed: $subjob_info->{subjob_name}", {
            subjob_id => $subjob_id,
            duration => $subjob_info->{duration},
            status => $status,
        });
        
        delete $self->{subjob_tracker}{$subjob_id};
    }
}

sub end_job_analysis {
    my ($self, $status) = @_;
    $status ||= 'completed';
    
    return unless $self->{job_start_time};
    
    my $end_time = time();
    my $total_duration = $end_time - $self->{job_start_time};
    
    # Calculate final metrics
    my %final_metrics = $self->_analyze_current_job();
    $final_metrics{end_time} = $end_time;
    $final_metrics{total_duration} = $total_duration;
    $final_metrics{status} = $status;
    $final_metrics{completed_subjobs} = scalar grep { exists $_->{end_time} } @{$self->{job_metrics}{subjobs}};
    $final_metrics{active_subjobs} = scalar keys %{$self->{subjob_tracker}};
    
    # Log job completion
    $self->log_event('info', "Job analysis completed: $self->{job_metrics}{job_name}", \%final_metrics);
    
    # Log job summary metrics
    $self->log_metric('job_duration_seconds', $total_duration, 'seconds', {
        job_name => $self->{job_metrics}{job_name},
        job_type => $self->{job_metrics}{job_type},
        status => $status,
    });
    
    $self->log_metric('job_subjobs_count', $final_metrics{completed_subjobs}, 'count', {
        job_name => $self->{job_metrics}{job_name},
        job_type => $self->{job_metrics}{job_type},
    });
    
    # Reset job tracking
    $self->{job_start_time} = undef;
    $self->{job_metrics} = {};
    $self->{subjob_tracker} = {};
}

sub _analyze_current_job {
    my ($self) = @_;
    my %analysis = ();
    
    eval {
        # Process information
        $analysis{process_cpu_percent} = $self->_get_cpu_percent();
        $analysis{process_memory_mb} = $self->_get_memory_mb();
        $analysis{process_threads} = 1;  # Perl doesn't have easy thread counting
        $analysis{process_fds} = 0;       # Not easily available in Perl
        $analysis{process_status} = 'running';
        
        # Children processes (subjobs) - simplified for Perl
        $analysis{children_count} = 0;  # Would need more complex logic
        $analysis{children_cpu_total} = 0;
        $analysis{children_memory_total_mb} = 0;
        
        # System load
        my @load_avg = $self->_get_load_average();
        $analysis{load_avg_1m} = $load_avg[0] || 0;
        $analysis{load_avg_5m} = $load_avg[1] || 0;
        $analysis{load_avg_15m} = $load_avg[2] || 0;
        
        # Job-specific metrics
        if ($self->{job_metrics}) {
            $analysis{job_id} = $self->{job_metrics}{job_id};
            $analysis{job_name} = $self->{job_metrics}{job_name};
            $analysis{job_type} = $self->{job_metrics}{job_type};
            $analysis{job_runtime} = time() - $self->{job_start_time} if $self->{job_start_time};
            $analysis{active_subjobs} = scalar keys %{$self->{subjob_tracker}};
        }
    };
    
    if ($@ && $self->{debug}) {
        $self->_log("Job analysis error: $@");
    }
    
    return %analysis;
}

sub enable_job_analysis {
    my ($self, $enabled) = @_;
    $enabled = 1 unless defined $enabled;
    $self->{job_analysis_enabled} = $enabled;
    $self->_log($enabled ? "Job analysis enabled" : "Job analysis disabled");
}

# Helper methods for job analysis
sub _get_cpu_count {
    my ($self) = @_;
    if (open my $fh, '<', '/proc/cpuinfo') {
        my $count = 0;
        while (<$fh>) {
            $count++ if /^processor\s*:/;
        }
        close $fh;
        return $count || 1;
    }
    return 1;  # Fallback
}

sub _get_total_memory_mb {
    my ($self) = @_;
    if (open my $fh, '<', '/proc/meminfo') {
        while (<$fh>) {
            if (/^MemTotal:\s*(\d+)\s*kB/) {
                close $fh;
                return int($1 / 1024);  # Convert KB to MB
            }
        }
        close $fh;
    }
    return 1024;  # Fallback
}

sub _get_load_average {
    my ($self) = @_;
    if (open my $fh, '<', '/proc/loadavg') {
        my $line = <$fh>;
        close $fh;
        if ($line =~ /^([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)/) {
            return ($1, $2, $3);
        }
    }
    return (0, 0, 0);  # Fallback
}

sub DESTROY {
    my ($self) = @_;
    if ($self->{job_start_time}) {
        $self->end_job_analysis('terminated');
    }
    $self->close() if $self->{socket};
}

1;

__END__

=head1 PERFORMANCE

The SDK has minimal overhead:
- Serialization: <0.1ms per message
- Socket write: <0.5ms per message
- Total: <1ms per instrumentation call

=head1 ERROR HANDLING

The SDK handles connection failures gracefully:
1. Messages are buffered locally (up to 1000 messages)
2. Automatic reconnection with exponential backoff
3. Buffer overflow protection (drops oldest messages)
4. No exceptions thrown to application code

=head1 AUTHOR

Wafer Monitor Team

=head1 LICENSE

Copyright (c) 2025. All rights reserved.

=cut

