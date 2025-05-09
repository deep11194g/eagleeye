#!/usr/bin/perl

use Getopt::Std;
use CGI;
use File::Temp qw( tempfile );
use File::Spec::Functions qw( rel2abs );
use File::Basename;

my %opt;
usage() unless getopts('ns:p:f:a:d:x:', \%opt);

sub usage {
  print STDERR<<'EOT';
EagleEye v1.66                                          [11/14/2008]
Copyright (C) 2008 by Ivan Adzhubey <iadzhubey@rics.bwh.harvard.edu>
Usage: run_eagleeye.pl [options] <DATA_FILE> [<LIBRARY_FILE>]
  where arguments are:
    <DATA_FILE>         (compressed) file or archive containing spectra
                        data file(s) in MGF or .dta format
    <LIBRARY_FILE>      optional user-supplied background library
                        in MGF format
  and options are:
    -s<N>               apply filtering presets: N=1 for LTQ Orbitrap,
                        N=2 for LTQ linear ion trap; see EagleEye web
                        page for details
    -p<X>               precursor mass tolerance, Da
    -f<Y>               fragment mass tolerance, Da
    -a<Z>               p-value cutoff
    -n                  create non-redundant background library
    -x<SUFFUX>          append SUFFIX string to output filenames
    -d<STRING>          description/comment
EOT
exit -1;
}

my $MYPATH = dirname(rel2abs($0));

my $PRESETS = $opt{'s'} || 0;
warn("Incorrect presets code specified: $PRESETS\n\n"), usage() if $PRESETS && !($PRESETS == 1 || $PRESETS == 2);
warn("Input filename missing\n\n"), usage() if @ARGV < 1;
warn("Incorrect number of arguments\n\n"), usage() if @ARGV > 2;
warn("Either a preset (-s) or a set of -p/-f/-a options should be specified\n\n"), usage()
  unless $PRESETS || (exists $opt{'p'} && exists $opt{'f'} && exists $opt{'a'});

my ($pmt, $fmt, $smj);
if      ($PRESETS == 1) {
  ($pmt, $fmt, $smj) = (0.01, 0.6, 0.01 );
} elsif ($PRESETS == 2) {
  ($pmt, $fmt, $smj) = (2.00, 0.6, 0.005);
}

$pmt = $opt{'p'} if exists $opt{'p'};
$fmt = $opt{'f'} if exists $opt{'f'};
$smj = $opt{'a'} if exists $opt{'a'};

my $desc = $opt{'d'} || '';
my $type = $opt{'n'} ? 'Nonred' : 'Filter';

my $SUFFIX = $opt{'x'} || '';

my $DATAFILE = shift;
my $LIBFILE  = shift if @ARGV;

my @PARAMS = qw(
  uploaded_spectra uploaded_background_library
  pmt fmt smj type description prjpath suffix
);
my %PARAMS = (
  uploaded_spectra => $DATAFILE,
  uploaded_background_library => $LIBFILE,
  pmt => $pmt,
  fmt => $fmt,
  smj => $smj,
  type => $type,
  description => $desc,
  prjpath => $MYPATH,
  suffix => $SUFFIX
);

my $query = new CGI;
foreach $name (@PARAMS) {
  $query->param($name, $PARAMS{$name}) if exists $PARAMS{$name} && defined $PARAMS{$name};
}

# Save query data to a temporary file
my ($fh, $fname) = tempfile('XXXXXXXX', SUFFIX=>'.query', UNLINK=>1);
$query->save($fh);

system $MYPATH . '/eagleeye.cgi', $fname;

if ($? == -1) {
  print "Failed to execute eagleeye.cgi: $!\n";
} elsif ($? & 127) {
  printf "eagleeye.cgi died with signal %d\n", ($? & 127);
}

close($fh);
