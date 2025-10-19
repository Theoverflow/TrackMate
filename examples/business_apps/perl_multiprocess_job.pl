#!/usr/bin/env perl

=head1 NAME

perl_multiprocess_job.pl - Realistic Perl multiprocess job processing file data

=head1 DESCRIPTION

Business Scenario:
- Parent job spawns 20+ subjobs (fork/processes)
- Each subjob processes 1MB file data
- Tasks take ~1 minute average (simulated)
- Full monitoring via HTTP API

=cut

use strict;
use warnings;
use File::Path qw(make_path);
use File::Basename;
use Digest::MD5 qw(md5_hex);
use Digest::SHA qw(sha256_hex);
use LWP::UserAgent;
use JSON;
use Time::HiRes qw(time sleep);
use Parallel::ForkManager;
use Getopt::Long;

use constant FILE_SIZE_MB => 1;
use constant PROCESSING_TIME_S => 1;  # 1 sec for testing (60 for production)

# Generate UUID (simplified)
sub generate_uuid {
    return sprintf("%08x-%04x-%04x-%04x-%012x",
                   int(rand(0xFFFFFFFF)),
                   int(rand(0xFFFF)),
                   int(rand(0xFFFF)),
                   int(rand(0xFFFF)),
                   int(rand(0xFFFFFFFFFFFF)));
}

# Send monitoring event
sub send_monitoring_event {
    my ($sidecar_url, $site_id, $app_name, $entity_type, $business_key,
        $event_kind, $status, $duration_s, $parent_job_id) = @_;
    
    my $ua = LWP::UserAgent->new(timeout => 5);
    my $uuid = generate_uuid();
    
    my $event = {
        site_id => $site_id,
        app => {
            app_id => $uuid,
            name => $app_name,
            version => '1.0.0'
        },
        entity => {
            type => $entity_type,
            id => $uuid,
            business_key => $business_key
        },
        event => {
            kind => $event_kind,
            status => $status,
            at => time(),
            metrics => {
                duration_s => $duration_s
            }
        }
    };
    
    if ($parent_job_id) {
        $event->{event}{metadata} = {
            parent_job_id => $parent_job_id
        };
    }
    
    my $json = encode_json($event);
    
    my $response = $ua->post(
        "$sidecar_url/v1/event",
        Content_Type => 'application/json',
        Content => $json
    );
    
    return $response->is_success;
}

# Generate test file
sub generate_test_file {
    my ($file_path, $size_mb) = @_;
    
    open my $fh, '>', $file_path or die "Cannot create file: $!";
    binmode $fh;
    
    for (my $i = 0; $i < $size_mb * 1024; $i++) {
        my $data = pack('C*', map { int(rand(256)) } (1..1024));
        print $fh $data;
    }
    
    close $fh;
}

# Process file data
sub process_file_data {
    my ($file_path, $subjob_id, $site_id, $sidecar_url, $parent_job_id) = @_;
    
    my $business_key = sprintf("subjob-%03d", $subjob_id);
    my $result = {
        subjob_id => $subjob_id,
        success => 0
    };
    
    # Send start event
    send_monitoring_event($sidecar_url, $site_id, 'perl-multiprocess-job',
                         'subjob', $business_key, 'started', 'running',
                         0.0, $parent_job_id);
    
    my $start_time = time();
    
    eval {
        # Read file
        open my $fh, '<', $file_path or die "Cannot read file: $!";
        binmode $fh;
        local $/ = undef;
        my $data = <$fh>;
        close $fh;
        
        my $file_size = length($data);
        $result->{file_size_bytes} = $file_size;
        $result->{file_size_mb} = $file_size / (1024 * 1024);
        
        # Compute hashes
        $result->{md5} = md5_hex($data);
        $result->{sha256} = sha256_hex($data);
        
        # Compute byte sum (sample first 1000 bytes)
        my $byte_sum = 0;
        my $sample_size = $file_size < 1000 ? $file_size : 1000;
        for (my $i = 0; $i < $sample_size; $i++) {
            $byte_sum += ord(substr($data, $i, 1));
        }
        $result->{byte_sum} = $byte_sum;
        
        # Simulate processing time
        sleep(PROCESSING_TIME_S);
        
        my $elapsed = time() - $start_time;
        $result->{processing_time_s} = $elapsed;
        $result->{success} = 1;
        
        # Send finish event
        send_monitoring_event($sidecar_url, $site_id, 'perl-multiprocess-job',
                             'subjob', $business_key, 'finished', 'succeeded',
                             $elapsed, $parent_job_id);
    };
    
    if ($@) {
        $result->{error} = $@;
        send_monitoring_event($sidecar_url, $site_id, 'perl-multiprocess-job',
                             'subjob', $business_key, 'finished', 'failed',
                             0.0, $parent_job_id);
    }
    
    return $result;
}

