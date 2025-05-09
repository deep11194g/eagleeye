#!/usr/bin/perl

use strict 'refs';
use CGI qw( :standard );
use File::Temp;
use File::Basename;

# Restore query parameters from file
my $QFILE = shift;
open(BLD, $QFILE) or die "Can't open query file: $QFILE\n";
restore_parameters(\*BLD);
close(BLD);

# Set up environment
my $WRK_PATH  = $ENV{'PWD'};
my $PRJ_PATH  = param('prjpath');
my $DATA_PATH = "$PRJ_PATH/data";
my $SUFFIX    = param('suffix');
$SUFFIX = "-$SUFFIX" if length $SUFFIX;

$IONTRAP_LIBRARY = 'redundant-library-1.11v';

# Check if we have spectra file(s) submitted
my $file = param('uploaded_spectra') or die "No spectra file(s) submitted\n";
my $spectra = fileparse($file);

my $DATATEMP = File::Temp->newdir();

my $library = param('uploaded_background_library');
my $request_type = param('type');
my $pmt = param('pmt');
my $fmt = param('fmt');
my $smj = param('smj');
my $request_name;

print "Eagle Eye v1.66\n\n";

my ($cmd, $rs, $mgf_flag, $mgflib_flag);
my @cleanup;  # list of filenames to be removed at the end of processing

# Extract MGF spectra file from the archive if we have archive specification
# submitted, e.g. archive:file
my ($sarc, $sfile) = split /:/, $spectra;
if (defined $sarc && defined $sfile) {
  my $uarc = $sarc;
  my ($arcbase, undef, $arcext) = fileparse($sarc, qw{.zip .tar .tar.gz .tgz});
  if ($arcext eq '.zip') {
    $cmd = "unzip -qq -j -o $uarc $sfile '*/$sfile' 2>&1 1>/dev/null";
  } elsif ($arcext eq '.tar' || $arcext eq '.tar.gz' || $arcext eq '.tgz') {
    my $op = $arcext eq '.tar' ? 'xf' : 'xzf';
    $cmd = "tar $op $uarc " . q{--transform='s,^/\?\([^/]\+/\)*,,' --no-anchored } . $sfile;
  } else {
    die "Unsupported archive type: $sarc\n";
  }
  $rs = `$cmd`;
  die "Failed to extract file '$sfile' from archive: $sarc\n" unless -e $sfile;
  $spectra = $file = $sfile;
  push @cleanup, $sfile;
}

my ($spectra_name, undef) = split /\./, $spectra;
my $numfiles = 0;

# Convert .mgf file to a set of .dta files which are put into data directory,
# optionally uncompressing .mgf file first.
if ($spectra =~ /\.mgf$/i || $spectra =~ /\.mgf\.zip$/i || $spectra =~ /\.mgf\.gz$/i) {
  $mgf_flag = 1;
  my $mgfile = $spectra;
  # Unzip
  if ($spectra =~ /\.zip$/i) {
    $mgfile =~ s/\.zip$//;
    $cmd = "unzip -qq -j -o $file 2>&1 1>/dev/null";
    die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
  # Gunzip
  } elsif ($spectra =~ /\.gz$/i) {
    $mgfile =~ s/\.gz$//;
    $cmd = "gunzip -q -c $file 2>&1 1>$mgfile";
    die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
  # Read uploaded uncompressed file directly from UPLOADS_PATH directory
  } else {
    $mgfile = $file;
  }
  mgf2dta($mgfile, $DATATEMP);
  unless ($mgfile eq $file) {
    unlink $mgfile or die "Failed to remove file: $mgfile\n";
  }
# Unzip/untar uploaded spectra archive with .dta files into data directory
} elsif ($spectra =~ /\.tar\.gz$/i || $spectra =~ /\.tgz$/i) {
  # tar's --transform option attempts to flatten archive contents by extracting
  # all of the files into the top directory (specified by -C option).
  $cmd = "tar --no-same-owner --no-same-permissions --overwrite " .
        "-xzf $file --transform='s,^/\\?\\([^/]\\+/\\)*,,' " .
        "-C $DATATEMP/ 2>&1 1>/dev/null";
  die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
  # Since --transform option still creates (empty) subdirectory(ies)
  # when extracting from archive, we should remove them all.
  # Note: don't forget to quote all backslashes within Perl double-quoted
  # strings with extra ones, i.e. '\\'.
  $cmd = "find $DATATEMP -depth -mindepth 1 -type d " .
          "-execdir rmdir '{}' \\; 2>&1 1>/dev/null";
  die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
# Unzip uploaded spectra archive with .dta files into data directory
} elsif ($spectra =~ /\.zip$/i) {
  $cmd = "unzip -qq -j -o $file -d $DATATEMP/ 2>&1 1>/dev/null";
  die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
} else {
  die "Unsupported file type uploaded: $spectra\n";
}

