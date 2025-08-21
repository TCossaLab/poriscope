

#ifndef UTILS_H_INCLUDED
#define UTILS_H_INCLUDED
#include<stdio.h>
#include<stdlib.h>
#include<inttypes.h>
#include<stdint.h>
#include<math.h>
#include<string.h>
#include<time.h>
#include<limits.h>
#define EPS 1e-10
#define STRLENGTH 1024
#define HEAD -1000
#define NUMTYPES 20

#define SECONDS_TO_MICROSECONDS 1e6
#define AMPS_TO_PICOAMPS 1e12
#define FRACTION_TO_PERCENTAGE 100

#define CUSUM 0
#define STEPRESPONSE 1
#define BADBASELINE 2
#define TOOLONG 3
#define TOOSHORT 4
#define BADLEVELS 5
#define BADTRACE 6
#define BADPADDING 7
#define FITSTEP 8
#define OVERFITTED 9
#define STEPZERO 10
#define STEPDEGEN 11
#define MAXITERS 12
#define FFAILED 13
#define OFILED 14
#define PFAILED 15
#define MEMORY 16
#define INVALUD 17
#define INTERRUPT 18
#define STEPNAN 19

#define CHIMERA 0
#define BINARY 1
#define IGOROPT 2
#define EONEDAT 3

#define SIGNED_INT_TYPE 0
#define UNSIGNED_INT_TYPE 1
#define FLOAT_TYPE 2

#define A_to_pA 1e12

#define ERR_BITS 1
#define ERR_MEM 2
#define ERR_FILE 3
#define ERR_DATA 4
#define ERR_STRING 5

#define BESSEL_EVENT_FILTER 1
#define WAVELET_EVENT_FILTER 2

//#define DEBUG
extern int errorcode;
union bitmaskunion
{
    uint16_t bitmask16;
    uint32_t bitmask32;
    uint64_t bitmask64;
};


struct Binary_Decoder_Struct
{
    int64_t header_bytes;
    double samplingfreq;
    int n_arrays;
    int array_index;
    size_t data_size;
    int data_type;
    int data_order;
    union bitmaskunion bitmask;
    double scale;
    double offset;
};
typedef struct Binary_Decoder_Struct binary_decoder;


struct Duration_Struct
{
    double duration;
    struct Duration_Struct *next;
};
typedef struct Duration_Struct duration_struct;


struct Time_Struct
{
     double t75;
     double t25;
};
typedef struct Time_Struct timestruct;

struct Signal_Struct
{
    double *paddedsignal;
    double *signal;
    void *rawsignal;
};
typedef struct Signal_Struct signal_struct;

struct IO_struct
{
    FILE *logfile;
    FILE *events;
    FILE *sublevels;
    FILE *crossings;
    FILE *rate;
    struct Input_File *input;
    FILE *baselinefile;
    binary_decoder *bincfg;
};
typedef struct IO_struct io_struct;

struct Chimera
{
    double samplerate;
    double TIAgain;
    double preADCgain;
    double currentoffset;
    double ADCvref;
    int ADCbits;
};
typedef struct Chimera chimera;


struct Cusumlevel
{
    double current;
    double stdev;
    double maxdeviation;
    int64_t maxdevindex;
    double raw_level_ecd;
    double fitted_level_ecd;
    int64_t length;
    struct Cusumlevel *next;
};
typedef struct Cusumlevel cusumlevel;


struct Baseline_struct
{
    double *histogram;
    double *current;
    int64_t numbins;
    double baseline_min;
    double baseline_max;
    double range;
    double delta;
    double mean;
    double stdev;
    double amplitude;
};
typedef struct Baseline_struct baseline_struct;

struct Event
{
    int64_t index;
    int64_t start;
    int64_t finish;
    int64_t length;
    int type;
    double area;
    double fitted_area;
    double baseline_before;
    double baseline_after;
    double average_blockage;
    double max_blockage;
    int64_t max_length;
    double min_blockage;
    int64_t min_length;
    double *signal;
    double *paddedsignal;
    double *filtered_signal;
    double *rawsignal;
    int64_t padding_before;
    int64_t padding_after;
    int64_t extra_before;
    int64_t extra_after;
    int numlevels;
    double threshold;
    double delta;
    double rc1;
    double rc2;
    double residual;
    double maxdeviation;
    double local_baseline;
    double local_stdev;
    int64_t intracrossings;
    struct Edge *intra_edges;
    struct Edge *first_edge;
    struct Cusumlevel *first_level;
};
typedef struct Event event;