# Main function
sub main {
    my $num_subjobs = 20;
    my $site_id = 'site1';
    my $data_dir = '/tmp/wafer-test-data-perl';
    my $sidecar_url = $ENV{SIDECAR_URL} || 'http://localhost:17000';
    
    GetOptions(
        'num-subjobs=i' => \$num_subjobs,
        'site-id=s' => \$site_id,
        'data-dir=s' => \$data_dir,
        'sidecar-url=s' => \$sidecar_url
    ) or die "Error in command line arguments\n";
    
    # Create data directory
    make_path($data_dir) unless -d $data_dir;
    
    my $parent_job_id = generate_uuid();
    
    # Send parent job start event
    send_monitoring_event($sidecar_url, $site_id, 'perl-multiprocess-job',
                         'job', 'multiprocess-batch', 'started', 'running',
                         0.0, undef);
    
    my $job_start_time = time();
    
    # Generate test files
    print "Generating $num_subjobs test files (1MB each)...\n";
    my @file_paths;
    for (my $i = 0; $i < $num_subjobs; $i++) {
        my $file_path = sprintf("%s/test_file_%03d.dat", $data_dir, $i);
        generate_test_file($file_path, FILE_SIZE_MB);
        push @file_paths, $file_path;
    }
    
    # Spawn subjobs using Parallel::ForkManager
    print "Spawning $num_subjobs subjobs...\n";
    
    my $pm = Parallel::ForkManager->new($num_subjobs);
    my @results;
    
    $pm->run_on_finish(sub {
        my ($pid, $exit_code, $ident, $exit_signal, $core_dump, $data_ref) = @_;
        push @results, $data_ref if $data_ref;
    });
    
    for (my $i = 0; $i < $num_subjobs; $i++) {
        $pm->start and next;
        
        # Child process
        my $result = process_file_data($file_paths[$i], $i, $site_id,
                                      $sidecar_url, $parent_job_id);
        
        $pm->finish(0, $result);
    }
    
    $pm->wait_all_children;
    
    my $job_elapsed = time() - $job_start_time;
    
    # Analyze results
    my $successful = grep { $_->{success} } @results;
    my $failed = scalar(@results) - $successful;
    
    my $total_processing_time = 0;
    my $total_data_mb = 0;
    
    foreach my $result (@results) {
        if ($result->{success}) {
            $total_processing_time += $result->{processing_time_s};
            $total_data_mb += $result->{file_size_mb};
        }
    }
    
    my $avg_processing_time = $successful > 0 ? $total_processing_time / $successful : 0;
    my $throughput = $job_elapsed > 0 ? $total_data_mb / $job_elapsed : 0;
    
    # Print summary
    print "\n" . "=" x 60 . "\n";
    print "JOB SUMMARY\n";
    print "=" x 60 . "\n";
    printf "Total Subjobs: %d\n", $num_subjobs;
    printf "Successful: %d\n", $successful;
    printf "Failed: %d\n", $failed;
    printf "Total Elapsed: %.2fs\n", $job_elapsed;
    printf "Avg Processing Time: %.2fs\n", $avg_processing_time;
    printf "Total Data Processed: %.2f MB\n", $total_data_mb;
    printf "Throughput: %.2f MB/s\n", $throughput;
    print "=" x 60 . "\n";
    
    # Send parent job finish event
    send_monitoring_event($sidecar_url, $site_id, 'perl-multiprocess-job',
                         'job', 'multiprocess-batch', 'finished', 'succeeded',
                         $job_elapsed, undef);
    
    # Cleanup
    foreach my $file_path (@file_paths) {
        unlink $file_path;
    }
    
    return 0;
}

exit main() unless caller;

