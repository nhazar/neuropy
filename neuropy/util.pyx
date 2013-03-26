# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
# cython: profile=False

"""Some functions written in Cython for max performance"""

cimport cython
#from cython.parallel import prange#, parallel
import numpy as np
cimport numpy as np
# import_array() is required for access to NumPy's C API, otherwise calls to something
# like `np.PyArray_EMPTY` segfault. See:
# http://docs.scipy.org/doc/numpy/reference/c-api.array.html#importing-the-api
np.import_array()


#import time
'''
cdef extern from "math.h":
    int abs(int x)
    float fabs(float x)
    double ceil(double x) nogil

cdef extern from "limits.h":
    int INT_MAX

cdef extern from "float.h":
    double DBL_MAX
'''
cdef extern from "stdio.h":
    int printf(char *, ...)
'''
cdef extern from "string.h":
    cdef void *memset(void *, int, size_t) nogil # sets n bytes in memory to constant
'''

def xcorr(np.ndarray[np.int64_t, ndim=1, mode='c'] x,
          np.ndarray[np.int64_t, ndim=1, mode='c'] y,
          np.ndarray[np.int64_t, ndim=1, mode='c'] trange):
    """Calculate cross-correlation of timepoints in x with y, constrained to lower
    and upper bounds in trange. Assume timepoints in x and y are sorted"""
    # should assert contig of x and y, this seems to happen automatically though
    cdef long long ntx, nty, loti, dtsi, xti, yti, maxxti, maxyti, t, dt
    cdef long long low = trange[0]
    cdef long long high = trange[1]
    cdef long long DTSALLOCSIZE = 1000000
    ntx = x.shape[0]
    nty = y.shape[0]
    maxxti = ntx - 1
    maxyti = nty - 1
    cdef np.ndarray[np.int64_t, ndim=1] dts = np.zeros(DTSALLOCSIZE, dtype=np.int64)
    cdef long long maxdtsi = dts.shape[0] - 1

    loti = 0
    dtsi = 0
    for xti in range(ntx):
        # t is current timepoint in x to compare to all timepoints in y:
        t = x[xti]
        while y[loti] - t < low: # keep checking lower trange bound
            loti += 1
            if loti > maxyti: # no y timepoints fall within trange of t
                break
        # start collecting dt values:
        if loti > maxyti: # no y timepoints fall within trange of t
            continue # to next xti
        yti = loti
        dt = y[yti] - t
        while dt < high: # keep checking upper trange bound
            if dtsi > maxdtsi:
                # when growing an array, pretty much need to allocate a new one,
                # can't very often do it in place:
                dts = np.resize(dts, (dts.shape[0] + DTSALLOCSIZE,))
                maxdtsi = dts.shape[0] - 1
                printf('resized dts array to %d entries\n', dts.shape[0])
            dts[dtsi] = dt
            #printf('%d ', dtsi)
            dtsi += 1 # inc for next loop iter
            yti += 1
            if yti > maxyti: # don't exceed maxyti when indexing into y
                break
            dt = y[yti] - t # update for next loop iter
    dts = dts[:dtsi] # trim it down
    return dts