my @dtafiles = glob "$DATATEMP/*.dta";
die "No data (.dta) files in archive: $spectra\n" unless scalar @dtafiles;

my $LIBTEMP;
# User has submitted a background library to use instead of a standard one
if ($library) {

  print 'Pre-processing user-supplied library...';

  $LIBTEMP = File::Temp->newdir();

  my $libfile = $library;

  # File naming convention for user library data files is as following:
  #   .zip, .tar, .tar.gz, and .tgz archives are assumed to contain
  #   (one or several) spectra dataset(s) in MGF format;
  #
  #   .dta.zip, .dta.tar, .dta.tar.gz, and .dta.tgz archives are
  #   assumed to each contain a single set of spectra files in .dta format,
  #   where each .dta file in the set holds only a SINGLE spectrum; .dta
  #   files with multiple spectra are NOT supported
  #
  #   all other filenames are assumed to be uncompressed files containing a
  #   single dataset in MGF format.
  #
  my ($libname, undef, $libext) = fileparse($library, qw{.zip .tar .tar.gz .tgz});
  my $libformat = $libname =~ /\.dta$/i ? 'dta' : 'mgf';
  $libext = lc($libext) if $libext;

  # Unpack archived .mgf library file and convert it to a set of .dta files
  # which are put into userlib directory.
  if ($libformat eq 'mgf') {
    $mgflib_flag = 1;
    my $mgfile = $library;
    # Read uploaded uncompressed file directly from UPLOADS_PATH directory
    if (!$libext) {
      # Uncompressed MGF file should have extension .mgf
      die "Unspecified or unsupported library format: $library\n"
        unless $libname =~ /\.mgf$/i;
      $mgfile = $libfile;
    # Unzip
    } elsif ($libext eq '.zip') {
      # Find out what file is inside zip archive (since it can have arbitrary name)
      $cmd = "unzip -qql $libfile";
      my @lines = `$cmd`;
      die "Command failed: $cmd\n" unless @lines;
      my @arclist;
      foreach (@lines) {
        chomp;
        s/^\s+//;
        my @a = split /\s+/, $_, 4;
        my $length = $a[0];
        my $name = $a[3];
        push @arclist, scalar fileparse($name)
          if ($name && $length !~ /[^\d]/ && $length > 0);
      }
      die "No files found in library archive: $library\n" unless @arclist;
      die "Multiple files found in library archive: $library\n"
        if scalar(@arclist) > 1;
      $mgfile = $arclist[0];
      # Uncompressed MGF file should have extension .mgf
      die "Unspecified or unsupported library format: $library:$mgfile\n"
        unless $mgfile =~ /\.mgf$/i;
      $cmd = "unzip -qq -j -o $libfile 2>&1 1>/dev/null";
      die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
    # Gunzip
    } elsif ($libext eq '.gz') {
      $mgfile = $libname;
      # Uncompressed MGF file should have extension .mgf
      die "Unspecified or unsupported library format: $library\n"
        unless $mgfile =~ /\.mgf$/i;
      $cmd = "gunzip -q -c $libfile 2>&1 1>$mgfile";
      die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
    # Unsupported library archive
    } else {
      die "Unsupported library archive format: $library\n";
    }
    mgf2dta($mgfile, $LIBTEMP);
    unless ($mgfile eq $libfile) {
      unlink $mgfile or die "Failed to remove file: $mgfile\n";
    }
  # Unpack archived .dat library into userlib directory.
  } elsif ($libformat eq 'dta') {
    # Files in DTA format should be archived
    if (!$libext) {
      die "Library in DTA format should be archived: $library\n";
    } elsif ($libext =~ /^\.(tar|tar\.gz|tgz)$/) {
      $cmd = "tar --no-same-owner --no-same-permissions --overwrite " .
            "-xzf $libfile --transform='s,^/\\?\\([^/]\\+/\\)*,,' " .
            "-C $LIBTEMP/ 2>&1 1>/dev/null";
      die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
      $cmd = "find $LIBTEMP -depth -mindepth 1 -type d " .
            "-execdir rmdir '{}' \\; 2>&1 1>/dev/null";
      die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
    } elsif ($libext eq '.zip') {
      $cmd = "unzip -qq -j -o $libfile " .
            "-d $LIBTEMP/ 2>&1 1>/dev/null";
      die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
    } else {
      die "Unsupported library archive format: $library\n";
    }
  } else {
      die "Unsupported library format: $library\n";
  }

  $numfiles = scalar glob "$LIBTEMP/*.dta";
  die "No data (.dta) files in archive: $library\n" unless $numfiles;

  $cmd = "$PRJ_PATH/preprocessLibrary.pl $LIBTEMP 0.05 2>&1 1>/dev/null";
  die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;

  print " Done.\n";
}

