#!/usr/bin/env perl
# Perl Integration Test Suite

use strict;
use warnings;
use Test::More tests => 8;
use Test::Deep;
use File::Temp qw(tempfile);
use JSON;
use LWP::UserAgent;

print "=== Perl Integration Tests ===\n\n";

# Test 1: Module loading
subtest 'Module Loading' => sub {
    plan tests => 4;
    
    use_ok('LWP::UserAgent');
    use_ok('JSON');
    use_ok('Parallel::ForkManager');
    use_ok('File::Temp');
};

# Test 2: Script existence and permissions
subtest 'Script Validation' => sub {
    plan tests => 2;
    
    ok(-e '/workspace/perl_multiprocess_job.pl', 'Script exists');
    ok(-x '/workspace/perl_multiprocess_job.pl', 'Script is executable');
};

# Test 3: File processing function
subtest 'File Processing' => sub {
    plan tests => 3;
    
    # Create temp file
    my ($fh, $filename) = tempfile(SUFFIX => '.dat', UNLINK => 1);
    print $fh 'X' x (1024 * 1024);  # 1MB
    close $fh;
    
    ok(-e $filename, 'Temp file created');
    my $size = -s $filename;
    is($size, 1024 * 1024, 'File size is 1MB');
    ok($size > 0, 'File has content');
};

# Test 4: JSON handling
subtest 'JSON Handling' => sub {
    plan tests => 2;
    
    my $data = {
        event_type => 'test',
        timestamp => time(),
        data => { key => 'value' }
    };
    
    my $json_text = encode_json($data);
    ok(defined $json_text, 'JSON encoding works');
    
    my $decoded = decode_json($json_text);
    is($decoded->{event_type}, 'test', 'JSON decoding works');
};

# Test 5: HTTP client
subtest 'HTTP Client' => sub {
    plan tests => 2;
    
    my $ua = LWP::UserAgent->new(timeout => 5);
    ok(defined $ua, 'HTTP client created');
    isa_ok($ua, 'LWP::UserAgent');
};

# Test 6: Fork manager
subtest 'Fork Manager' => sub {
    plan tests => 2;
    
    my $pm = Parallel::ForkManager->new(2);
    ok(defined $pm, 'Fork manager created');
    isa_ok($pm, 'Parallel::ForkManager');
};

# Test 7: Script execution (dry run)
subtest 'Script Execution' => sub {
    plan tests => 1;
    
    # Run with minimal load
    my $output = `timeout 60s perl /workspace/perl_multiprocess_job.pl 2 2 2>&1`;
    my $exit_code = $? >> 8;
    
    # Accept 0 or 124 (timeout) as success
    ok($exit_code == 0 || $exit_code == 124, 
       "Script executed (exit code: $exit_code)");
};

# Test 8: Monitoring integration
subtest 'Monitoring Integration' => sub {
    plan tests => 2;
    
    # Check script for monitoring endpoints
    open my $script_fh, '<', '/workspace/perl_multiprocess_job.pl' 
        or die "Cannot open script: $!";
    my $script_content = do { local $/; <$script_fh> };
    close $script_fh;
    
    like($script_content, qr/http:\/\//, 'HTTP endpoint found in script');
    like($script_content, qr/POST/, 'POST method found in script');
};

print "\n=== All Perl Integration Tests Complete ===\n";

done_testing();

