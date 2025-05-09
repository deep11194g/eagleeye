#!/usr/bin/perl

my ($cmd, $rs);
my @tempfiles;

my ($yourtable2, $smj, $MSDATAtemporarydir2, $MSDATAnonred_lib) = @ARGV;

open(FN1, $yourtable2) or die "Can't open input file: $yourtable2\n";
my %copied;
while (chomp($line = <FN1>)) {
  my @arr = split(/\s+/, $line);
  my @tmparr1 = split(/\//, $arr[0]);
  my @tmparr2 = split(/\//, $arr[1]);

  if ($arr[@arr-1] < 0) {$pvalue=0;}
  else {$pvalue = 1 - exp(-($arr[@arr-1]/0.832697)**8.87259);}

  $lr = join(" ", $tmparr1[@tmparr1-1], $tmparr2[@tmparr2-1]);
  $rl = join(" ", $tmparr2[@tmparr2-1], $tmparr1[@tmparr1-1]);

  $PV{$lr} = $pvalue;
  $PV{$rl} = $pvalue;

  if ($tmparr1[@tmparr1-1] eq $tmparr2[@tmparr2-1]) {
    $PV{$lr} = 1.0;
    $PV{$rl} = 1.0;
  }

  $pvz=$pvalue;
}
close(FN1);

my @dir_contents = glob "$MSDATAtemporarydir2/*.dta";
die "No data (.dta) files in directory: $MSDATAtemporarydir2\n" unless scalar @dir_contents;

# Now loop through array and print file names
my $num_non_red_files = 0;
foreach $file (@dir_contents) {
  unless ($copied{$file} == 1) {
    my $net_pohojego = 1;
    for (my $i=0; $i<$num_non_red_files; $i++) {
      $lr = join(" ", $file, $list_of_files[$i]);
      $rl = join(" ", $list_of_files[$i], $file);
      if (($PV{$lr} > 0 || $PV{$rl} > 0) && ($PV{$lr} < $smj || $PV{$rl} < $smj))
        { $net_pohojego = 0; }
    }
    if ($net_pohojego == 1) {
      $cmd = "cp -f $file $MSDATAnonred_lib/";
      die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
      $copied{$file} = 1;
      $list_of_files[$num_non_red_files++] = $file;
    }
  }
}
