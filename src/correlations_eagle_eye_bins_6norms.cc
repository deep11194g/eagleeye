#include <iostream>
#include <fstream>
#include <math.h>
#include <errno.h>
#include <dirent.h>
#include <stdlib.h>
#include <cstring>

using std::cerr;
using std::cout;
using std::endl;

#include "msfilter.h"

using namespace std;

#define MAX_SPEC_GOOD 20000
#define MAX_SPEC 267000
#define N_SPECTRUM_MASSES 10000

//#define precursor_mass_tolerance 2.5
//#define fragment_mass_tolerance 0.5

double precursor_mass_tolerance, fragment_mass_tolerance;

#define max_intens_factor 0.01

int read_directory(char *directory_name, spectrum **spe)
{

  double a, b;
  int i;

  DIR *pdirspec;
  struct dirent *pentspec;
  ifstream good_spectrum;

  double *mass = new double[N_SPECTRUM_MASSES];
  double *intensity = new double[N_SPECTRUM_MASSES];

  int num_spec = -1;

  char str1[MAX_IDLEN];
  strcpy(str1, directory_name);  strcat(str1, "/");

  char str2[MAX_IDLEN];
  int fname_len, ext_pos;

  pdirspec=opendir(directory_name);
  if (!pdirspec){
    cerr << "opendir() failure; terminating" << endl;
    exit(1);
  }
  errno=0;
  while ((pentspec = readdir(pdirspec)) != NULL){

    // Skip special directory entries
    if (strcmp(pentspec->d_name, ".")==0 || strcmp(pentspec->d_name, "..")==0) continue;

    fname_len = strlen(pentspec->d_name);
    ext_pos = fname_len - 4;
    if (ext_pos < 0) {
      cerr << "readdir() failure: illegal filename: " << pentspec->d_name << endl;
      exit(1);
    }

    // Only process .dta files
    if (strncasecmp(&pentspec->d_name[ext_pos], ".dta", 4) == 0) {

      num_spec++;

      double precursor_mass;
      int charge;
      strcpy(str2, str1);
      strcat(str2, pentspec->d_name);
      // Check that full spectrum filename is not too long
      if (strlen(str2) >= MAX_IDLEN) {
        cerr << "Fatal error: spectrum file name too long: " << str2 << endl;
        exit(1);
      }
      good_spectrum.open(str2);
      if(!good_spectrum) {
        cerr << "open() failure: could not open file: " << str2 << endl;
        exit(1);
      }
      i = 0;
      while(good_spectrum >> a >> b) {
        if (i == 0) { precursor_mass = a; charge = int(b); }
        else {
          mass[i-1] = a;
          intensity[i-1] = b;
        }
        i++;
      }
      good_spectrum.close();

      // create a class spectrum object

      spe[num_spec] = new spectrum(precursor_mass, charge, str2, i-1, mass, intensity);

    }

  }
  if (errno){
    cerr << "readdir() failure; terminating\n";
    exit(1);
  }

  closedir(pdirspec);

  return(num_spec+1);

}

int read_mgf(char *file_name, spectrum **spe)
{
  double a, b;  int i;

  double precursor_mass;  int charge;  string spectrum_name;

  double *mass, *intensity;

  int num_spec = 0;

  ifstream fin(file_name);
  if(fin.is_open() == false) {
    cerr << "Can't open file. Bye.\n";
    exit(EXIT_FAILURE);
  }
  string line;
  while(getline(fin,line)) {
    if (line.find("TITLE") < string::npos) {
      mass = new double[N_SPECTRUM_MASSES];
      intensity = new double[N_SPECTRUM_MASSES];
      i = 0;
      string pm(line,line.find("=")+1,line.length());
      spectrum_name = pm;
    }
    if (line.find("CHARGE") < string::npos) {
      string pm(line,line.find("=")+1,line.length()-1);
      charge = atoi(pm.c_str());
    }
    if (line.find("PEPMASS") < string::npos) {
      string pm(line,line.find("=")+1,line.length()-1);
      precursor_mass = charge * atof( pm.c_str() ) - 1.008 * ( charge - 1 );
    }
    if (line.find(" ") < string::npos && line.find("IONS")==string::npos) {
      string pm(line,0,line.find(" "));
      mass[i] = atof(pm.c_str());
      string pm1(line,line.find(" "),line.length());
      intensity[i] = atof(pm1.c_str());
      i++;
    }
    if (line.find("END") < string::npos) {
      spe[num_spec] = new spectrum(precursor_mass, charge, spectrum_name.c_str(), i, mass, intensity);
      num_spec++;
      delete [] mass;
      delete [] intensity;
    }
  }

  return num_spec;

}

