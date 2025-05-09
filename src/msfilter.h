#define MAX_IDLEN 2048

#ifndef SPECTRUM_H
#define SPECTRUM_H

class spectrum
{

 public:

  spectrum(double pm, int ch, char* id, int l, double* m, double* i);
  spectrum(double pm, int ch, const char* id, int l, double* m, double* i);
  ~spectrum();

  double precursor_mass, max_intensity;
  int charge, spectrum_length, sorted;
  char scan_id[MAX_IDLEN];

  double *mass, *intensity, *sorted_intensity;
  int *rank_by_intensity;

  void sort_intensities();
  void quicksort(double *, int *, int lo, int hi);

};

#endif  // SPECTRUM_H
