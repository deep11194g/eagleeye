#!/usr/bin/perl

foreach $f (<$ARGV[0]/*.dta>) {
  if (-f $f) {
    $numfiles++;
    $numlines = 0;
    $maxpeak = 0;
    open(F, $f) or die "Can't open file: $f";
    while (chomp($line = <F>)) {
        $theline[$numlines] = $line;
        ($one, $two) = split(/\s+/, $line);
        $peak[$numlines] = $two;
        if ($numlines > 0 && $two > $maxpeak) { $maxpeak = $two; }
        $numlines++;
    }
    @arr21 = split(/\//, $f);
    $arr21[@arr21-1] = join('', 'm', $arr21[@arr21-1]);
    $f1 = join("/", @arr21);
    open(F1, ">$f1") or die "Can't create file: $f1";
    print F1 $theline[0], "\n";
    for ($i=1; $i<$numlines; $i++) {
        if ($peak[$i] > $maxpeak*$ARGV[1]) { print F1 $theline[$i], "\n"; }
    }
    my $cmd = "mv -f $f1 $f";
    die "Command failed: $cmd\n$rs\n" if $rs = `$cmd`;
  }
}