print 'Calculating distances...';

$tmpyt1 = new File::Temp( TEMPLATE => "$WRK_PATH/your1tableXXXXXX" );
$tmpyt2 = new File::Temp( TEMPLATE => "$WRK_PATH/your2tableXXXXXX" );

my $yourtable1 = $tmpyt1->filename;
my $yourtable2 = $tmpyt2->filename;

# Create non-redundant library by filtering submitted spectra against themselves
if($request_type eq 'Nonred') {
  $cmd = "msfilter $DATATEMP $DATATEMP 0.05 $pmt $fmt 2>&1 1>$yourtable1";
  $request_name = 'Create non-redundant library';
} else {
  # User-supplied background library submitted, use it to filter spectra
  if ($library) {
    $cmd = "msfilter $DATATEMP $LIBTEMP 0.05 $pmt $fmt 2>&1 1>$yourtable1";
    $request_name = 'Process spectra with user-supplied Iontrap-type library';
  # No user-supplied libray, use standard Iontrap background library
  } else {
    $cmd = "msfilter $DATATEMP $DATA_PATH/$IONTRAP_LIBRARY 0.05 $pmt $fmt 2>&1 1>$yourtable1";
    $request_name = 'Process spectra with Iontrap background library';
  }
}

die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;

# if ($library) {
#   # Remove unpacked contents of the optional background library
#   $cmd = "/bin/rm -rf $LIBTEMP/ 2>&1 1>/dev/null";
#   die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
# }

print " Done.\n";

print 'Sorting table...';

$cmd = "sort -b -g -k 7,7 $yourtable1 2>&1 1>$yourtable2";
die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;

print " Done.\n";

my ($goodfile, $bgroundfile, $nonredfile, $tablefilename);

# Filtered using either standard built-in or user-supplied library
if ($request_type eq 'Filter') {

  $tablefilename = $spectra_name . $SUFFIX . '-table.csv';
  processtable($yourtable2, $tablefilename, $smj, $spectra_name,
               $numfiles, $mgf_flag);

  # Remove temporary data directory
  #$cmd = "/bin/rm -rf $DATATEMP/ 2>&1 1>/dev/null";
  #die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;

  if ($mgf_flag) {
    $goodfile    = $spectra_name . $SUFFIX . '-good.mgf';
    $bgroundfile = $spectra_name . $SUFFIX . '-background.mgf';
  } else {
    $goodfile    = $spectra_name . $SUFFIX . '-good.zip';
    $bgroundfile = $spectra_name . $SUFFIX . '-background.zip';
  }

# Created non-redundant library
} elsif ($request_type eq 'Nonred') {

  my $NRLIBTEMP = File::Temp->newdir();

  $cmd = "$PRJ_PATH/make_nonredundant.pl $yourtable2 $smj $DATATEMP $NRLIBTEMP 2>&1 1>$yourtable1";
  die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;

  if ($mgf_flag) {
    $nonredfile = $spectra_name . $SUFFIX . '-nonredundant.mgf';
    dta2mgf($NRLIBTEMP, $nonredfile);
  } else {
    $nonredfile = $spectra_name . $SUFFIX . '-nonredundant.zip';
    $cmd = "zip -qr $nonredfile $NRLIBTEMP/ 2>&1 1>/dev/null";
    die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
  }

  # Remove temporary nonredlib
  $cmd = "/bin/rm -rf $NRLIBTEMP/ 2>&1 1>/dev/null";
  die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;

  # Remove temporary data directory
  #$cmd = "/bin/rm -rf $DATATEMP/ 2>&1 1>/dev/null";
  #die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;

# Unsupported request type
} else {
  die "Unsupported request type: $request_type";
}

