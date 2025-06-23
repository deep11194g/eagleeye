# Scaffold created by GitHub Co-pilot

import os
from glob import glob


def main(library_dir: str, threshold: float) -> None:
    """
    Preprocess a user-supplied DTA library directory for EagleEye.

    :param library_dir: Directory containing .dta files to preprocess
    :param threshold: Threshold value for preprocessing
    """
    dta_files = glob(os.path.join(library_dir, "*.dta"))
    for f in dta_files:
        if os.path.isfile(f):
            numlines = 0
            maxpeak = 0
            theline = []
            peak = []
            # Read all lines and find max peak
            with open(f, "r") as fin:
                for line in fin:
                    line = line.strip()
                    theline.append(line)
                    parts = line.split()
                    if len(parts) == 2:
                        one, two = parts
                        try:
                            peak_val = float(two)
                        except ValueError:
                            peak_val = 0.0
                    else:
                        peak_val = 0.0
                    peak.append(peak_val)
                    if numlines > 0 and peak_val > maxpeak:
                        maxpeak = peak_val
                    numlines += 1
            # Prepare new file name (add 'm' at the start of the filename)
            arr21 = f.split(os.sep)
            arr21[-1] = 'm' + arr21[-1]
            f1 = os.sep.join(arr21)
            # Write filtered peaks to the new file
            with open(f1, "w") as fout:
                if theline:
                    print(theline[0], file=fout)
                for i in range(1, numlines):
                    if peak[i] > maxpeak * threshold:
                        print(theline[i], file=fout)
            # Replace original file with new file
            os.replace(f1, f)
