# Wafer Monitor Perl SDK

Production-ready Perl module for monitoring distributed applications and sending events to the Wafer Monitor system.

## Features

- ✅ **Pure Perl**: No complex dependencies
- ✅ **Simple API**: Familiar Perl function interface
- ✅ **Object-Oriented**: Clean OO design
- ✅ **Multiple Backends**: Sidecar, filesystem
- ✅ **Automatic Retries**: Built-in exponential backoff
- ✅ **POD Documentation**: Full perldoc documentation

## Installation

```bash
# Using cpanm
cpanm .

# Manual installation
perl Makefile.PL
make
make test
make install
```

## Dependencies

```bash
# Install dependencies
cpanm LWP::UserAgent JSON::PP Time::HiRes Sys::Hostname Data::UUID
```

## Quick Start

```perl
use Monitoring;

# Initialize SDK
Monitoring::init(
    mode         => 'sidecar',
    app_name     => 'my-perl-app',
    app_version  => '1.0.0',
    site_id      => 'fab1',
    sidecar_url  => 'http://localhost:17000',
);

# Monitor a job
my $ctx = Monitoring::start('process-wafer', 'W-12345');
Monitoring::progress($ctx, 50, 'halfway');
Monitoring::add_metric($ctx, 'temperature', 75.5);
Monitoring::finish($ctx);

# Cleanup
Monitoring::shutdown();
```

## API Reference

### Initialization

```perl
Monitoring::init(
    mode         => 'sidecar',          # or 'direct'
    app_name     => 'my-app',
    app_version  => '1.0.0',
    site_id      => 'fab1',
    instance_id  => 'instance-001',     # optional
    sidecar_url  => 'http://localhost:17000',
    timeout      => 5.0,                # optional
    max_retries  => 3,                  # optional
);

Monitoring::shutdown();
Monitoring::is_initialized();
```

### Context API

```perl
# Start monitoring
my $ctx = Monitoring::start($name, $entity_id, $entity_type);

# Report progress
Monitoring::progress($ctx, 50, 'halfway');

# Add metrics
Monitoring::add_metric($ctx, 'temperature', 75.5);

# Add metadata
Monitoring::add_metadata($ctx, 'operator', 'john.doe');

# Finish
Monitoring::finish($ctx);         # Success
Monitoring::error($ctx, 'error'); # Error
Monitoring::cancel($ctx);         # Cancel
```

## Examples

Run the included examples:

```bash
perl examples/simple_job.pl
perl examples/multiprocess_job.pl
```

## Testing

```bash
# Run tests
prove -l t/

# With verbose output
prove -lv t/
```

## Configuration

### Sidecar Mode (Recommended)

```perl
Monitoring::init(
    mode         => 'sidecar',
    app_name     => 'my-perl-app',
    app_version  => '1.0.0',
    site_id      => 'fab1',
    sidecar_url  => 'http://localhost:17000',
    timeout      => 5.0,
    max_retries  => 3,
);
```

### Direct Mode (File Backend)

```perl
Monitoring::init(
    mode           => 'direct',
    app_name       => 'my-perl-app',
    app_version    => '1.0.0',
    site_id        => 'fab1',
    backend_type   => 'filesystem',
    backend_config => {
        output_dir      => './monitoring_events',
        filename_prefix => 'events',
    },
);
```

## Error Handling

```perl
eval {
    my $ctx = Monitoring::start('risky-job', 'job-001');
    # ... do work ...
    Monitoring::finish($ctx);
};
if ($@) {
    Monitoring::error($ctx, $@);
    die $@;
}
```

## Integration with Parallel Processing

### Using Parallel::ForkManager

```perl
use Parallel::ForkManager;

my $pm = Parallel::ForkManager->new(4);

for my $i (1..100) {
    $pm->start and next;  # Fork
    
    # Each child initializes its own SDK
    Monitoring::init(...);
    
    my $ctx = Monitoring::start('parallel-task', "task-$i");
    # ... do work ...
    Monitoring::finish($ctx);
    
    Monitoring::shutdown();
    
    $pm->finish;
}

$pm->wait_all_children;
```

## Documentation

View full API documentation:

```bash
perldoc Monitoring
perldoc Monitoring::Context
perldoc Monitoring::Backend::Sidecar
```

## License

MIT License - See LICENSE file for details

## Support

For issues and questions:
- GitHub Issues: https://github.com/your-org/wafer-monitor
- Documentation: https://docs.wafer-monitor.io