# Cleanup
my $cnt = unlink @cleanup;
my $filesleft = scalar(@cleanup) - $cnt;
warn "Failed to remove $filesleft of " . scalar(@cleanup) . " temporary files\n"
  if $filesleft;

# Store query parameters in CSV format
my $params_file = $spectra_name . $SUFFIX . '-params.csv';
my $description = param('description') || '';
open(PF, '>', $params_file) or die "Can't create file: $params_file\n";
print PF "Spectra,Library,PMT,FMT,SMJ,RequestType,Description\n";
print PF param('uploaded_spectra'), ",$library,$pmt,$fmt,$smj,$request_type,$description\n";
close(PF);

print
  "\n",
  $description ? "Description: $description\n" : '',
  'Input file: ' . param('uploaded_spectra') . "\n",
  'Job type: ' . $request_name . "\n",
  $request_type eq 'Filter' && $library ? "User-supplied library: $library\n" : '',
  "Precursor mass tolerance: $pmt\n",
  "Fragment mass tolerance: $fmt\n",
  "p-Value cutoff: $smj\n";

if ($request_type eq 'Nonred') {
  print
    "\n",
    "Output files:\n",
    "Parameters: $WRK_PATH/$params_file\n",
    "Non-redundant library: $WRK_PATH/$nonredfile\n";
} else {
  print
    "\n",
    "Output files:\n",
    "Parameters: $WRK_PATH/$params_file\n",
    "Spectra table: $WRK_PATH/$tablefilename\n";
  if (-e $goodfile && -s $goodfile) {
    print "Good spectra: $WRK_PATH/$goodfile\n";
  }
  if (-e $bgroundfile && -s $bgroundfile) {
    print "Background spectra: $WRK_PATH/$bgroundfile\n";
  }
}

print
  "\n",
  'Created: ' . localtime,
  "\n";

#---------Subroutines----------------------------------------------------------#

# Parameters passed:
#   dtapath - path to a directory containing set of .dta files
#             to convert (no trailing slash)
#   mgfname - full filename (including path) of the .mgf file
#
sub dta2mgf {
  my ($dtapath, $mgfname) = @_;
  die "MGF filename missing\n" unless $mgfname;
  open(FOUT, '>', $mgfname) or die "Can't create output file: $mgfname\n";
  # Copy global parameters from the original MGF file, if present
  my $gfile = "$dtapath/globals.meta";
  if (-e $gfile) {
    open(GF, $gfile) or die "Can't open file: $gfile\n";
    while (<GF>) { print FOUT; }
    close(GF);
  }
  foreach $file (glob "$dtapath/*.dta") {
    my $name = fileparse($file);
    open(FIN, '<', $file) or die "Can't open DTA file: $file\n";
      $_ = <FIN>; s/\r\n$/\n/; chomp;
      my ($MH, $Z) = split /\s+/;
      if (defined $MH && defined $Z) {
        print FOUT "BEGIN IONS\n";
        my $MoverZ = sprintf("%.9g", ($MH + ($Z - 1) * 1.007825) / $Z);
        my $title = $name;
        # URL-decode title
        $title =~ s/\%([A-Fa-f0-9]{2})/pack('C', hex($1))/seg;
        # Copy local spectrum parameters from the original MGF file, if present
        my $lfile = $file; $lfile =~ s/\.dta$/.meta/;
        my ($intensity, $extras);
        if (-e $lfile) {
          open(LF, $lfile) or die "Can't open file: $lfile\n";
          while (<LF>) {
            # Put TITLE, CHARGE and PEPMASS parameters in the output file in exactly
            # the same order in which they are present in the local metafile.
            if      (/^\s*TITLE\s*=/) {
              print FOUT "TITLE=$title\n";
              $title = '';
            } elsif (/^\s*CHARGE\s*=/) {
              print FOUT "CHARGE=$Z+\n";
              $Z = '';
            } elsif (/^\s*PEPMASS\s*=\s*([\dEe.+-]+)/) {
              $intensity = $2 if /^\s*PEPMASS\s*=\s*([\dEe.+-]+)\s+([\dEe.+-]+)\s*$/;
              $MoverZ .= " $intensity" if defined $intensity;
              print FOUT "PEPMASS=$MoverZ\n";
              $MoverZ = '';
            } else {
              $extras .= $_;
            }
          }
          close(LF);
        }
        # Put TITLE, CHARGE and PEPMASS parameters (in that order!) in the output
        # file unless they have already been printed out while processing local
        # parameters metafile (above).
        print FOUT "TITLE=$title\n"     if length $title;
        print FOUT "CHARGE=$Z+\n"       if length $Z;
        print FOUT "PEPMASS=$MoverZ\n"  if length $MoverZ;
        print FOUT $extras              if defined $extras;
        while ($line = <FIN>) {
          $line =~ s/\r\n$/\n/; chomp $line;
          if ($line =~ /^\s*[\dEe.+-]+\s+[\dEe.+-]+\s*$/) {
            my ($one, $two) = split(/\s+/, $line);
            print FOUT "$one\t$two\n";
          } else {
            die "Invalid data format in file $name: $line\n";
          }
        }
        print FOUT "END IONS\n\n";
      } else {
        die "Invalid header in file $file: $_\n"
      }
      close(FIN);
  }
  close(FOUT);
}

