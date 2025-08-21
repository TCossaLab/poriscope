// # MIT License
// #
// # Copyright (c) 2025 TCossaLab
// #
// # Permission is hereby granted, free of charge, to any person obtaining a copy
// # of this software and associated documentation files (the "Software"), to deal
// # in the Software without restriction, including without limitation the rights
// # to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// # copies of the Software, and to permit persons to whom the Software is
// # furnished to do so, subject to the following conditions:
// #
// # The above copyright notice and this permission notice shall be included in all
// # copies or substantial portions of the Software.
// #
// # THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// # IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// # FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// # AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// # LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// # OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// # SOFTWARE.
// #
// # Contributors:
// # Kyle Briggs

#include"wavelet_filter.h"


void filter_signal_wt(double *signal, int64_t length, const char *wname)
{
    wdenoise_object obj;
	double *filtered_signal;
	filtered_signal = (double*)malloc(sizeof(double)* length);
	
	char *method = "dwt"; // dwt, swt or modwt - modwt works only with modwtshrink. The other two methods work with visushrink and sureshrink
	char *ext = "sym"; // sym and per work with dwt. swt and modwt only use per extension when called through denoise.
	// You can use sy extension if you directly call modwtshrink with cmethod set to fft. See modwtdenoisetest.c file
	char *thresh = "soft"; // soft or hard
	char *level = "all"; // noise estimation at "first" or "all" levels. modwt only has the option of "all"
    //printf("-->%d<--",levels);

    int filt_len = filtlength(wname);
    int levels = (int) (log((double)length / ((double)filt_len - 1.0)) / log(2.0));

    obj = wdenoise_init(length, levels, wname); //Length, Nb. of levels, Wavelet Name

    //
    //TODO: make tthe 4 a parameter (levels). 2 seems better for most applications.
    setWDenoiseMethod(obj, "sureshrink");
    setWDenoiseWTMethod(obj, method); //method
    setWDenoiseWTExtension(obj,ext); //extension
    setWDenoiseParameters(obj,thresh, level); //thresh, level
    wdenoise(obj, signal, filtered_signal);
    memcpy(signal, filtered_signal, length*sizeof(double));
	wdenoise_free(obj);
	free(filtered_signal);
}


