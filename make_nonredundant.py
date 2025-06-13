import argparse
import math
import os
import shutil
from glob import glob
from typing import Dict, List


def compute_pvalue(score: float) -> float:
    if score < 0:
        return 0.0
    return 1 - math.exp(- (score / 0.832697) ** 8.87259)


def parse_table(table_path: str) -> Dict[str, float]:
    PV: Dict[str, float] = {}
    with open(table_path, "r") as fin:
        for line in fin:
            arr = line.strip().split()
            fileA = os.path.basename(arr[0])
            fileB = os.path.basename(arr[1])
            try:
                score = float(arr[-1])
            except Exception:
                score = -1.0
            pvalue = compute_pvalue(score)
            lr = f"{fileA} {fileB}"
            rl = f"{fileB} {fileA}"
            PV[lr] = pvalue
            PV[rl] = pvalue
            if fileA == fileB:
                PV[lr] = 1.0
                PV[rl] = 1.0
    return PV


def select_nonredundant_files(
        dta_files: List[str],
        PV: Dict[str, float],
        smj: float,
        output_dir: str
) -> None:
    copied: Dict[str, int] = {}
    list_of_files: List[str] = []
    num_non_red_files = 0

    for file in dta_files:
        if copied.get(file, 0) == 1:
            continue
        net_pohojego = True
        for i in range(num_non_red_files):
            f1 = os.path.basename(file)
            f2 = os.path.basename(list_of_files[i])
            lr = f"{f1} {f2}"
            rl = f"{f2} {f1}"
            if ((PV.get(lr, 0) > 0 or PV.get(rl, 0) > 0) and
                    (PV.get(lr, 0) < smj or PV.get(rl, 0) < smj)):
                net_pohojego = False
                break
        if net_pohojego:
            try:
                shutil.copy(file, output_dir)
            except Exception as e:
                raise RuntimeError(f"Copy failed: {file} to {output_dir}: {str(e)}")
            copied[file] = 1
            list_of_files.append(file)
            num_non_red_files += 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a non-redundant library from a table and DTA directory."
    )
    parser.add_argument(
        "yourtable2",
        type=str,
        help="Input table file (yourtable2)"
    )
    parser.add_argument(
        "smj",
        type=float,
        help="Score cutoff threshold (smj)"
    )
    parser.add_argument(
        "msdata_temp_dir",
        type=str,
        help="Directory with input DTA files"
    )
    parser.add_argument(
        "msdata_nonred_lib",
        type=str,
        help="Output directory for non-redundant DTA files"
    )
    args = parser.parse_args()

    PV = parse_table(args.yourtable2)

    dta_files = glob(os.path.join(args.msdata_temp_dir, "*.dta"))
    if not dta_files:
        raise FileNotFoundError(f"No data (.dta) files in directory: {args.msdata_temp_dir}")

    if not os.path.exists(args.msdata_nonred_lib):
        os.makedirs(args.msdata_nonred_lib)

    select_nonredundant_files(
        dta_files=dta_files,
        PV=PV,
        smj=args.smj,
        output_dir=args.msdata_nonred_lib
    )


if __name__ == "__main__":
    main()