# Parameters passed:
#   mgfile -  full filename, including optional path, of .mgf file
#             to convert.
#   dtapath - (optional) path where .dta files will be stored;
#             defaults to current directory
#
#   NB: $pepmass_dta = (($pepmass_mgf - 1.00782) * $charge) + 1.00782;
#
sub mgf2dta {
  my ($mgfile, $dtapath) = @_;
  my $mgfname = fileparse($mgfile);
  my $mgfbase = $mgfname; $mgfbase =~ s/\..*$//;
  unless (-e $dtapath && -d $dtapath) {
    mkpath $dtapath or die "Can't create directory: $dtapath\n";
  }
  my $globals  = 1; # Global parameters flag, by default globals are at the top
                    # of mgf file but theoretically can also be inserted between
                    # individual spectra (is this true?)
  my $locals   = 0; # Local parameters flag, local parameters are placed at the top
                    # of each ion section, preceeding all actual spectrum data
  my ($gtitle, $gcharge, $gpepmass); # Global values
  my ($title, $charge, $pepmass);    # Per-ion values
  my ($t, $c, $m);
  my @cc;
  my $lineno = 0;
  my $sbuffer = ''; # Spectrum data buffer, saved as $title.$charge.dta file(s)
  my $gbuffer = ''; # Global MGF parameters, saved as globals.meta file
  my $lbuffer = ''; # Local spectrum parameters, saved as $title.$charge.meta file(s)
  open(FIN, '<', $mgfile) or die "Can't open MGF file: $mgfile\n";
  while (<FIN>) {
    $lineno++;
    s/\r\n$/\n/; chomp;
    # Note, that parameters encountered inside ion spectra data section
    # ($globals=0 && $locals=0) will be skipped silently, although this
    # is a MGF syntax error
    if      (/^TITLE=(.+)/)   {
      if ($globals) { $gtitle = $1; } elsif ($locals) { $title = $1; }
    } elsif (/^CHARGE=(.+)/)  {
      if ($globals) { $gcharge = $1; } elsif ($locals) { $charge = $1; }
    } elsif (/^PEPMASS=(.+)/) {
      if ($globals) { $gpepmass = $1; } elsif ($locals) { $pepmass = $1; }
    } elsif (/^BEGIN IONS/)   {
      $globals = 0; $locals  = 1;
      next; # Skip saving line to a metadata buffer
    } elsif (/^END IONS/)     {
      foreach $chargevar (@cc) {
        my $dta = $t;
        $dta =~ s/\.dta$//;
        $dta =~ s/\.\d$//;
        # URL-encode for safety and filesystem compatibility
        $dta =~ s/([^A-Za-z0-9,._=-])/sprintf("%%%02X", ord($1))/seg;
        my $meta = $dta;
        $dta .= ".$chargevar.dta";
        $dta = $dtapath . '/' . $dta if $dtapath;
        open(FOUT, '>', $dta) or die "Can't create file: $dta\n";
        my $dtamass = sprintf("%.9g", (($m - 1.007825) * $chargevar) + 1.007825);
        print FOUT "$dtamass $chargevar\n";
        print FOUT $sbuffer;
        close(FOUT);
        # Save local spectrum metadata
        if (length $lbuffer) {
          $meta .= ".$chargevar.meta";
          $meta = $dtapath . '/' . $meta if $dtapath;
          open(FOUT, '>', $meta) or die "Can't create file: $meta\n";
          print FOUT $lbuffer;
          close(FOUT);
        }
      }
      $title = $charge = $pepmass = $t = $c = $m = '';
      $sbuffer = $lbuffer = '';
      @cc = ();
      $globals = 1; $locals  = 0;
      next; # Skip saving line to a metadata buffer
    } elsif (/^\s*([\dEe.+-]+)\s+([\dEe.+-]+)\s*$/) {
      my ($one, $two) = ($1, $2);
      die "Illegal global parameter at line $lineno of file: $mgfname\n" if $globals;
      if ($locals) {
        $t = $title || $gtitle;
        $c = $charge || $gcharge;
        $m = $pepmass || $gpepmass;
        # Process all possible combinations of charge values
        if (length $c) {
          @cc = split /\s+and\s+/, $c;
          s/\s*(\d)(\+|-)\s*/\1/ for @cc;
        # Assume "2+ and 3+" if charge specification is missing
        } else {
          @cc = qw{ 2 3 };
        }
        foreach (@cc) {
          die "Ambiguous precursor charge ($c) at line $lineno of file: $mgfname\n"
            unless /^\d$/;
        }
        die "Precursor title missing at line $lineno of file: $mgfname\n" unless $t;
        die "Precursor charge missing at line $lineno of file: $mgfname\n" unless @cc;
        die "Precursor mass missing at line $lineno of file: $mgfname\n" unless $m;
        $locals = 0;  # Finished processing local ion parameters
      }
      $sbuffer .= "$one $two\n";
    } elsif (m|^[#;!/]|) {
      # Skip comments (but save them to a proper metadatda buffer)
      ;
    } elsif (/^\s*$/) {
      next; # Skip saving empty lines to metadata buffers
    } else {
      # Skip all unrecognised lines (but save them to a proper metadatda buffer)
      ;
    }
    if ($globals) { $gbuffer .= "$_\n"; } elsif ($locals) { $lbuffer .= "$_\n"; }
  }
  close(FIN);
  # Save global MGF parameters
  if (length $gbuffer) {
    my $gfile = 'globals.meta';
    $gfile = $dtapath . '/' . $gfile if $dtapath;
    open(FOUT, '>', $gfile) or die "Can't create file: $gfile\n";
    print FOUT $gbuffer;
    close(FOUT);
  }
}

sub processtable {

  my ($INPUT_FILE, $OUTPUT_FILE, $SMJ, $UPLOAD_NAME, $NUMFILES, $MGF_FLAG) = @_;

  my ($cmd, $rs);

  open(FIN, $INPUT_FILE) or die "Can't open input file: $INPUT_FILE\n";
  open(FOUT, '>', $OUTPUT_FILE) or die "Can't open output file: $OUTPUT_FILE\n";
  printf FOUT "%-40s\t%-40s\t%-7s\t%-9s\t%-10s\n",
    '#Query', 'Matched', 'DScore', 'p-Value', 'Prediction';

  my $gd = File::Temp->newdir();
  my $bd = File::Temp->newdir();

  my $libsize = $NUMFILES;

  my %copied;
  my $datapath;
  my $good_flag = 0;    # flags that we have at least one good spectrum
  my $backgr_flag = 0;  # flags that we have at least one background spectrum
  while (<FIN>) {

      chomp; s/^\s+//; s/\s+$//;
      #       0        1       2        3         4          5       6
      # sp_file lib_file sp_mass lib_mass sp_charge lib_charge d_score
      my @arr = split /\s+/;
      my $sfile = $arr[0];
      (undef, $datapath) = fileparse($arr[0]) unless defined $datapath;
      my $lfile = $arr[1];
      $sfile =~ s/\%([A-Fa-f0-9]{2})/pack('C', hex($1))/seg;
      $lfile =~ s/\%([A-Fa-f0-9]{2})/pack('C', hex($1))/seg;
      $sfile = fileparse($sfile);
      $lfile = fileparse($lfile);

      my $ds = $arr[-1];
      if    ($ds == 1.0) { $pvalue = 1; }
      elsif ($ds > 0)    { $pvalue = 1 - exp(-($ds/0.832697)**8.87259); }
      else               { $pvalue = 0; }

      # Spectrum matches background
      if ($pvalue < $SMJ) {
        $backgr_flag = 1;
        unless ($copied{$arr[0]}) {
          $cmd = "cp -f $arr[0] $bd";
          die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
          # Copy spectrum metadata file if present
          my $metafile = $arr[0];
          $metafile .= '.meta' unless $metafile =~ s/\.dta$/.meta/;
          if (-e $metafile) {
            $cmd = "cp -f $metafile $bd";
            die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
          }
          $copied{$arr[0]} = 1;
          printf FOUT "%-40s\t%-40s\t%.4f\t%.6f\t%-10s\n",
            $sfile, $lfile, $ds, $pvalue, 'Background';
        }
        # If there is a corresponding .2/.3 file then it
        # should be unconditionally called background
        my ($spath, $sz) = ($arr[0], $arr[-3]);
        my $dtaflag = 1 if $spath =~ s/\.dta$//;
        $spath =~ s/\.\d$//;
        my $zflip;
        if ($sz && length $spath) {
          if    ($sz == 2) { $zflip = '.3'; }
          elsif ($sz == 3) { $zflip = '.2'; }
          # We only process .2/.3 pairs
          if ($zflip) {
            my $fpath = $spath . $zflip;
            $fpath .= '.dta' if $dtaflag;
            my $ffile = fileparse($fpath);
            if (-e $fpath && !$copied{$fpath}) {
              $cmd = "cp -f $fpath $bd";
              die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
              # Copy spectrum metadata file if present
              my $metafile = $fpath;
              $metafile .= '.meta' unless $metafile =~ s/\.dta$/.meta/;
              if (-e $metafile) {
                $cmd = "cp -f $metafile $bd";
                die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
              }
              $copied{$fpath} = 1;
              printf FOUT "%-40s\t%-40s\t%.4f\t%.6f\t%-10s\n",
                $ffile, $lfile, $ds, $pvalue, 'Background';
            }
          }
        }

      # Good spectrum
      } else {
        $good_flag = 1;
        unless ($copied{$arr[0]}) {
          $cmd = "cp -f $arr[0] $gd";
          die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
          # Copy spectrum metadata file if present
          my $metafile = $arr[0];
          $metafile .= '.meta' unless $metafile =~ s/\.dta$/.meta/;
          if (-e $metafile) {
            $cmd = "cp -f $metafile $gd";
            die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
          }
          $copied{$arr[0]} = 1;
          printf FOUT "%-40s\t%-40s\t%.4f\t%.6f\t%-10s\n",
            $sfile, $lfile, $ds, $pvalue, 'Good';
        }
      }

  }

  close(FOUT);
  close(FIN);

  # Copy global parameters metadata file (if present) to both good
  # and background directories.
  my $globals_file = 'globals.meta';
  $globals_file = $datapath . '/' . $globals_file if length $datapath;
  if (-e $globals_file && -s $globals_file) {
    $cmd = "cp -f $globals_file $gd";
    die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
    $cmd = "cp -f $globals_file $bd";
    die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
  }

  my ($gf, $bf);
  if ($MGF_FLAG) {
    $gf = $UPLOAD_NAME . $SUFFIX . '-good.mgf';
    $bf = $UPLOAD_NAME . $SUFFIX . '-background.mgf';
    dta2mgf($gd, $gf) if $good_flag;
    dta2mgf($bd, $bf) if $backgr_flag;
  } else {
    $gf = $UPLOAD_NAME . $SUFFIX . '-good.zip';
    $bf = $UPLOAD_NAME . $SUFFIX . '-background.zip';
    if ($good_flag) {
      $cmd = "zip -qr $gf $gd 2>&1 1>/dev/null";
      die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
    }
    if ($backgr_flag) {
      $cmd = "zip -qr $bf $bd 2>&1 1>/dev/null";
      die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
    }
  }

}
