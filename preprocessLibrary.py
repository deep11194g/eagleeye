import argparse
import os
from glob import glob


def preprocess_library(library_dir, threshold):
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


def main():
    parser = argparse.ArgumentParser(
        description="Preprocess a user-supplied DTA library directory for EagleEye."
    )
    parser.add_argument(
        "library_dir",
        type=str,
        help="Directory containing .dta files to preprocess"
    )
    parser.add_argument(
        "threshold",
        type=float,
        help="Threshold value for preprocessing"
    )
    args = parser.parse_args()

    preprocess_library(args.library_dir, args.threshold)


if __name__ == "__main__":
    main()
