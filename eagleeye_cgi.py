# Scaffold created by GitHub Co-pilot

import os
import shutil
import tempfile
import subprocess
import csv
import glob
from datetime import datetime

from preprocessLibrary import main as preprocessLibrary_main
from make_nonredundant import main as make_nonredundant_main


def read_params(qfile: str) -> dict:
    """
    Reads query parameters from a file (key=value per line).
    """
    params = {}
    with open(qfile) as f:
        for line in f:
            line = line.strip()
            if not line or '=' not in line:
                continue
            k, v = line.split('=', 1)
            params[k] = v
    return params


def mgf2dta(mgfile: str, dtapath: str) -> None:
    """
    Converts an MGF file to DTA files in the specified directory.
    Each ion is written as a single .dta file, with associated meta info.
    """
    os.makedirs(dtapath, exist_ok=True)
    gtitle = gcharge = gpepmass = ''
    title = charge = pepmass = ''
    t = c = m = None
    cc = []
    sbuffer = ''
    gbuffer = ''
    lbuffer = ''
    globals_flag = True
    locals_flag = False
    mgfname = os.path.basename(mgfile)
    with open(mgfile, 'r') as fin:
        for line in fin:
            line = line.rstrip('\r\n')
            if line.startswith('TITLE='):
                if globals_flag:
                    gtitle = line[6:]
                elif locals_flag:
                    title = line[6:]
            elif line.startswith('CHARGE='):
                if globals_flag:
                    gcharge = line[7:]
                elif locals_flag:
                    charge = line[7:]
            elif line.startswith('PEPMASS='):
                if globals_flag:
                    gpepmass = line[8:]
                elif locals_flag:
                    pepmass = line[8:]
            elif line.startswith('BEGIN IONS'):
                globals_flag = False
                locals_flag = True
                continue
            elif line.startswith('END IONS'):
                # Write DTA file(s) for all charge states
                if c:
                    cc = [x.replace('+', '').replace('-', '').strip() for x in c.split('and')]
                else:
                    cc = ['2', '3']
                for chargevar in cc:
                    dta = t or ''
                    dta = dta.replace('.dta', '').rsplit('.', 1)[0] if '.dta' in dta else dta
                    # URL encode (simple, for safety)
                    dta = ''.join(['%%%02X' % ord(ch) if not ch.isalnum() and ch not in ',._-=' else ch for ch in dta])
                    meta = dta
                    dta_file = os.path.join(dtapath, f"{dta}.{chargevar}.dta")
                    dtamass = float(m) if m else 0.0
                    dtamass = ((dtamass - 1.007825) * float(chargevar)) + 1.007825
                    with open(dta_file, 'w') as f_out:
                        f_out.write(f"{dtamass} {chargevar}\n")
                        f_out.write(sbuffer)
                    # Write local spectrum metadata
                    if lbuffer:
                        meta_file = os.path.join(dtapath, f"{meta}.{chargevar}.meta")
                        with open(meta_file, 'w') as f_meta:
                            f_meta.write(lbuffer)
                # Reset for next ion
                title = charge = pepmass = t = c = m = None
                sbuffer = lbuffer = ''
                cc = []
                globals_flag = True
                locals_flag = False
                continue
            elif line and all(
                    x.replace('.', '', 1).replace('E', '', 1).replace('+', '', 1).replace('-', '', 1).isdigit() for x in
                    line.split()):
                # peak data line
                if globals_flag:
                    raise Exception(f"Illegal global parameter in file: {mgfname}")
                if locals_flag:
                    t = title or gtitle
                    c = charge or gcharge
                    m = pepmass or gpepmass
                    if not t or not c or not m:
                        raise Exception("Missing precursor info in mgf2dta")
                    locals_flag = False
                sbuffer += line + '\n'
            if globals_flag:
                gbuffer += line + '\n'
            elif locals_flag:
                lbuffer += line + '\n'
    # Save global MGF parameters
    if gbuffer:
        gfile = os.path.join(dtapath, 'globals.meta')
        with open(gfile, 'w') as fout:
            fout.write(gbuffer)


