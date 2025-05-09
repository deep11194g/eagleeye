#include <stdlib.h>
#include <iostream>

#include "msfilter.h"

spectrum::spectrum(double pm, int ch, char *si,
			  int sl, double *m, double *ints)
{
  precursor_mass = pm;
  charge = ch;
  spectrum_length = sl;
  max_intensity = 0.0;
  mass = new double[spectrum_length];
  intensity = new double[spectrum_length];
  sorted = 0;
  for ( int i = 0; i < MAX_IDLEN; i++ ) { scan_id[i] = si[i]; }
  for ( int i = 0; i < sl; i++ ) {
    mass[i] = m[i];
    intensity[i] = ints[i];
    if (intensity[i] > max_intensity) { max_intensity = intensity[i]; }
  }
}

spectrum::spectrum(double pm, int ch, const char *si,
			  int sl, double *m, double *ints)
{
  precursor_mass = pm;
  charge = ch;
  spectrum_length = sl;
  max_intensity = 0.0;
  mass = new double[spectrum_length];
  intensity = new double[spectrum_length];
  sorted = 0;
  for ( int i = 0; i < MAX_IDLEN; i++ ) { scan_id[i] = si[i]; }
  for ( int i = 0; i < sl; i++ ) {
    mass[i] = m[i];
    intensity[i] = ints[i];
    if (intensity[i] > max_intensity) { max_intensity = intensity[i]; }
  }
}

spectrum::~spectrum()
{
  delete mass;
  delete intensity;
  if(sorted) {
    delete sorted_intensity;
    delete rank_by_intensity;
  }
}

void spectrum::sort_intensities()
{
  int *dummy_rank = new int[spectrum_length];
  sorted_intensity = new double[spectrum_length];
  rank_by_intensity = new int[spectrum_length];
  for (int i=0; i<spectrum_length; i++) {
    sorted_intensity[i] = intensity[i];
    dummy_rank[i]=i;
  }
  quicksort(sorted_intensity, dummy_rank, 0, spectrum_length-1);
  for (int i=0; i<spectrum_length; i++) {
    rank_by_intensity[dummy_rank[i]]=spectrum_length-i;
  }
  sorted = 1;
}

void spectrum::quicksort(double *dummy, int *rbi, int lo, int hi)
{
//  lo is the lower index, hi is the upper index
//  of the region of array intens that is to be sorted

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
