# Scaffold created by GitHub Co-pilot

import argparse
import tempfile
import os

from eagleeye_cgi import main as eagleeye_cgi_main


def main():
    parser = argparse.ArgumentParser(description="EagleEye CLI frontend")
    parser.add_argument("data_file", help="Spectra data file(s) (MGF or .dta format)")
    parser.add_argument("library_file", nargs="?", default=None, help="Optional background library (MGF format)")
    parser.add_argument("-s", type=int, help="Preset filtering mode")
    parser.add_argument("-p", type=float, help="Precursor mass tolerance")
    parser.add_argument("-f", type=float, help="Fragment mass tolerance")
    parser.add_argument("-a", type=float, help="p-value cutoff")
    parser.add_argument("-n", action="store_true", help="Create non-redundant background library")
    parser.add_argument("-x", type=str, default="", help="Suffix for output files")
    parser.add_argument("-d", type=str, default="", help="Description/comment")
    args = parser.parse_args()

    params = {
        "uploaded_spectra": args.data_file,
        "uploaded_background_library": args.library_file,
        "pmt": args.p,
        "fmt": args.f,
        "smj": args.a,
        "type": "Nonred" if args.n else "Filter",
        "description": args.d,
        "prjpath": os.path.dirname(os.path.abspath(__file__)),
        "suffix": args.x,
    }

    # Save parameters to a temp file (e.g., as JSON)
    with tempfile.NamedTemporaryFile('w', delete=False, suffix=".query") as tmp:
        for k, v in params.items():
            if v is not None:
                tmp.write(f"{k}={v}\n")
        tmp_name = tmp.name

    eagleeye_cgi_main(qfile=tmp_name)

    # Remove temp file
    os.remove(tmp_name)


if __name__ == "__main__":
    main()