void quicksort(double *dummy, int *rbi, int lo, int hi)
{
  int i=lo, j=hi, dummy_id, dummy_in, k;
  double h;
  double x=dummy[(lo+hi)/2];

  //  partition
  do
    {
      while (dummy[i]<x) i++;
      while (dummy[j]>x) j--;
      if (i<=j)
        {
	  h=dummy[i]; dummy[i]=dummy[j]; dummy[j]=h;
	  k=rbi[j]; rbi[j]=rbi[i]; rbi[i]=k;
	  i++; j--;
        }
    } while (i<=j);

  //  recursion
  if (lo<j) quicksort(dummy, rbi, lo, j);
  if (i<hi) quicksort(dummy, rbi, i, hi);

}



double spearman_rank(double *inte1, double *inte2, int length)
{

  double *dummy1 = new double[length];
  int *dummy_rank1 = new int[length];
  int *rank1 = new int[length];
  for (int i=0; i<length; i++) {
    dummy1[i]=inte1[i];
    dummy_rank1[i]=i;
  }

  quicksort(dummy1, dummy_rank1, 0, length-1);
  for (int i=0; i<length; i++) {
    rank1[dummy_rank1[i]]=length-i;
  }


  double *dummy2 = new double[length];
  int *dummy_rank2 = new int[length];
  int *rank2 = new int[length];
  for (int i=0; i<length; i++) {
    dummy2[i]=inte2[i];
    dummy_rank2[i]=i;
  }

  quicksort(dummy2, dummy_rank2, 0, length-1);
  for (int i=0; i<length; i++) {
    rank2[dummy_rank2[i]]=length-i;
  }


  double rho = 0.;
  for (int i = 0; i < length; i++) {
    rho += (rank1[i]-rank2[i])*(rank1[i]-rank2[i]);
  }
  rho = rho*6/length/(length*length-1);
  rho = 1.-rho;

  for (int i = 0; i < length; i++) {
      cout << inte1[i] << "\t" << rank1[i] << "\t" << dummy1[i] << "\t"
	   << inte2[i] << "\t" << rank2[i] << "\t" << dummy2[i] << "\t" << endl;
    }

  delete dummy1;
  delete dummy_rank1;
  delete rank1;
  delete dummy2;
  delete dummy_rank2;
  delete rank2;

  return rho;

}

void eagles_eye(spectrum *s1, spectrum *s2, double eye_catching_height, double &nesovpal, double &total_intens)
{
  // get the number of coinciding peaks
  int n=0, lastj=0, high_good_peaks=0, high_bckgr_peaks=0;
  double smallest_mass=10000.0, largest_mass=0.0;
  double sum_intensity_total_bin1 = 0.0, sum_intensity_total_sq = 0.0, sum_intensity_total_log = 0.0;
  double sum_intensity_sovpal_bin1 = 0.0, sum_intensity_sovpal_sq = 0.0, sum_intensity_sovpal_log = 0.0;
  double sum_intensity_total_bin2 = 0.0;
  double sum_intensity_sovpal_bin2 = 0.0;
  double sum_intensity_total_bin3 = 0.0;
  double sum_intensity_sovpal_bin3 = 0.0;

  int high_unmatched_peak = 0;

  for (int i = 0; i<s1->spectrum_length; i++) {
    if(s1->intensity[i]>s1->max_intensity*eye_catching_height
       && s1->mass[i]<0.900001*s1->precursor_mass/s1->charge ) {
      high_good_peaks++;
      sum_intensity_total_bin1 += s1->intensity[i]/s1->max_intensity;

      if (s1->intensity[i]>s1->max_intensity*0.5) high_unmatched_peak = 1;

      double m2, i2 = 0., m1 = s1->mass[i], i1 = s1->intensity[i];
      for (int j = lastj; s2->mass[j] < m1+fragment_mass_tolerance, s2->mass[j]>0.01, j<s2->spectrum_length; j++) {
	if (s2->intensity[j] > s2->max_intensity*eye_catching_height) {
	  if (s2->mass[j] > m1 - fragment_mass_tolerance && s2->mass[j] < m1 + fragment_mass_tolerance) {
	    lastj = j;
	    n++;
	    sum_intensity_sovpal_bin1 += s1->intensity[i]/s1->max_intensity;

	    if (s2->intensity[j] > s2->max_intensity*eye_catching_height*2) high_unmatched_peak = 0;

	    break;
	  }
	}
      }
    }
  }

  for (int i = 0; i < s1->spectrum_length; i++) {
    if(s1->intensity[i]>s1->max_intensity*eye_catching_height
       &&s1->mass[i]>0.9*s1->precursor_mass/s1->charge
       && s1->mass[i]<1.000001*s1->precursor_mass/s1->charge) {
      high_good_peaks++;

      sum_intensity_total_bin2 += s1->intensity[i]/s1->max_intensity;

      if (s1->intensity[i]>s1->max_intensity*0.5) high_unmatched_peak = 1;

      double m2, i2 = 0., m1 = s1->mass[i], i1 = s1->intensity[i];
      for (int j = lastj; s2->mass[j] < m1+fragment_mass_tolerance, s2->mass[j]>0.01, j<s2->spectrum_length; j++) {
	if (s2->intensity[j] > s2->max_intensity*eye_catching_height) {
	  if (s2->mass[j] > m1 - fragment_mass_tolerance && s2->mass[j] < m1 + fragment_mass_tolerance) {
	    lastj = j;
	    n++;
	    sum_intensity_sovpal_bin2 += s1->intensity[i]/s1->max_intensity;

	    if (s2->intensity[j] > s2->max_intensity*eye_catching_height*2) high_unmatched_peak = 0;

	    break;
	  }
	}
      }
    }
  }

  for (int i = 0; i < s1->spectrum_length; i++) {
    if(s1->intensity[i]>s1->max_intensity*eye_catching_height && s1->mass[i]>(s1->precursor_mass/s1->charge)) {
      high_good_peaks++;

      sum_intensity_total_bin3 += s1->intensity[i]/s1->max_intensity;

      if (s1->intensity[i]>s1->max_intensity*0.5) high_unmatched_peak = 1;

      double m2, i2 = 0., m1 = s1->mass[i], i1 = s1->intensity[i];
      for (int j = lastj; s2->mass[j] < m1+fragment_mass_tolerance, s2->mass[j]>0.01, j<s2->spectrum_length; j++) {
	if (s2->intensity[j] > s2->max_intensity*eye_catching_height) {
	  if (s2->mass[j] > m1 - fragment_mass_tolerance && s2->mass[j] < m1 + fragment_mass_tolerance) {
	    lastj = j;
	    n++;
	    sum_intensity_sovpal_bin3 += s1->intensity[i]/s1->max_intensity;

	    if (s2->intensity[j] > s2->max_intensity*eye_catching_height*2) high_unmatched_peak = 0;

	    break;
	  }
	}
      }
    }
  }

  nesovpal = 2.*(sum_intensity_total_bin1 - sum_intensity_sovpal_bin1)+1.*(sum_intensity_total_bin2 - sum_intensity_sovpal_bin2)
    +4.*(sum_intensity_total_bin3 - sum_intensity_sovpal_bin3);
  total_intens = 2*sum_intensity_total_bin1 + sum_intensity_total_bin2 + 4.*sum_intensity_total_bin3;

}