def dta2mgf(dtapath: str, mgfname: str) -> None:
    """
    Converts a directory of DTA files to an MGF file.
    Each DTA file becomes an IONS block in the MGF.
    """
    with open(mgfname, 'w') as fout:
        # Copy global parameters if present
        gfile = os.path.join(dtapath, 'globals.meta')
        if os.path.exists(gfile):
            with open(gfile, 'r') as gf:
                fout.write(gf.read())
        for file in sorted(glob.glob(os.path.join(dtapath, '*.dta'))):
            name = os.path.basename(file)
            with open(file, 'r') as fin:
                header = fin.readline().strip()
                if not header:
                    continue
                MH, Z = header.split()
                MH = float(MH)
                Z = int(Z)
                fout.write("BEGIN IONS\n")
                MoverZ = (MH + (Z - 1) * 1.007825) / Z
                title = name
                # Simple URL decode (for coverage)
                import re
                title = re.sub(r'%([A-Fa-f0-9]{2})', lambda m: chr(int(m.group(1), 16)), title)
                # Copy local meta if present
                lfile = file[:-4] + '.meta'
                intensity = None
                extras = ''
                if os.path.exists(lfile):
                    with open(lfile, 'r') as lf:
                        for line in lf:
                            if line.strip().startswith('TITLE='):
                                fout.write(f"TITLE={title}\n")
                                title = ''
                            elif line.strip().startswith('CHARGE='):
                                fout.write(f"CHARGE={Z}+\n")
                                Z = ''
                            elif line.strip().startswith('PEPMASS='):
                                parts = line.strip().split('=')
                                if len(parts) > 1:
                                    vals = parts[1].split()
                                    if len(vals) > 1:
                                        intensity = vals[1]
                                if intensity:
                                    fout.write(f"PEPMASS={MoverZ} {intensity}\n")
                                else:
                                    fout.write(f"PEPMASS={MoverZ}\n")
                                MoverZ = ''
                            else:
                                extras += line
                if title:
                    fout.write(f"TITLE={title}\n")
                if Z:
                    fout.write(f"CHARGE={Z}+\n")
                if MoverZ != '':
                    fout.write(f"PEPMASS={MoverZ}\n")
                if extras:
                    fout.write(extras)
                for line in fin:
                    line = line.strip()
                    if line and all(
                            x.replace('.', '', 1).replace('E', '', 1).replace('+', '', 1).replace('-', '', 1).isdigit()
                            for x in line.split()):
                        one, two = line.split()
                        fout.write(f"{one}\t{two}\n")
                    else:
                        raise Exception(f"Invalid data format in file {name}: {line}")
                fout.write("END IONS\n\n")


def processtable(INPUT_FILE: str, OUTPUT_FILE: str, SMJ: float, UPLOAD_NAME: str,
                 NUMFILES: int, MGF_FLAG: bool, SUFFIX: str) -> None:
    """
    Processes the filtered table, classifies spectra as 'Good' or 'Background',
    copies DTA/meta files to temporary dirs, and outputs a summary table (CSV).
    """
    import math
    gd = tempfile.mkdtemp()
    bd = tempfile.mkdtemp()
    copied = {}
    datapath = None
    good_flag = False
    backgr_flag = False

    with open(INPUT_FILE, 'r') as fin, open(OUTPUT_FILE, 'w', newline='') as fout:
        fout.write("{:<40}\t{:<40}\t{:7}\t{:9}\t{:10}\n".format(
            '#Query', 'Matched', 'DScore', 'p-Value', 'Prediction'
        ))
        for line in fin:
            arr = line.strip().split()
            if len(arr) < 7:
                continue
            sfile, lfile, *_, ds = arr
            if not datapath:
                datapath = os.path.dirname(sfile)
            import re
            # URL decode
            sfile = re.sub(r'%([A-Fa-f0-9]{2})', lambda m: chr(int(m.group(1), 16)), os.path.basename(sfile))
            lfile = re.sub(r'%([A-Fa-f0-9]{2})', lambda m: chr(int(m.group(1), 16)), os.path.basename(lfile))
            ds = float(ds)
            if ds == 1.0:
                pvalue = 1
            elif ds > 0:
                pvalue = 1 - math.exp(-(ds / 0.832697) ** 8.87259)
            else:
                pvalue = 0
            if pvalue < SMJ:
                backgr_flag = True
                if not copied.get(sfile, False):
                    shutil.copy(arr[0], bd)
                    metafile = arr[0][:-4] + '.meta' if arr[0].endswith('.dta') else arr[0] + '.meta'
                    if os.path.exists(metafile):
                        shutil.copy(metafile, bd)
                    copied[sfile] = True
                    fout.write("{:<40}\t{:<40}\t{:.4f}\t{:.6f}\t{:10}\n".format(
                        sfile, lfile, ds, pvalue, 'Background'))
            else:
                good_flag = True
                if not copied.get(sfile, False):
                    shutil.copy(arr[0], gd)
                    metafile = arr[0][:-4] + '.meta' if arr[0].endswith('.dta') else arr[0] + '.meta'
                    if os.path.exists(metafile):
                        shutil.copy(metafile, gd)
                    copied[sfile] = True
                    fout.write("{:<40}\t{:<40}\t{:.4f}\t{:.6f}\t{:10}\n".format(
                        sfile, lfile, ds, pvalue, 'Good'))

    # Copy global meta to good/backgr if present
    globals_file = os.path.join(datapath, 'globals.meta') if datapath else None
    if globals_file and os.path.exists(globals_file) and os.path.getsize(globals_file) > 0:
        shutil.copy(globals_file, gd)
        shutil.copy(globals_file, bd)

    if MGF_FLAG:
        gf = f"{UPLOAD_NAME}{SUFFIX}-good.mgf"
        bf = f"{UPLOAD_NAME}{SUFFIX}-background.mgf"
        if good_flag:
            dta2mgf(gd, gf)
        if backgr_flag:
            dta2mgf(bd, bf)
    else:
        gf = f"{UPLOAD_NAME}{SUFFIX}-good.zip"
        bf = f"{UPLOAD_NAME}{SUFFIX}-background.zip"
        if good_flag:
            shutil.make_archive(gf.replace('.zip', ''), 'zip', gd)
        if backgr_flag:
            shutil.make_archive(bf.replace('.zip', ''), 'zip', bd)

    shutil.rmtree(gd)
    shutil.rmtree(bd)


