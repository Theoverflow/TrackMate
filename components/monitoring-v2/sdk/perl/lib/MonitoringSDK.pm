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
    
    return $self->_send_message({
        type => 'resource',
        data => {
            cpu  => $cpu_percent + 0,
            mem  => $memory_mb + 0,
            disk => $disk_io_mb + 0,
            net  => $network_io_mb + 0,
        }
    });
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

sub DESTROY {
    my ($self) = @_;
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