struct Edge
{
    int64_t location;
    int64_t type;
    double local_stdev;
    double local_baseline;
    struct Edge *next;
};
typedef struct Edge edge;

struct Input_File
{
    FILE *data_file;
    char datafilename[STRLENGTH];
    double timestamp;
    int64_t length;
    int64_t offset;
    chimera *daqsetup;
    struct Input_File *next;
};
typedef struct Input_File input_file;

struct Configuration
{
    char filepath[STRLENGTH]; //input file
    char outputfolder[STRLENGTH];
    char eventsfolder[STRLENGTH];
    char eventsfile[STRLENGTH];
    char sublevelsfile[STRLENGTH];
    char crossingsfile[STRLENGTH];
    char ratefile[STRLENGTH];
    char logfile[STRLENGTH];
    char baselinefile[STRLENGTH];

    //file reading parameters
    int64_t start;
    int64_t finish;
    int64_t readlength;
    int64_t fixed_event_length;

    //filter parameters
    int use_data_filter;
    int use_event_filter;
    int wave_levels;
    double data_cutoff;
    double event_cutoff;
    double samplingfreq;
    int64_t data_order; //must be even
    int64_t event_order; //must be even

    //detection parameters
    double threshold;
    double hysteresis;
    int64_t padding_wait;
    int64_t event_minpoints;
    int64_t event_maxpoints;

    double baseline_min;
    double baseline_max;
    int manual_baseline_override;
    double manual_baseline;
    double manual_baseline_std;

    int event_direction;

    double cusum_min_threshold;
    double cusum_max_threshold;
    double cusum_delta;
    double cusum_elasticity;
    double cusum_minstep;
    int64_t subevent_minpoints;
    int64_t max_sublevels;

    double intra_threshold;
    double intra_hysteresis;

    int64_t stepfit_samples;
    int64_t maxiters;
    int attempt_recovery;
    int datatype;
    int current_output_type;
    int skip_fit;

    char wname[STRLENGTH];
    char method[STRLENGTH];
    char ext[STRLENGTH];
    char thresh[STRLENGTH];
    char level[STRLENGTH];
    int levels;
};
typedef struct Configuration configuration;

void fatal(int error);
signal_struct *initialize_signal(configuration *config, int64_t filterpadding, binary_decoder *bincfg);
void free_signal(signal_struct *sig);
void check_bits(void);
FILE *fopen64_and_check(const char *fname, const char *mode, int caller);
void *calloc_and_check(int64_t num, int64_t size, char *msg);
int signum(double num);
double my_min(double a, double b);
double my_max(double a, double b);
int64_t intmin(int64_t a, int64_t b);
int64_t intmax(int64_t a, int64_t b);
double d_abs(double num); //absolute value of a number

double ARL(int64_t length, double sigma, double mun, double h);

int64_t count_edges(edge *head_edge);
edge *initialize_edges(void);
edge *add_edge(edge *current, int64_t location, int type, double stdev, double baseline);
void free_edges(edge *current);

event *initialize_events(void);
event *add_event(event *current, int64_t start, int64_t finish, int64_t index, double local_stdev, double local_baseline);
void free_single_event(event *current);

cusumlevel *add_cusum_level(cusumlevel *lastlevel, double current, int64_t length);
void free_levels(cusumlevel *current);
cusumlevel *initialize_levels(void);

double signal_max(double *signal, int64_t length);
double signal_min(double *signal, int64_t length);
double signal_average(double *signal, int64_t length);
double signal_extreme(double *signal, int64_t length, double sign);
double signal_variance(double *signal, int64_t length);


int64_t get_filesize(input_file *input);
void progressbar(int64_t pos, int64_t finish, const char *msg, double elapsed);



void invert_matrix(double m[3][3], double inverse[3][3]);
baseline_struct *initialize_baseline(configuration *config);
void free_baseline(baseline_struct *baseline);

int64_t locate_min(double *signal, int64_t length);
int64_t locate_max(double *signal, int64_t length);


duration_struct *initialize_durations(void);
duration_struct *add_duration(duration_struct *current, double duration);
void free_durations(duration_struct *current);

input_file *initialize_input_files(int datatype);
input_file *add_input_file(input_file *current, const char *filename, const char *settingsname, int datatype, binary_decoder *bincfg);
void free_input_files(input_file *current);


#endif // UTILS_H_INCLUDED