main(int argc, char *argv[])
{

  spectrum **spe_good = new(spectrum *[MAX_SPEC_GOOD]);
  spectrum **spe_bckg = new(spectrum *[MAX_SPEC]);

  int num_good_spec, num_bckg_spec;
  string madrebuena(argv[1]);
  if ( madrebuena.find("mgf") < string::npos ) {
    num_good_spec = read_mgf(argv[1], spe_good);
  }
  else {
    num_good_spec = read_directory(argv[1], spe_good);
  }

  string madremala(argv[2]);
  if ( madremala.find("mgf") < string::npos ) {
    num_bckg_spec = read_mgf(argv[2], spe_bckg);
  }
  else {
    num_bckg_spec = read_directory(argv[2], spe_bckg);
  }

  double eye_catching_height = atof(argv[3]);
  precursor_mass_tolerance = atof(argv[4]);
  fragment_mass_tolerance = atof(argv[5]);

  int found_match, tot_matches = 0;
  for (int i = 0; i < num_good_spec; i++) {
    found_match = 0;

    double tot_intens1, nesovpal1, tot_intens2, nesovpal2;

    for (int j = 0; j < num_bckg_spec; j++) {
      if (fabs(spe_good[i]->precursor_mass-spe_bckg[j]->precursor_mass)<precursor_mass_tolerance
          && spe_good[i]->charge == spe_bckg[j]->charge) {

	eagles_eye(spe_good[i],spe_bckg[j],eye_catching_height, nesovpal1, tot_intens1);
	eagles_eye(spe_bckg[j],spe_good[i],eye_catching_height, nesovpal2, tot_intens2);

	//printf("%-s\t%-s\t", spe_good[i]->scan_id, spe_bckg[j]->scan_id);
	cout << spe_good[i]->scan_id << "\t" << spe_bckg[j]->scan_id << "\t";
	cout << spe_good[i]->precursor_mass << "\t" << spe_bckg[j]->precursor_mass << "\t";
	cout << spe_good[i]->charge << "\t" << spe_bckg[j]->charge << "\t";
	cout << (nesovpal1+nesovpal2)/(tot_intens1+tot_intens2) << endl;
	found_match = 1;
      }
    }
    if (found_match) tot_matches++;
    else {
      //printf("%-s\tno_bckgr_spectra_with_same_precursor_mass\t\t\t", spe_good[i]->scan_id);
    	cout << spe_good[i]->scan_id << "\t" << "no_bckgr_spectra_with_same_precursor_mass" << "\t\t\t";
	    cout << spe_good[i]->precursor_mass << "\t" << "not_found" << "\t\t";
	    cout << spe_good[i]->charge << "\t" << "not_found" << "\t\t";
      cout << "1.00\n";
    }
  }

  return EXIT_SUCCESS;

}