def main(qfile: str):
    params = read_params(qfile)

    WRK_PATH = os.environ.get('PWD', os.getcwd())
    PRJ_PATH = params.get('prjpath', WRK_PATH)
    DATA_PATH = os.path.join(PRJ_PATH, 'data')
    SUFFIX = params.get('suffix', '')
    SUFFIX = f'-{SUFFIX}' if SUFFIX else ''
    IONTRAP_LIBRARY = 'redundant-library-1.11v'

    file = params.get('uploaded_spectra')
    if not file:
        raise Exception("No spectra file(s) submitted")
    spectra = os.path.basename(file)

    DATATEMP = tempfile.mkdtemp()
    cleanup = []

    library = params.get('uploaded_background_library')
    request_type = params.get('type')
    pmt = params.get('pmt')
    fmt = params.get('fmt')
    smj = float(params.get('smj', 0.05))
    request_name = None
    mgf_flag = False
    mgflib_flag = False
    rs = None

    print("Eagle Eye v1.66\n")

    # Archive extraction
    if ':' in spectra:
        sarc, sfile = spectra.split(':', 1)
        arcbase, arcext = os.path.splitext(sarc)
        if arcext == '.zip':
            cmd = f"unzip -qq -j -o {sarc} {sfile} '*/{sfile}'"
        elif arcext in ('.tar', '.tar.gz', '.tgz'):
            op = 'xf' if arcext == '.tar' else 'xzf'
            cmd = f"tar {op} {sarc} --transform='s,^/\\?([^/]+/)*,,' --no-anchored {sfile}"
        else:
            raise Exception(f"Unsupported archive type: {sarc}")
        subprocess.run(cmd, shell=True, check=True)
        if not os.path.exists(sfile):
            raise Exception(f"Failed to extract file '{sfile}' from archive: {sarc}")
        spectra = file = sfile
        cleanup.append(sfile)

    spectra_name = spectra.split('.')[0]
    numfiles = 0

    # Convert MGF to DTA or extract DTA files
    if spectra.lower().endswith(('.mgf', '.mgf.zip', '.mgf.gz')):
        mgf_flag = True
        mgfile = spectra
        if spectra.lower().endswith('.zip'):
            mgfile = mgfile[:-4]
            cmd = f"unzip -qq -j -o {file}"
            subprocess.run(cmd, shell=True, check=True)
        elif spectra.lower().endswith('.gz'):
            mgfile = mgfile[:-3]
            cmd = f"gunzip -q -c {file} > {mgfile}"
            subprocess.run(cmd, shell=True, check=True)
        else:
            mgfile = file
        mgf2dta(mgfile, DATATEMP)
        if mgfile != file:
            os.remove(mgfile)
    elif spectra.lower().endswith(('.tar.gz', '.tgz')):
        cmd = f"tar --no-same-owner --no-same-permissions --overwrite -xzf {file} --transform='s,^/\\?([^/]+/)*,,' -C {DATATEMP}/"
        subprocess.run(cmd, shell=True, check=True)
        cmd = f"find {DATATEMP} -depth -mindepth 1 -type d -execdir rmdir '{{}}' \\;"
        subprocess.run(cmd, shell=True, check=True)
    elif spectra.lower().endswith('.zip'):
        cmd = f"unzip -qq -j -o {file} -d {DATATEMP}/"
        subprocess.run(cmd, shell=True, check=True)
    else:
        raise Exception(f"Unsupported file type uploaded: {spectra}")

    dtafiles = glob.glob(os.path.join(DATATEMP, "*.dta"))
    if not dtafiles:
        raise Exception(f"No data (.dta) files in archive: {spectra}")

    LIBTEMP = None
    if library:
        print('Pre-processing user-supplied library...')
        LIBTEMP = tempfile.mkdtemp()
        libfile = library

        libname, libext = os.path.splitext(os.path.basename(library))
        libformat = 'dta' if libname.lower().endswith('.dta') else 'mgf'
        libext = libext.lower()
        if libformat == 'mgf':
            mgflib_flag = True
            mgfile = library
            if not libext:
                if not libname.lower().endswith('.mgf'):
                    raise Exception(f"Unspecified or unsupported library format: {library}")
                mgfile = libfile
            elif libext == '.zip':
                cmd = f"unzip -qql {libfile}"
                lines = subprocess.check_output(cmd, shell=True).decode().splitlines()
                arclist = []
                for l in lines:
                    a = l.strip().split(None, 3)
                    if len(a) < 4:
                        continue
                    length, name = a[0], a[3]
                    if name and length.isdigit() and int(length) > 0:
                        arclist.append(os.path.basename(name))
                if not arclist:
                    raise Exception(f"No files found in library archive: {library}")
                if len(arclist) > 1:
                    raise Exception(f"Multiple files found in library archive: {library}")
                mgfile = arclist[0]
                if not mgfile.lower().endswith('.mgf'):
                    raise Exception(f"Unspecified or unsupported library format: {library}:{mgfile}")
                cmd = f"unzip -qq -j -o {libfile}"
                subprocess.run(cmd, shell=True, check=True)
            elif libext == '.gz':
                mgfile = libname
                if not mgfile.lower().endswith('.mgf'):
                    raise Exception(f"Unspecified or unsupported library format: {library}")
                cmd = f"gunzip -q -c {libfile} > {mgfile}"
                subprocess.run(cmd, shell=True, check=True)
            else:
                raise Exception(f"Unsupported library archive format: {library}")
            mgf2dta(mgfile, LIBTEMP)
            if mgfile != libfile:
                os.remove(mgfile)
        elif libformat == 'dta':
            if not libext:
                raise Exception(f"Library in DTA format should be archived: {library}")
            elif libext in ('.tar', '.tar.gz', '.tgz'):
                cmd = f"tar --no-same-owner --no-same-permissions --overwrite -xzf {libfile} --transform='s,^/\\?([^/]+/)*,,' -C {LIBTEMP}/"
                subprocess.run(cmd, shell=True, check=True)
                cmd = f"find {LIBTEMP} -depth -mindepth 1 -type d -execdir rmdir '{{}}' \\;"
                subprocess.run(cmd, shell=True, check=True)
            elif libext == '.zip':
                cmd = f"unzip -qq -j -o {libfile} -d {LIBTEMP}/"
                subprocess.run(cmd, shell=True, check=True)
            else:
                raise Exception(f"Unsupported library archive format: {library}")
        else:
            raise Exception(f"Unsupported library format: {library}")

        numfiles = len(glob.glob(os.path.join(LIBTEMP, "*.dta")))
        if not numfiles:
            raise Exception(f"No data (.dta) files in archive: {library}")

        preprocessLibrary_main(library_dir=LIBTEMP, threshold=0.05)

        print(" Done.")

    print('Calculating distances...')

    tmpyt1 = tempfile.NamedTemporaryFile(prefix=f"{WRK_PATH}/your1table", delete=False)
    tmpyt2 = tempfile.NamedTemporaryFile(prefix=f"{WRK_PATH}/your2table", delete=False)
    yourtable1 = tmpyt1.name
    yourtable2 = tmpyt2.name
    tmpyt1.close()
    tmpyt2.close()

    # Main computation
    if request_type == 'Nonred':
        cmd = f"msfilter {DATATEMP} {DATATEMP} 0.05 {pmt} {fmt} > {yourtable1}"
        request_name = 'Create non-redundant library'
    else:
        if library:
            cmd = f"msfilter {DATATEMP} {LIBTEMP} 0.05 {pmt} {fmt} > {yourtable1}"
            request_name = 'Process spectra with user-supplied Iontrap-type library'
        else:
            cmd = f"msfilter {DATATEMP} {os.path.join(DATA_PATH, IONTRAP_LIBRARY)} 0.05 {pmt} {fmt} > {yourtable1}"
            request_name = 'Process spectra with Iontrap background library'
    subprocess.run(cmd, shell=True, check=True)
    print(" Done.")

    print('Sorting table...')
    cmd = f"sort -b -g -k 7,7 {yourtable1} > {yourtable2}"
    subprocess.run(cmd, shell=True, check=True)
    print(" Done.")

    goodfile = bgroundfile = nonredfile = tablefilename = None

    if request_type == 'Filter':
        tablefilename = f"{spectra_name}{SUFFIX}-table.csv"
        processtable(yourtable2, tablefilename, smj, spectra_name, numfiles, mgf_flag, SUFFIX)
        if mgf_flag:
            goodfile = f"{spectra_name}{SUFFIX}-good.mgf"
            bgroundfile = f"{spectra_name}{SUFFIX}-background.mgf"
        else:
            goodfile = f"{spectra_name}{SUFFIX}-good.zip"
            bgroundfile = f"{spectra_name}{SUFFIX}-background.zip"
    elif request_type == 'Nonred':
        NRLIBTEMP = tempfile.mkdtemp()

        cmd = f"{PRJ_PATH}/make_nonredundant.py {yourtable2} {smj} {DATATEMP} {NRLIBTEMP} > {yourtable1}"
        subprocess.run(cmd, shell=True, check=True)

        make_nonredundant_main(yourtable2=yourtable2,
                               smj=smj,
                               msdata_temp_dir=DATATEMP,
                               msdata_nonred_lib=NRLIBTEMP)

        if mgf_flag:
            nonredfile = f"{spectra_name}{SUFFIX}-nonredundant.mgf"
            dta2mgf(NRLIBTEMP, nonredfile)
        else:
            nonredfile = f"{spectra_name}{SUFFIX}-nonredundant.zip"
            cmd = f"zip -qr {nonredfile} {NRLIBTEMP}/"
            subprocess.run(cmd, shell=True, check=True)
        shutil.rmtree(NRLIBTEMP)
    else:
        raise Exception(f"Unsupported request type: {request_type}")

    # Cleanup
    for f in cleanup:
        try:
            os.remove(f)
        except Exception:
            pass

    # Store query parameters in CSV format
    params_file = f"{spectra_name}{SUFFIX}-params.csv"
    description = params.get('description', '')
    with open(params_file, 'w', newline='') as pf:
        writer = csv.writer(pf)
        writer.writerow(["Spectra", "Library", "PMT", "FMT", "SMJ", "RequestType", "Description"])
        writer.writerow([params.get('uploaded_spectra', ''), library, pmt, fmt, smj, request_type, description])

    # Output summary
    print()
    if description:
        print(f"Description: {description}")
    print(f"Input file: {params.get('uploaded_spectra', '')}")
    print(f"Job type: {request_name}")
    if request_type == 'Filter' and library:
        print(f"User-supplied library: {library}")
    print(f"Precursor mass tolerance: {pmt}")
    print(f"Fragment mass tolerance: {fmt}")
    print(f"p-Value cutoff: {smj}")

    if request_type == 'Nonred':
        print("\nOutput files:")
        print(f"Parameters: {WRK_PATH}/{params_file}")
        print(f"Non-redundant library: {WRK_PATH}/{nonredfile}")
    else:
        print("\nOutput files:")
        print(f"Parameters: {WRK_PATH}/{params_file}")
        print(f"Spectra table: {WRK_PATH}/{tablefilename}")
        if goodfile and os.path.exists(goodfile) and os.path.getsize(goodfile) > 0:
            print(f"Good spectra: {WRK_PATH}/{goodfile}")
        if bgroundfile and os.path.exists(bgroundfile) and os.path.getsize(bgroundfile) > 0:
            print(f"Background spectra: {WRK_PATH}/{bgroundfile}")

    print("\nCreated:", datetime.now().strftime("%c"))
