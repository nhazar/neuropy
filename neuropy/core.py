"""Miscellaneous functions and classes"""

from __future__ import division

import os
import sys
import time
import types
import __main__
import struct
import re
import random
import math
import datetime

from copy import copy
from pprint import pprint
printraw = sys.stdout.write # useful for raw printing

from PyQt4 import QtGui
from PyQt4.QtGui import QPixmap, QImage, QPalette, QColor
from PyQt4.QtCore import Qt, QSize

import numpy as np
# make overflow, underflow, div by zero, and invalid all raise errors
# this really should be the default in numpy...
np.seterr(all='raise', under='ignore') # raise all except float underflow
import scipy.signal
from scipy.special import cbrt # real cube root
import scipy.stats

import matplotlib as mpl
import matplotlib.cm
import pylab as pl
from pylab import get_current_fig_manager as gcfm
from matplotlib.collections import LineCollection

import pyximport
pyximport.install(build_in_temp=False, inplace=True)
import util # .pyx file

import filter
from colour import CLUSTERCOLOURRGBDICT

TAB = '    ' # 4 spaces
EPOCH = datetime.datetime(1899, 12, 30, 0, 0, 0) # epoch for datetime stamps in .ptcs


class dictattr(dict):
    """Dictionary with attribute access. Copied from dimstim.Core"""
    def __init__(self, *args, **kwargs):
        super(dictattr, self).__init__(*args, **kwargs)
        for k, v in kwargs.iteritems():
            # call our own __setitem__ so we get keys as attribs even on kwarg init:
            self.__setitem__(k, v)
    
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError, '%r object has no attribute %r' % ('dictattr', key)
    
    def __setattr__(self, key, val):
        self[key] = val

    def __getitem__(self, key):
        """On KeyError, see if converting the key from an int to a 1 or 2 digit str
        works instead"""        
        try:
            return super(dictattr, self).__getitem__(key)
        except KeyError, e: # try converting key to str of up to 2 digits in length
            for ndigits in [1, 2]:
                try:
                    #print('key: %r' % key)
                    #print('ndigits: %d' % ndigits)
                    key = pad0s(key, ndigits=ndigits)
                    #print('padded key: %r' % key)
                except ValueError:
                    raise e
                try:
                    return super(dictattr, self).__getitem__(key)
                except KeyError:
                    pass
            raise e
                
    def __setitem__(self, key, val):
        super(dictattr, self).__setitem__(key, val)
        # key isn't a number or a string starting with a number:
        if key.__class__ == str and not key[0].isdigit():
            key = key.replace(' ', '_') # get rid of any spaces
            self.__dict__[key] = val # make the key show up as an attrib upon dir()


class PTCSHeader(object):
    """Polytrode clustered spikes file header"""
    def __init__(self):
        self.VER2FUNC = {1: self.read_ver_1, 2: self.read_ver_2} # call the appropriate method

    def read(self, f):
        """Read in format version, followed by rest according to verison

        formatversion: int64 (currently version 1)
        """
        self.FORMATVERSION = int(np.fromfile(f, dtype=np.int64, count=1)) # formatversion
        self.VER2FUNC[self.FORMATVERSION](f) # call the appropriate method
        
    def read_ver_1(self, f):
        """Read in header of .ptcs file version 1. For text fields, rstrip both null
        and space bytes, since NVS generated .ptcs files mix the two for padding.

        ndescrbytes: uint64 (nbytes, keep as multiple of 8 for nice alignment)
        descr: ndescrbytes of ASCII text
            (padded with null bytes if needed for 8 byte alignment)

        nneurons: uint64 (number of neurons)
        nspikes: uint64 (total number of spikes)
        nsamplebytes: uint64 (number of bytes per template waveform sample)
        samplerate: uint64 (Hz)

        npttypebytes: uint64 (nbytes, keep as multiple of 8 for nice alignment)
        pttype: npttypebytes of ASCII text
            (padded with null bytes if needed for 8 byte alignment)
        nptchans: uint64 (total num chans in polytrode)
        chanpos: nptchans * 2 * float64
            (array of (x, y) positions, in um, relative to top of polytrode,
             indexed by 0-based channel IDs)
        nsrcfnamebytes: uint64 (nbytes, keep as multiple of 8 for nice alignment)
        srcfname: nsrcfnamebytes of ASCII text
            (source file name, probably .srf, padded with null bytes if needed for
             8 byte alignment)
        datetime: float64
            (absolute datetime corresponding to t=0 us timestamp, stored as days since
             epoch: December 30, 1899 at 00:00)
        ndatetimestrbytes: uint64 
        datetimestr: ndatetimestrbytes of ASCII text
            (human readable string representation of datetime, preferrably ISO 8601,
             padded with null bytes if needed for 8 byte alignment)
        """
        self.ndescrbytes = int(np.fromfile(f, dtype=np.uint64, count=1)) # ndescrbytes
        self.descr = f.read(self.ndescrbytes).rstrip('\0 ') # descr
        try:
            self.descr = eval(self.descr) # should come out as a dict
        except: pass
        
        self.nneurons = int(np.fromfile(f, dtype=np.uint64, count=1)) # nneurons
        self.nspikes = int(np.fromfile(f, dtype=np.uint64, count=1)) # nspikes
        self.nsamplebytes = int(np.fromfile(f, dtype=np.uint64, count=1)) # nsamplebytes
        self.samplerate = int(np.fromfile(f, dtype=np.uint64, count=1)) # samplerate

        self.npttypebytes = int(np.fromfile(f, dtype=np.uint64, count=1)) # npttypebytes
        self.pttype = f.read(self.npttypebytes).rstrip('\0 ') # pttype
        self.nptchans = int(np.fromfile(f, dtype=np.uint64, count=1)) # nptchans
        self.chanpos = np.fromfile(f, dtype=np.float64, count=self.nptchans*2) # chanpos
        self.chanpos.shape = self.nptchans, 2 # reshape into rows of (x, y) coords
        self.nsrcfnamebytes = int(np.fromfile(f, dtype=np.uint64, count=1)) # nsrcfnamebytes
        self.srcfname = f.read(self.nsrcfnamebytes).rstrip('\0 ') # srcfname
        # maybe convert this to a proper Python datetime object in the Neuron:
        self.datetime = float(np.fromfile(f, dtype=np.float64, count=1)) # datetime (days)
        self.ndatetimestrbytes = int(np.fromfile(f, dtype=np.uint64, count=1)) # ndatetimestrbytes
        self.datetimestr = f.read(self.ndatetimestrbytes).rstrip('\0 ') # datetimestr

    def read_ver_2(self, f):
        """Same as version 1. NVS created some version 1 files incorrectly, and
        incremented to version 2 for the correctly exported ones"""
        return self.read_ver_1(f)


class PTCSNeuronRecord(object):
    """Polytrode clustered spikes file neuron record"""
    def __init__(self, header):
        self.VER2FUNC = {1: self.read_ver_1, 2:self.read_ver_2} # call the appropriate method
        self.header = header
        nsamplebytes = self.header.nsamplebytes
        self.wavedtype = {2: np.float16, 4: np.float32, 8: np.float64}[nsamplebytes]

    def read(self, f):
        self.VER2FUNC[self.header.FORMATVERSION](f) # call the appropriate method
        
    def read_ver_1(self, f):
        """Read in neuron record of .ptcs file version 1

        nid: int64 (signed neuron id, could be -ve, could be non-contiguous with previous)
        ndescrbytes: uint64 (nbytes, keep as multiple of 8 for nice alignment, defaults to 0)
        descr: ndescrbytes of ASCII text
            (padded with null bytes if needed for 8 byte alignment)
        clusterscore: float64
        xpos: float64 (um)
        ypos: float64 (um)
        zpos: float64 (um) (defaults to NaN)
        nchans: uint64 (num chans in template waveforms)
        chanids: nchans * uint64 (0 based IDs of channels in template waveforms)
        maxchanid: uint64 (0 based ID of max channel in template waveforms)
        nt: uint64 (num timepoints per template waveform channel)
        nwavedatabytes: uint64 (nbytes, keep as multiple of 8 for nice alignment)
        wavedata: nwavedatabytes of nsamplebytes sized floats
            (template waveform data, laid out as nchans * nt, in uV,
             padded with null bytes if needed for 8 byte alignment)
        nwavestdbytes: uint64 (nbytes, keep as multiple of 8 for nice alignment)
        wavestd: nwavestdbytes of nsamplebytes sized floats
            (template waveform standard deviation, laid out as nchans * nt, in uV,
             padded with null bytes if needed for 8 byte alignment)
        nspikes: uint64 (number of spikes in this neuron)
        spike timestamps: nspikes * uint64 (us, should be sorted)
        """
        self.nid = int(np.fromfile(f, dtype=np.int64, count=1)) # nid
        self.ndescrbytes = int(np.fromfile(f, dtype=np.uint64, count=1)) # ndescrbytes
        self.descr = f.read(self.ndescrbytes).rstrip('\0 ') # descr
        if self.descr:
            try:
                self.descr = eval(self.descr) # might be a dict
            except: pass
        self.clusterscore = float(np.fromfile(f, dtype=np.float64, count=1)) # clusterscore
        self.xpos = float(np.fromfile(f, dtype=np.float64, count=1)) # xpos (um)
        self.ypos = float(np.fromfile(f, dtype=np.float64, count=1)) # ypos (um)
        self.zpos = float(np.fromfile(f, dtype=np.float64, count=1)) # zpos (um)
        self.nchans = int(np.fromfile(f, dtype=np.uint64, count=1)) # nchans
        self.chans = np.fromfile(f, dtype=np.uint64, count=self.nchans) # chanids
        self.maxchan = int(np.fromfile(f, dtype=np.uint64, count=1)) # maxchanid
        self.nt = int(np.fromfile(f, dtype=np.uint64, count=1)) # nt
        self.nwavedatabytes, self.wavedata = self.read_wave(f)
        self.nwavestdbytes, self.wavestd = self.read_wave(f)
        self.nspikes = int(np.fromfile(f, dtype=np.uint64, count=1)) # nspikes
        # spike timestamps (us):
        self.spikes = np.fromfile(f, dtype=np.uint64, count=self.nspikes)
        # convert from unsigned to signed int for calculating intervals:
        self.spikes = np.asarray(self.spikes, dtype=np.int64)

    def read_wave(self, f):
        """Read wavedata/wavestd bytes"""
        # nwavedata/nwavestd bytes, padded:
        nbytes = int(np.fromfile(f, dtype=np.uint64, count=1))
        fp = f.tell()
        count = nbytes // self.header.nsamplebytes # trunc to ignore any pad bytes
        X = np.fromfile(f, dtype=self.wavedtype, count=count) # wavedata/wavestd (uV)
        if nbytes != 0:
            X.shape = self.nchans, self.nt # reshape
        f.seek(fp + nbytes) # skip any pad bytes
        return nbytes, X

    def read_ver_2(self, f):
        """Same as version 1. NVS created some version 1 files incorrectly, and
        incremented to version 2 for the correctly exported ones"""
        return self.read_ver_1(f)


class SPKHeader(object):
    """Represents a folder containing neurons in .spk files. Similar to a
    PTCSHeader, but much more impoverished"""
    def __init__(self, path):
        self.path = path
        fnames = [ fname for fname in os.listdir(self.path)
                   if os.path.isfile(os.path.join(self.path, fname))
                   and fname.endswith('.spk') ] # spike filenames
        self.spkfnames = sorted(fnames)
        self.nspikes = 0

    def read(self, neuron):
        neuron.loadspk() # load the neuron
        self.nspikes += neuron.nspikes
        # look for neuron2pos.py file, which contains a dict mapping neuron id to (x, y)
        # position
        if 'neuron2pos.py' in os.listdir(self.path):
            oldpath = os.getcwd()
            os.chdir(self.path)
            from neuron2pos import neuron2pos
            neuron.record.xpos, neuron.record.ypos = neuron2pos[neuron.id]
            os.chdir(oldpath)
            

class SPKNeuronRecord(object):
    """Represents the spike times in a simple .spk file as a record. Similar to a
    PTCSNeuronRecord, but much more impoverished"""
    def __init__(self, fname):
        self.fname = fname
        
    def parse_id(self):
        """Return everything from just after the last '_t' to the end of the
        fname, should be all numeric"""
        name = os.path.split(self.fname)[-1] # pathless
        name = os.path.splitext(name)[0] # extensionless
        return int(name.rsplit('_t', 1)[-1]) # id

    def read(self):
        self.nid = self.parse_id()
        with open(self.fname, 'rb') as f:
            self.spikes = np.fromfile(f, dtype=np.int64) # spike timestamps (us)
        self.nspikes = len(self.spikes)
    

class LFP(object):
    """Holds LFP data loaded from a numpy .npz-compatible .lfp.zip file"""
    def __init__(self, recording, fname):
        """
        self.chanpos: array of (x, y) LFP channel positions on probe, in order of
                      increasing zero-based channel IDs
        self.chans: channel IDs of rows in self.chanpos and self.data, in vertical
                    spatial order
        self.data: LFP voltage values, channels in rows (in vertical spatial order),
                   timepoints in columns
        self.t0: time in us of first LFP timepoint, from start of recording acquisition
        self.t1: time in us of last LFP timepoint
        self.tres: temporal resolution in us of each LFP timepoint
        self.uVperAd: number of uV per AD voltage value in LFP data
        """
        self.r = recording
        self.fname = fname # with full path

    def load(self):
        with open(self.fname, 'rb') as f:
            d = np.load(f)
            assert sorted(d.keys()) == ['chanpos', 'chans', 'data', 't0', 't1', 'tres',
                                        'uVperAD']
            # bind arrays in .lfp.zip file to self:
            for key, val in d.iteritems():
                # pull some singleton vals out of their arrays:
                if key in ['t0', 't1', 'tres']: # should all be us
                    val = int(val)
                elif key == 'uVperAD':
                    val = float(val)
                self.__setattr__(key, val)
        # make sure chans are in vertical spatial order:
        assert issorted(self.chanpos[self.chans][1])
        self.sampfreq = intround(1e6 / self.tres) # in Hz
        assert self.sampfreq == 1000 # should be 1000 Hz
        self.data = self.data * self.uVperAD # convert to float uV
        self.PLOTGAIN = 2

    def save(self):
        ## TODO: option to overwrite original .lfp.zip file from spyke with filtered data,
        ## add filteredfreqs and filteredbws keywords when resaving to indicate what exactly
        ## was filtered out. Also, convert data back to int16?
        raise NotImplementedError

    def get_data(self):
        """Return data, testing first to see if it's been loaded"""
        try:
            self.data
        except AttributeError:
            self.load()
        return self.data

    def get_tssec(self):
        """Return full set of timestamps, in sec"""
        return np.arange(self.t0/1e6, self.t1/1e6, self.tres/1e6)

    def plot(self, t0=None, t1=None, chanis=None, figsize=(20, 6.5)):
        """Plot chanis of LFP data between t0 and t1 in sec"""
        self.get_data()
        ts = self.get_tssec() # full set of timestamps, in sec
        if t0 == None:
            t0, t1 = ts[0], ts[-1]
        if t1 == None:
            t1 = t0 + 10 # 10 sec window
        if chanis == None:
            chanis = range(len(self.chans)) # all chans
        t0i, t1i = ts.searchsorted((t0, t1))
        ts = ts[t0i:t1i] # constrained set of timestamps, in sec
        chanis = tolist(chanis)
        nchans = len(chanis)
        # grab desired channels and time range, and AD values to uV:
        data = self.data[chanis][:, t0i:t1i] * self.uVperAD * self.PLOTGAIN
        nt = len(ts)
        assert nt == data.shape[1]
        x = np.tile(ts, nchans)
        x.shape = nchans, nt
        segments = np.zeros((nchans, nt, 2)) # x vals in col 0, yvals in col 1
        segments[:, :, 0] = x
        segments[:, :, 1] = data
        # add offsets:
        for chanii, chani in enumerate(chanis):
            chan = self.chans[chani]
            xpos, ypos = self.chanpos[chan]
            #segments[chani, :, 0] += xpos
            segments[chanii, :, 1] -= ypos # vertical distance below top of probe
        lc = LineCollection(segments, linewidth=1, linestyle='-', colors='k',
                            antialiased=True, visible=True)
        f = pl.figure(figsize=figsize)
        a = f.add_subplot(111)
        a.add_collection(lc) # add to axes' pool of LCs
        a.autoscale(enable=True, tight=True)
        # turn off annoying "+2.41e3" type offset on x axis:
        formatter = mpl.ticker.ScalarFormatter(useOffset=False)
        a.xaxis.set_major_formatter(formatter)
        a.set_xlabel("time (sec)")
        a.set_ylabel("depth (um)")
        titlestr = lastcmd()
        gcfm().window.setWindowTitle(titlestr)
        a.set_title(titlestr)
        a.text(0.998, 0.99, '%s' % self.r.name, transform=a.transAxes,
               horizontalalignment='right', verticalalignment='top')
        f.tight_layout(pad=0.3) # crop figure to contents
        self.f = f
        return self
        
    def specgram(self, t0=None, t1=None, f0=0.1, f1=100, p0=-60, p1=None, chanis=-1,
                 width=4.096, tres=1, cm=None, colorbar=False, figsize=(20, 6.5)):
        """Plot a spectrogram from t0 to t1 in sec, from f0 to f1 in Hz, and clip power values
        from p0 to p1 in dB, based on channel index chani of LFP data. chanis=0 uses most
        superficial channel, chanis=-1 uses deepest channel. If len(chanis) > 1, take mean of
        specified chanis. width and tres are in sec. Best to keep number of samples in width a
        power of 2. As an alternative to cm.jet (the default), cm.gray, cm.hsv cm.terrain, and
        cm.cubehelix_r colormaps seem to bring out the most structure in the spectrogram"""
        self.get_data()
        ts = self.get_tssec() # full set of timestamps, in sec
        if t0 == None:
            t0, t1 = ts[0], ts[-1] # full duration
        if t1 == None:
            t1 = t0 + 10 # 10 sec window
        assert tres <= width
        NFFT = intround(width * self.sampfreq)
        noverlap = intround(NFFT - tres * self.sampfreq)
        t0i, t1i = ts.searchsorted((t0, t1))
        #ts = ts[t0i:t1i] # constrained set of timestamps, in sec
        data = self.data[:, t0i:t1i] # slice data
        f = pl.figure(figsize=figsize)
        a = f.add_subplot(111)
        if iterable(chanis):
            data = data[chanis].mean(axis=0) # take mean of data on chanis
        else:
            data = data[chanis] # get single row of data at chanis
        # convert data from uV to mV, returned t is midpoints of timebins in sec from
        # start of data. I think P is in mV^2?:
        P, freqs, t = mpl.mlab.specgram(data/1e3, NFFT=NFFT, Fs=self.sampfreq,
                                        noverlap=noverlap)
        # for completeness, should convert t to time from start of acquisition, although
        # there's no need to because t isn't used anywhere:
        #t += t0
        # keep only freqs between f0 and f1:
        if f0 == None:
            f0 = freqs[0]
        if f1 == None:
            f1 = freqs[-1]
        lo, hi = freqs.searchsorted([f0, f1])
        P, freqs = P[lo:hi], freqs[lo:hi]
        # check for and replace zero power values (ostensibly due to gaps in recording)
        # before attempting to convert to dB:
        zis = np.where(P == 0.0) # row and column indices where P has zero power
        if len(zis[0]) > 0: # at least one hit
            P[zis] = np.finfo(np.float64).max # temporarily replace zeros with max float
            minnzval = P.min() # get minimum nonzero value
            P[zis] = minnzval # replace with min nonzero values
        P = 10. * np.log10(P) # convert power to dB wrt 1 mV^2?
        # for better visualization, clip power values to within (p0, p1) dB
        if p0 != None:
            P[P < p0] = p0
        if p1 != None:
            P[P > p1] = p1
        #self.P = P
        # Label far left, right, top and bottom edges of imshow image. imshow interpolates
        # between these to place the axes ticks. Time limits are
        # set from start of acquisition:
        extent = t0, t1, freqs[0], freqs[-1]
        #print('specgram extent: %r' % (extent,))
        # flip P vertically for compatibility with imshow:
        im = a.imshow(P[::-1], extent=extent, cmap=cm)
        a.autoscale(enable=True, tight=True)
        a.axis('tight')
        # turn off annoying "+2.41e3" type offset on x axis:
        formatter = mpl.ticker.ScalarFormatter(useOffset=False)
        a.xaxis.set_major_formatter(formatter)
        a.set_xlabel("time (sec)")
        a.set_ylabel("frequency (Hz)")
        titlestr = lastcmd()
        gcfm().window.setWindowTitle(titlestr)
        a.set_title(titlestr)
        a.text(0.998, 0.99, '%s' % self.r.name, color='w', transform=a.transAxes,
               horizontalalignment='right', verticalalignment='top')
        f.tight_layout(pad=0.3) # crop figure to contents
        if colorbar:
            f.colorbar(im, pad=0) # creates big whitespace to the right for some reason
        self.f = f
        return P, freqs

    def notch(self, chanis=None, freq=60, bw=0.25, gpass=0.01, gstop=30, ftype='ellip'):
        """Filter out frequencies centered on freq (Hz), of bandwidth +/- bw (Hz) on
        data row indices chanis.

        ftype: 'ellip', 'butter', 'cheby1', 'cheby2', 'bessel'
        """
        data = self.get_data()
        if chanis == None:
            chanis = np.arange(len(data))
        data = data[chanis]
        data, b, a = filter.notch(data, self.sampfreq, freq, bw, gpass, gstop, ftype)
        self.data[chanis] = data
        return b, a

    def naivenotch(self, freqs=60, bws=1):
        """Filter out frequencies in data centered on freqs (Hz), of bandwidths bws (Hz).
        Filtering out by setting components to 0 is probably naive"""
        data = self.get_data()
        self.data = filter.naivenotch(data, self.sampfreq, freqs, bws)

    def filter(self, chanis=None, f0=0, f1=7, fr=0.5, gpass=0.01, gstop=30, ftype='ellip'):
        """Bandpass filter data on row indices chanis, between f0 and f1 (Hz), with filter
        rolloff (?) fr (Hz).

        ftype: 'ellip', 'butter', 'cheby1', 'cheby2', 'bessel'
        """
        data = self.get_data()
        if chanis == None:
            chanis = np.arange(len(data))
        data = data[chanis]
        data, b, a = filter.filter(data, self.sampfreq, f0, f1, fr, gpass, gstop, ftype)
        self.data[chanis] = data
        return b, a

    def filterord(self, chanis=None, f0=300, f1=None, order=4, rp=None, rs=None,
                  btype='highpass', ftype='butter'):
        """Bandpass filter data by specifying filter order and btype, instead of gpass and
        gstop"""
        data = self.get_data()
        if chanis == None:
            chanis = np.arange(len(data))
        data = data[chanis]
        data, b, a = filter.filterord(data, self.sampfreq, f0, f1, order, rp, rs, btype, ftype)
        self.data[chanis] = data
        return b, a

    def si(self, chani=-1, lowband=None, highband=None, ratio='L/(L+H)',
           width=None, tres=None, plot=True):
        """Return synchrony index, i.e. power ratio of low vs high bands, as measured by
        Fourier transform. Use either L/(L+H) ratio (Saleem2010) or L/H ratio (Li, Poo, Dan
        2009). width and tres are in sec. A smaller tres smooths the returned time series"""
        data = self.get_data()
        ts = self.get_tssec() # full set of timestamps, in sec
        t0, t1 = ts[0], ts[-1] # full duration
        x = data[chani] / 1e3 # convert from uV to mV
        x = filter.notch(x)[0] # remove 60 Hz mains noise
        rr = self.r.e0.I['REFRESHRATE']
        if rr <= 100: # CRT was at low vertical refresh rate
            print('filtering out %d Hz from LFP in %s' % (intround(rr), self.r.name))
            x = filter.notch(x, freq=rr)[0] # remove CRT interference

        uns = get_ipython().user_ns
        if lowband == None:
            lowband = uns['SILOWBAND']
        f0, f1 = lowband
        if highband == None:
            highband = uns['SIHIGHBAND']
        f2, f3 = highband
        if width != None:
            if tres == None:
                tres = width
        if width == None:
            width = uns['SIWIDTH'] # sec
        if tres == None:
            tres = uns['SITRES'] # sec
        assert tres <= width
        NFFT = intround(width * self.sampfreq)
        noverlap = intround(NFFT - tres * self.sampfreq)
        #print('len(x), NFFT, noverlap: %d, %d, %d' % (len(x), NFFT, noverlap))
        # t is midpoints of timebins in sec from start of data. P is in mV^2?:
        P, freqs, t = mpl.mlab.specgram(x, NFFT=NFFT, Fs=self.sampfreq, noverlap=noverlap)
        # don't convert power to dB, just washes out the signal in the ratio:
        #P = 10. * np.log10(P)
        # convert t to time from start of acquisition:
        t += t0
        # keep only freqs between f0 and f1, and f2 and f3:
        if f0 == None:
            f0 = freqs[0]
        if f1 == None:
            f1 = freqs[-1]
        f0i, f1i, f2i, f3i = freqs.searchsorted([f0, f1, f2, f3])
        lP = P[f0i:f1i]
        hP = P[f2i:f3i]
        lP = lP.sum(axis=0)
        hP = hP.sum(axis=0)
        if ratio == 'L/(L+H)':
            r = lP/(hP + lP)
        elif ratio == 'L/H':
            r = lP/hP
        else:
            raise ValueError
        if plot:
            ylabel = 'LFP synchrony index (%s)' % ratio
            self.si_plot(t, r, t0, t1, ylabel, title=lastcmd(), text=self.r.name)
        return r, t # t are midpoints of bins, from start of acquisition
        
    def si_hilbert(self, chani=-1, lowband=None, highband=None, ratio='L/(L+H)',
                   plot=True):
        """Return synchrony index, i.e. power ratio of low vs high bands, as measured by
        Hilbert transform (Saleem2010). Use either L/(L+H) ratio (Saleem2010) or L/H ratio
        (Li, Poo, Dan 2009)"""
        if lowband == None:
            lowband = uns['SILOWBAND']
        f0, f1 = lowband
        if highband == None:
            highband = uns['SIHIGHBAND']
        f2, f3 = highband
        data = self.get_data()
        t = self.get_tssec() # full set of timestamps, in sec
        t0, t1 = t[0], t[-1] # full duration
        x = data[chani] / 1e3 # convert from uV to mV
        x = filter.notch(x)[0] # remove 60 Hz mains noise
        rr = self.r.e0.I['REFRESHRATE']
        if rr <= 100: # CRT was at low vertical refresh rate
            print('filtering out %d Hz from LFP in %s' % (intround(rr), self.r.name))
            x = filter.notch(x, freq=rr)[0] # remove CRT interference
        # remove everything below f0:
        #x = filter.filterord(data=x, f0=f0, order=4, btype='highpass')[0]
        #x = filter.filter(data=x, f0=0.5, f1=0, fr=0.1, ftype='ellip', gstop=20)
        # remove everything above f3:
        x = filter.filterord(data=x, f0=f3, order=10, btype='lowpass')[0]
        l = filter.filterord(data=x, f0=f1, order=4, btype='lowpass')[0]
        h = filter.filterord(data=x, f0=f2, order=11, btype='highpass')[0]
        lP, lPh, lE, lA = filter.hilbert(l)
        hP, hPh, hE, hA = filter.hilbert(h)

        if ratio == 'L/(L+H)':
            r = lP/(hP + lP)
        elif ratio == 'L/H':
            r = lP/hP
        else:
            raise ValueError
        if plot:
            ylabel = 'LFP synchrony index (%s)' % ratio
            self.si_plot(t, r, t0, t1, ylabel, title=lastcmd(), text=self.r.name)
        return r, t

    def si_plot(self, t, P, t0=None, t1=None, ylabel=None, title=None, text=None,
                figsize=(20, 6.5)):
        """Plot synchrony index as a function of time, with hopefully the same
        temporal scale as some of the other plots in self"""
        if figsize == None:
            f = pl.gcf()
            a = pl.gca()
        else:
            f = pl.figure(figsize=figsize)
            a = f.add_subplot(111)
        a.plot(t, P, 'k.-')
        a.set_xlabel("time (sec)")
        if ylabel == None:
            ylabel = "power (AU?)"
        elif ylabel in ['L/(L+H)', 'H/(L+H)']:
            a.set_ylim(0, 1)
        a.set_xlim(t0, t1) # low/high limits are unchanged if None
        a.set_ylim(0, 1) # full SI range
        a.set_ylabel(ylabel)
        #a.autoscale(axis='x', enable=True, tight=True)
        # turn off annoying "+2.41e3" type offset on x axis:
        formatter = mpl.ticker.ScalarFormatter(useOffset=False)
        a.xaxis.set_major_formatter(formatter)
        if title:
            gcfm().window.setWindowTitle(title)
            a.set_title(title)
        if text:
            a.text(0.998, 0.01, '%s' % text, color='k', transform=a.transAxes,
                   horizontalalignment='right', verticalalignment='bottom')
        f.tight_layout(pad=0.3) # crop figure to contents

    def filterwavelet(self, chanis=None, wname="db4", maxlevel=6):
        """Filter data using wavelet multi-level decomposition and reconstruction (WMLDR).
        See Wiltschko2008"""
        data = self.get_data()
        if chanis == None:
            chanis = np.arange(len(data))
        data = data[chanis]
        data = filter.wavelet(data, wname, maxlevel)
        self.data[chanis] = data


class DensePopulationRaster(object):
    """Population spike raster plot, with dense vertical spacing according to neuron depth
    rank, and colour proportional to neuron depth"""
    def __init__(self, trange=None, neurons=None, norder=None, units='sec', text=None,
                 figsize=(20, None)):
        """neurons is a dict, trange is time range in us to raster plot over. Raster plot
        is displayed in time units of units"""
        assert len(trange) == 2
        trange = np.asarray(trange)
        if norder != None:
            nids = norder
        else: # sort neurons by their depth rank:
            nids = np.sort(neurons.keys())
            # depth from top of electrode:
            unsorted_ypos = np.array([ neurons[nid].pos[1] for nid in nids ])
            nids = nids[unsorted_ypos.argsort()]
        self.nids = nids
        print(nids)
        # depth of nids from top of electrode
        ypos = np.array([ neurons[nid].pos[1] for nid in nids ])
        supis, midis, deepis = laminarity(ypos)
        nn = len(nids)
        t, y, c = [], [], []
        for nidi, nid in enumerate(nids):
            n = neurons[nid]
            lo, hi = n.spikes.searchsorted(trange)
            spikes = n.spikes[lo:hi]
            nspikes = len(spikes)
            if nspikes > 0:
                t.append(spikes)
                y.append(np.tile(nidi, nspikes)) # depth rank below top of electrode
                if supis[nidi]: color = 'r'
                elif midis[nidi]: color = 'g'
                elif deepis[nidi]: color = 'b'
                else: color = 'y'
                c.append(np.tile(color, nspikes))

        t = np.hstack(t)
        # spike time multiplier to use for raster labels:
        tx = {'us': 1, 'ms': 1000, 'sec': 1000000}[units]
        if tx != 1:
            t = t / tx # don't do in-place, allow conversion to float
        y = np.hstack(y)
        c = np.hstack(c)

        if figsize[1] == None:
            figsize = figsize[0], 1 + nn / 7 # ~1/7th vertical inch per neuron
        f = pl.figure(figsize=figsize)
        a = f.add_subplot(111)
        a.scatter(t, y, marker='|', c=c, s=50)
        a.set_xlim(trange/tx)
        a.set_ylim(nn, -1) # this inverts the y axis
        # turn off annoying "+2.41e3" type offset on x axis:
        formatter = mpl.ticker.ScalarFormatter(useOffset=False)
        a.xaxis.set_major_formatter(formatter)
        a.set_xlabel("time (%s)" % units)
        a.set_ylabel("neuron depth rank")
        titlestr = lastcmd()
        gcfm().window.setWindowTitle(titlestr)
        if text: # add text to titlestr, to keep axes completely free of text
            titlestr += ' (%s)' % text
        a.set_title(titlestr)
        # add pseudo legend of coloured text:
        tmax = a.get_xlim()[1]
        #rainbow_text(a, 0.905*tmax, -1.5, ['superficial', 'middle', 'deep'], ['r', 'g', 'b'])
        a.text(0.908*tmax, -1.5, 'superficial', color='r')
        a.text(0.952*tmax, -1.5, 'middle', color='g')
        a.text(0.980*tmax, -1.5, 'deep', color='b')
        f.tight_layout(pad=0.3) # crop figure to contents
        self.f = f


class SpatialPopulationRaster(object):
    """Population spike raster plot, with vertical spacing proportional to neuron depth,
    colour representing neuron id, and point size inversely proportional to spike rate."""
    def __init__(self, trange=None, neurons=None, norder=None, units='sec', text=None,
                 figsize=(20, 6.5)):
        """neurons is a dict, trange is time range in us to raster plot over. Raster plot
        is displayed in time units of units"""
        assert len(trange) == 2
        trange = np.asarray(trange)
        if norder != None:
            nids = norder
            self.norder = norder
            print(norder)
        else:
            nids = sorted(neurons.keys())
        t, y, c, s = [], [], [], []
        for nidi, nid in enumerate(nids):
            n = neurons[nid]
            lo, hi = n.spikes.searchsorted(trange)
            spikes = n.spikes[lo:hi]
            nspikes = len(spikes)
            if nspikes > 0:
                t.append(spikes)
                if norder != None:
                    ypos = nidi
                else:
                    ypos = -n.pos[1]
                y.append(np.tile(ypos, nspikes)) # -ve, distance below top of electrode
                color = CLUSTERCOLOURRGBDICT[nid]
                c.append(np.tile(color, nspikes))
                # use big points for low rate cells, small points for high rate cells:
                ms = max(min(10000/nspikes, 50), 5)
                s.append(np.tile(ms, nspikes))
        t = np.hstack(t)
        # spike time multiplier to use for raster labels:
        tx = {'us': 1, 'ms': 1000, 'sec': 1000000}[units]
        if tx != 1:
            t = t / tx # don't do in-place, allow conversion to float
        y = np.hstack(y)
        c = np.hstack(c)
        c.shape = -1, 3
        s = np.hstack(s)

        f = pl.figure(figsize=figsize)
        a = f.add_subplot(111)
        a.scatter(t, y, marker='.', c=c, edgecolor='none', s=s)
        a.set_xlim(trange/tx)
        if norder == None: # set y axis limits according to spatial extent of probe
            # grab first neuron's sort.chanpos, should be the same for all:
            chanpos = neurons[nids[0]].sort.chanpos
            ymax = chanpos[:, 1].max() # max chan distance below top of probe
            ymax = np.ceil(ymax / 50) * 50 # round up to nearest multiple of 100 um
            a.set_ylim(-ymax, 0)
        else: # autoscale 'nidi' integer y axis
            a.autoscale(enable=True, axis='y', tight=True)
        # turn off annoying "+2.41e3" type offset on x axis:
        formatter = mpl.ticker.ScalarFormatter(useOffset=False)
        a.xaxis.set_major_formatter(formatter)
        a.set_xlabel("time (%s)" % units)
        if norder != None:
            a.set_ylabel("nidi")
        else:
            a.set_ylabel("depth (um)")
        titlestr = lastcmd()
        gcfm().window.setWindowTitle(titlestr)
        if text: # add text to titlestr, to keep axes completely free of text
            titlestr += ' (%s)' % text
        a.set_title(titlestr)
        f.tight_layout(pad=0.3) # crop figure to contents
        self.f = f
    '''
    def _onmotion(self, event):
        """Called during mouse motion over figure. Pops up neuron and
        experiment info in a tooltip when hovering over a neuron row."""
        self.f.canvas.mpl_connect('motion_notify_event', self._onmotion)
        self.f.canvas.mpl_connect('key_press_event', self._onkeypress)

        if event.inaxes: # if mouse is inside the axes
            nii = int(math.floor(event.ydata)) # use ydata to get index into sorted list of neurons
            ni = self.nids[nii]
            neuron = self.neurons[ni]
            currentexp = None
            for e in self.e.values(): # for all experiments
                estart = (e.trange[0]-self.t0)/self.tconv
                eend = (e.trange[1]-self.t0)/self.tconv
                if estart < event.xdata  < eend:
                    currentexp = e
                    break # don't need to check any of the other experiments
            tip = 't: %.3f ms\n' % event.xdata # print timepoint down to nearest us, in units of ms
            tip += 'n%d: %d spikes' % (neuron.id, neuron.nspikes)
            if currentexp == None:
                tip += '\nno experiment'
            else:
                tip += '\nexperiment %s: %r' % (currentexp.id, currentexp.name)
            self.tooltip.SetTip(tip) # update the tooltip
            self.tooltip.Enable(True) # make sure it's enabled
        else: # mouse is outside the axes
            self.tooltip.Enable(False) # disable the tooltip

    def _onkeypress(self, event):
        """Called during a figure keypress"""
        key = event.guiEvent.GetKeyCode() # wx dependent
        #print key
        # you can also just use the backend-neutral event.key, but that doesn't recognize as many keypresses, like pgup, pgdn, etc.
        if not event.guiEvent.ControlDown(): # Ctrl key isn't down, wx dependent
            if key == wx.WXK_RIGHT: # pan right
                self._panx(+0.1)
            elif key == wx.WXK_LEFT: # pan left
                self._panx(-0.1)
            elif key == wx.WXK_UP: # zoom in
                self._zoomx(1.2)
            elif key == wx.WXK_DOWN: # zoom out
                self._zoomx(1/1.2)
            elif key == wx.WXK_NEXT: # PGDN (page right)
                self._panx(+1)
            elif key == wx.WXK_PRIOR: # PGUP (page left)
                self._panx(-1)
            elif key == wx.WXK_HOME: # go to start of first Experiment
                self._panx(left=self.experimentmarkers[0])
            elif key == wx.WXK_END: # go to end of last Experiment
                self._panx(left=self.experimentmarkers[-1]-self.width)
            elif key == ord('['): # skip backwards to previous jump point
                i = self.jumpts.searchsorted(self.left, side='left') # current position of left edge of the window in jumpts list
                i = max(0, i-1) # decrement by 1, do bounds checking
                self._panx(left=self.jumpts[i])
            elif key == ord(']'): # skip forwards to next jump point
                i = self.jumpts.searchsorted(self.left, side='right') # current position of left edge of the window in jumpts list
                i = min(i, len(self.jumpts)-1) # bounds checking
                self._panx(left=self.jumpts[i])
            elif key == wx.WXK_RETURN: # go to position
                self._goto()
            elif key == ord(','): # cycle tick formatter through thousands separators
                self._cyclethousandssep()
            elif key == ord('B'): # toggle plotting of bin edges
                self._togglebinedges()
        else: # Ctrl key is down
            if key == wx.WXK_LEFT: # skip backwards to previous experiment marker
                i = self.experimentmarkers.searchsorted(self.left, side='left') # current position of left edge of the window in experimentmarkers list
                i = max(0, i-1) # decrement by 1, do bounds checking
                self._panx(left=self.experimentmarkers[i])
            elif key == wx.WXK_RIGHT: # skip forwards to next experiment marker
                i = self.experimentmarkers.searchsorted(self.left, side='right') # current position of left edge of the window in experimentmarkers list
                i = min(i, len(self.experimentmarkers)-1) # bounds checking
                self._panx(left=self.experimentmarkers[i])
            elif key == wx.WXK_UP: # zoom in faster
                self._zoomx(3.0)
            elif key == wx.WXK_DOWN: # zoom out faster
                self._zoomx(1/3.0)
    '''

class Codes(object):
    """A 2D array where each row is a neuron code, and each column
    is a binary population word for that time bin, sorted LSB to MSB from top to bottom.
    neurons is a list of Neurons, also from LSB to MSB. Order in neurons is preserved."""
    def __init__(self, neurons=None, tranges=None, shufflecodes=False):
        self.neurons = neurons
        self.tranges = tolist(tranges)
        self.shufflecodes = shufflecodes
        self.nids = [ neuron.id for neuron in self.neurons ]
        self.nneurons = len(self.neurons)
        # make a dict from keys:self.nids, vals:range(self.nneurons). This converts from nids
        # to niis (from neuron indices to indices into the binary code array self.c)
        self.nids2niisdict = dict(zip(self.nids, range(self.nneurons)))

    def nids2niis(self, nids=None):
        """Converts from nids to niis (from neuron indices to indices into the binary code
        array self.c). nids can be a sequence"""
        try:
            return [ self.nids2niisdict[ni] for ni in nids ]
        except TypeError: # iteration over non-sequence, nids is a scalar
            return self.nids2niisdict[nids]

    def calc(self):
        self.c = [] # stores the 2D code array
        # append neurons in their order in self.neurons, store them LSB to MSB from top to
        # bottom
        for neuron in self.neurons:
            codeo = neuron.code(tranges=self.tranges)
            # build up nested list (ie, 2D) of spike times, each row will have different
            # length:
            if self.shufflecodes:
                c = codeo.c.copy() # make a copy (leave the codeo's codetrain untouched)
                np.random.shuffle(c) # shuffle each neuron's codetrain separately, in-place
            else:
                c = codeo.c # just a pointer
            self.c.append(c) # flat list
        # store the bin edges, for reference. All bin times should be the same for all
        # neurons, because they're all given the same trange. use the bin times of the last
        # neuron
        self.t = codeo.t
        nneurons = len(self.neurons)
        nbins = len(self.c[0]) # all entries in the list should be the same length
        self.c = np.concatenate(self.c).reshape(nneurons, nbins)

    def syncis(self):
        """Returns synch indices, ie the indices of the bins for which all the
        neurons in this Codes object have a 1 in them"""
        # take product down all rows, only synchronous events across all cells will survive:
        return self.c.prod(axis=0).nonzero()[0]

    def syncts(self):
        """Returns synch times, ie times of the left bin edges for which
        all the neurons in this Codes object have a 1 in them"""
        return self.t[self.syncis()]

    def synctsms(self):
        """Returns synch times in ms, to the nearest ms"""
        return np.int32(np.round(self.syncts() / 1e3))

    def copy(self):
        """Returns a copy of the Codes object"""
        return copy(self)
    '''
    # needs some testing:
    def append(self, others):
        """Adds other Codes objects appended in time (horizontally) to this Codes object.
        Useful for appending Codes objects across Recordings ? (don't really need it
        for appending across Experiments)"""
        others = tolist(others)
        for other in others:
            assert other.neurons == self.neurons
        codesos = [self] # list of codes objects
        codesos.extend(others)
        # this tranges potentially holds multiple tranges from each codes objects,
        # times the number of codes objects
        self.tranges = [ trange for codeso in codesos for trange in codeso.tranges ]
        self.calc() # recalculate this code with its new set of tranges
    '''
    
class SpikeCorr(object):
    """Calculate and plot spike correlations of all cell pairs from nids (or of all
    cell pairs within some torus of radii R=(R0, R1) in um) in this Recording, during tranges
    or experiments. If width is not None, calculate self as a function of time, with bin
    widths width sec and time resolution tres sec. Weights is a tuple of weight values and
    times, to weight different parts of the recording differently. For each pair, shift the
    second spike train by shift ms, or shift it by shiftcorrect ms and subtract the
    correlation from the unshifted value."""
    def __init__(self, recording=None, tranges=None, width=None, tres=None, weights=None,
                 shift=0, shiftcorrect=0, experiments=None, nids=None, R=None):
        self.r = recording
        if tranges != None:
            self.tranges = tranges
        elif experiments != None:
            self.tranges = [ e.trange for e in experiments ]
        else:
            self.tranges = [ self.r.trange ] # use the Recording's trange

        if shift or shiftcorrect:
            raise NotImplementedError("shift and shiftcorrect are currently disabled to "
                                      "simplify the logic")

        if nids == None:
            nids = sorted(self.r.n)
            if len(nids) == 0:
                raise RuntimeError("Recording %s has no active neurons" % self.r.id)
        self.nids = nids
        self.codes = self.r.codes(nids=nids, tranges=tranges) # calculate them once

        if width != None:
            if tres == None:
                tres = width
            assert tres <= width
            width = intround(width * 1000000) # convert from sec to us
            tres = intround(tres * 1000000) # convert from sec to us
        self.width = width
        self.tres = tres

        if weights != None:
            raise NotImplementedError('weights are currently disabled for speed')
        self.weights = weights
        self.shift = shift # shift spike train of the second of each neuron pair, in ms
        # shift correct spike train of the second of each neuron pair by this much, in ms
        self.shiftcorrect = shiftcorrect
        if R != None:
            assert len(R) == 2 and R[0] < R[1]  # should be R = (R0, R1) torus
        self.R = R

    def calc(self):
        if self.width != None:
            # compute correlation coefficients as a function of time, one value per trange:
            self.tranges = split_tranges(self.tranges, self.width, self.tres)
            uns = get_ipython().user_ns
            highval = uns['CODEVALS'][1]
            c, t = self.codes.c, self.codes.t
            corrs, counts = util.sct(c, t, self.tranges, highval)
            nneurons = len(c)
            pairs = np.asarray(np.triu_indices(nneurons, k=1)).T
        else:
            # compute correlation coefficients once across entire set of tranges:
            corrs, counts, pairs = self.calc_single(self.codes)
        self.corrs = corrs
        self.counts = counts
        self.pairs = pairs
        self.npairs = len(pairs)

    def calc_single(self, codes):
        """Calculate one spike correlation value for each cell pair, given codes spanning
        some subset of self.tranges, contrained to torus described by self.R, weighted by
        self.weights"""
        c = codes.c # nneurons x nbins array
        c = np.float64(c) # prevent int8 overflow somewhere
        nneurons, nbins = c.shape
        nids = self.nids
        '''
        # calculate bin weights:
        binw = 1 # default
        if self.weights != None:
            w, wt = self.weights # weights and weight times
            assert len(w) == len(wt)
            ## TODO: maybe w needs to be recentered between max and min possible LFP
            ## synch values (say, 1 and 0.15?)
            # get bin times from codes:
            t = codes.t
            binw = np.zeros(nbins) # bin weights
            # this might assume that there are fewer weight times than bin times,
            # but that should usually be a safe assumption if weights come from LFP:
            assert len(wt) < nbins
            tis = t.searchsorted(wt) # where weight times fit into bin times
            tis = np.append(tis, nbins)
            for i in range(len(tis)-1):
                ti0 = tis[i]
                ti1 = tis[i+1]
                binw[ti0:ti1] = w[i]
        meanw = np.mean(binw)
        '''
        # precalculate mean and std of each cell's codetrain, rows correspond to nids:
        means = c.mean(axis=1)
        stds = c.std(axis=1)

        # precalculate number of high states in each neuron's code:
        nhigh = np.zeros(nneurons, dtype=np.int64)
        uns = get_ipython().user_ns
        if uns['CODEVALS'] != [0, 1]:
            raise RuntimeError("counting of high states assumes CODEVALS = [0, 1]")
        for nii0 in range(nneurons):
            nhigh[nii0] = c[nii0].sum()
        
        #shift, shiftcorrect = self.shift, self.shiftcorrect
        #if shift and shiftcorrect:
        #    raise ValueError("only one of shift or shiftcorrect can be nonzero")

        # iterate over all pairs:
        n = self.r.n
        R = self.R
        corrs = []
        counts = []
        pairs = []
        for nii0 in range(nneurons):
            ni0 = nids[nii0]
            for nii1 in range(nii0+1, nneurons):
                ni1 = nids[nii1]
                # skip the pair's if a torus is specified and if
                # the pair's separation falls outside bounds of specified torus:
                if R != None and not (R[0] < dist(n[ni0].pos, n[ni1].pos) < R[1]):
                    continue # to next pair
                # potentially shift only the second code train of each pair:
                #c0 = self.r.n[ni0].code(tranges=tranges).c
                #c1 = self.r.n[ni1].code(tranges=tranges, shift=shift).c
                c0 = c[nii0]
                c1 = c[nii1]
                # (mean of product - product of means) / product of stds:
                #numer = (c0 * c1 * binw).mean() - means[nii0] * means[nii1] * meanw
                numer = np.dot(c0, c1) / nbins - means[nii0] * means[nii1]
                denom = stds[nii0] * stds[nii1]
                if numer == 0.0:
                    sc = 0.0 # even if denom is also 0
                elif denom == 0.0: # numer is not 0, but denom is 0, prevent div by 0
                    print('skipped pair (%d, %d) in r%s' % (ni0, ni1, self.r.id))
                    continue # skip to next pair
                else:
                    sc = numer / denom
                # potentially shift correct using only the second spike train of each pair:
                #if shiftcorrect:
                #    c1sc = self.r.n[ni1].code(tranges=tranges, shift=shiftcorrect).c
                #    scsc = ((c0 * c1sc).mean() - means[ni0] * means[ni1]) / denom
                #    ## TODO: might also want to try subtracting abs(scsc)?
                #    sc -= scsc
                corrs.append(sc)
                pairs.append([nii0, nii1])
                # take sum of high code counts of pair. Note that taking the mean wouldn't
                # change results in self.sct(), because it would end up simply normalizing
                # by half the value
                counts.append(nhigh[nii0] + nhigh[nii1])
        corrs = np.asarray(corrs)
        counts = np.asarray(counts)
        pairs = np.asarray(pairs)
        return corrs, counts, pairs

    def clear_codes(self):
        """Delete all of recording's cached codes"""
        for n in self.r.alln.values():
            try:
                del n._codes
            except AttributeError:
                pass

    def norder(self, metric=False, n_init=10, max_iter=1000, verbose=0, eps=-np.inf,
               n_jobs=1, init=None):
        """Return nids of self's recording sorted according to their pairwise correlations.
        This uses multidimensional scaling (MDS) to take N*(N-1)/2 pairwise values and
        return a 1D projection in which cells with the greatest similarity are kept as close
        to each other as possible, with as little "stress" as possible. This might then be
        useful for sorting raster plots to better reveal ensemble activity.

        Note that so far, this generates orderings that are poorly reproducible across runs,
        and seem fairly random. There is some confusion in the docs for sklearn.manifold.MDS
        as to whether to pass it a similarity matrix (high values mean that pair should be
        kept close together) or a dissimilarity matrix (high values mean that pair should be
        kep far apart). Also, the eps and max_iter kwargs are a bit deceiving. Usually, the
        algorithm reaches a minimum stress after only the 2 or 3 iterations, and after that
        starts increasing again, ie the error becomes -ve and the algorithm exits. If
        max_iter is anything greater than about 3, it'll never be reached. If you provide a
        -ve eps however, this forces the algorithm to exit only once it reaches max_iter.
        The final stress value will be higher than the minimum, but at least it actually
        becomes stable. You can see this by setting verbose=2. Stable non-minimum stress
        values seem to provide more consistent neuron sorting across runs ("inits" in
        sklearn's language) than when simply exiting at minimum stress, but I'm not all that
        certain.
        """
        ## TODO: try Isomap instead
        from sklearn.manifold import MDS
        self.calc()
        sim = copy(self.corrs) # similarities, 1D array of length npairs
        npairs = len(sim)
        N = len(self.nids)
        assert npairs == N * (N-1) / 2 # sanity check
        # scale, might not be necessary, although -ve values might be bad:
        sim -= sim.min()
        sim /= sim.max()
        dissim = 1 - sim # dissimilarities
        # maybe keep all values well above 0, MDS ignores 0 values?
        dissim += 1e-5
        ui = np.triu_indices(N, 1) # upper triangle indices
        li = np.tril_indices(N, -1) # lower triangle indices
        dissimm = np.zeros((N, N)) # dissimilarity matrix, 0s on diagonal
        dissimm[ui] = dissim # fill upper triangle, which is filled row major, same as corrs
        dissimm[li] = dissimm.T[li] # make symmetric by filling lower triangle
        mds = MDS(n_components=1, metric=metric, n_init=n_init, max_iter=max_iter,
                  verbose=verbose, eps=eps, n_jobs=n_jobs, dissimilarity='precomputed')
        pos = mds.fit_transform(dissimm, init=init)
        print('lowest stress: %s' % mds.stress_)
        #print('pos:')
        #print(pos.ravel())
        sortis = pos.ravel().argsort()
        #print('sortis:')
        #print(sortis)
        norder = np.asarray(self.nids)[sortis]
        #print('sorted nids:')
        #print(norder)
        return norder

    def pair_laminarity(self, nids, pairs, inclusive=False):
        """Color cell pairs according to whether they're superficial, deep, or other. If
        inclusive, label a pair as superficial if *either* of the cells are superficial. Ditto
        for deep. This means many pairs will be counted as both superficial and deep.
        Return RGB colours and indices into self.pairs"""
        # y positions of all nids:
        ys = np.array([ self.r.n[nid].pos[1] for nid in nids ])
        supis, midis, deepis = laminarity(ys)
        npairs = len(pairs)
        c = np.empty((npairs, 3), dtype=float) # color RGB array
        cc = mpl.colors.colorConverter
        REDRGB = cc.to_rgb('r')
        GREENRGB = cc.to_rgb('g')
        BLUERGB = cc.to_rgb('b')
        YELLOWRGB = cc.to_rgb('y')
        c[:] = YELLOWRGB # init to yellow, other pairs remain yellow
        if inclusive:
            for i, (ni0, ni1) in enumerate(pairs):
                if supis[ni0] or supis[ni1]:
                    c[i] = REDRGB # at least one cell is superficial
                if midis[ni0] or midis[ni1]:
                    c[i] = GREENRGB # at least one cell is middle
                if deepis[ni0] or deepis[ni1]:
                    c[i] = BLUERGB # at least one cell is deep
        else:
            for i, (ni0, ni1) in enumerate(pairs):
                if supis[ni0] and supis[ni1]:
                    c[i] = REDRGB # both cells are superficial
                if midis[ni0] and midis[ni1]:
                    c[i] = GREENRGB # both cells are middle
                if deepis[ni0] and deepis[ni1]:
                    c[i] = BLUERGB # both cells are deep
        # overwrite boolean neuron indices with boolean pair indices:
        supis, = np.where((c == REDRGB).all(axis=1))
        midis, = np.where((c == GREENRGB).all(axis=1))
        deepis, = np.where((c == BLUERGB).all(axis=1))
        otheris, = np.where((c == YELLOWRGB).all(axis=1))
        return c, supis, midis, deepis, otheris

    def shifts(self, start=-5000, stop=5000, step=50, shiftcorrect=True, figsize=(7.5, 6.5)):
        """Plot shift-corrected, or just shifted, median pairwise spike correlations of all
        cell pairs as a function of shifts, from start to stop in steps of step ms"""
        assert step > 0
        if stop % step == 0:
            stop += step # make stop end inclusive
        assert start < stop
        shifts = np.arange(start, stop, step) # shift values, in ms
        uns = get_ipython().user_ns
        self.calc() # run it once here to init self.nids and self.pairs
        c, supis, midis, deepis, otheris = self.pair_laminarity(self.nids, self.pairs)
        nsup, nmid, ndeep, nother = len(supis), len(midis), len(deepis), len(otheris)
        allmeds = np.zeros(len(shifts)) # medians of all pairs
        supmeds = np.zeros(len(shifts)) # medians of superficial pairs
        midmeds = np.zeros(len(shifts)) # medians of middle pairs
        deepmeds = np.zeros(len(shifts)) # medians of deep pairs
        othermeds = np.zeros(len(shifts)) # medians of other pairs
        for shifti, shift in enumerate(shifts):
            # calculate corrs for each shift
            if shiftcorrect:
                self.shiftcorrect = shift
            else:
                self.shift = shift
            self.calc()
            allmeds[shifti] = np.median(self.corrs)
            # check for empty *is, which raise FloatingPointErrors in np.median:
            if nsup: supmeds[shifti] = np.median(self.corrs[supis])
            if nmid: midmeds[shifti] = np.median(self.corrs[midis])
            if ndeep: deepmeds[shifti] = np.median(self.corrs[deepis])
            if nother: othermeds[shifti] = np.median(self.corrs[otheris])
            print '%d,' % shift, # no newline
        print # newline
        self.clear_codes() # free memory
        f = pl.figure(figsize=figsize)
        a = f.add_subplot(111)
        a.plot(shifts, allmeds, 'e-o', mec='e', ms=3, label='all')
        if nsup: a.plot(shifts, supmeds, 'r-o', mec='r', ms=3, label='superficial')
        if nmid: a.plot(shifts, midmeds, 'g-o', mec='g', ms=3, label='middle')
        if ndeep: a.plot(shifts, deepmeds, 'b-o', mec='b', ms=3, label='deep')
        if nother: a.plot(shifts, othermeds, 'y-o', mec='y', ms=3, label='other')
        # underplot horizontal line at y=0:
        a.axhline(y=0, c='e', ls='--', marker=None)
        a.set_xlim(shifts[0], shifts[-1]) # override any MPL smarts
        if shiftcorrect:
            a.set_xlabel("shift correction (ms)")
            a.set_ylabel("median shift-corrected correlation coefficient")
            pos = 0.99, 0.01 # put info text in bottom right
            verticalalignment = 'bottom'
            legendloc = 'lower left'
        else:
            a.set_xlabel("shift (ms)")
            a.set_ylabel("median shifted correlation coefficient")
            verticalalignment = 'top'
            pos = 0.99, 0.99 # put info text in top right
            legendloc = 'upper left'
        titlestr = lastcmd()
        gcfm().window.setWindowTitle(titlestr)
        a.set_title(titlestr)
        # add info text to top/bottom right of plot:
        uns = get_ipython().user_ns
        a.text(pos[0], pos[1], '%s\n'
                               'tres = %d ms\n'
                               'phase = %d deg\n'
                               'R = %r um\n'
                               'minrate = %.2f Hz\n'
                               'nneurons = %d\n'
                               'npairs = %d\n'
                               'sup = %r um\n'
                               'mid = %r um\n'
                               'deep = %r um\n'
                               'dt = %d min'
                               % (self.r.name, uns['CODETRES']//1000, uns['CODEPHASE'],
                                  self.R, uns['MINRATE'], len(self.nids), self.npairs,
                                  uns['SUPRANGE'], uns['MIDRANGE'], uns['DEEPRANGE'],
                                  intround(self.r.dtmin)),
                               transform=a.transAxes,
                               horizontalalignment='right',
                               verticalalignment=verticalalignment)
        # add legend:
        a.legend(loc=legendloc, markerscale=2.0, handletextpad=0.5)
        f.tight_layout(pad=0.3) # crop figure to contents
        self.f = f
        return self

    def pdf(self, crange=[-0.05, 0.25], figsize=(7.5, 6.5), limitstats=True,
            nbins=30, density=True):
        """Plot PDF of pairwise spike correlations. If limitstats, the stats displayed
        exclude any corr values that fall outside of crange"""
        self.calc()
        nbins = max(nbins, 2*intround(np.sqrt(self.npairs)))
        self.nbins = nbins
        self.density = density

        # figure out the bin edges:
        if crange != None:
            bins = np.linspace(start=crange[0], stop=crange[1], num=self.nbins,
                               endpoint=True)
        else: # let np.histogram() figure out the bin edges
            bins = self.nbins
        self.n, self.c = np.histogram(self.corrs, bins=bins, density=density)
        binwidth = self.c[1] - self.c[0] # take width of first bin in self.c

        # self.n and self.c are the full values, potentially constrained n and c values
        # are what are reported and plotted:
        if limitstats:
            corrs = self.corrs[(self.corrs >= crange[0]) * (self.corrs <= crange[1])]
            n, c = np.histogram(corrs, bins=bins, density=density)
        else:
            corrs = self.corrs
            n = self.n
            c = self.c
        self.mean = np.mean(corrs)
        self.median = np.median(corrs)
        argmode = n.argmax()
        self.mode = c[argmode] + binwidth / 2 # middle of tallest bin
        self.stdev = np.std(corrs)

        f = pl.figure(figsize=figsize)
        a = f.add_subplot(111)
        # omit last right edge in c:
        a.bar(left=c[:-1], height=n, width=binwidth, bottom=0, color='k', ec='k')
        if crange != None:
            a.set_xlim(crange)
        titlestr = lastcmd()
        gcfm().window.setWindowTitle(titlestr)
        a.set_title(titlestr)
        
        if self.density:
            a.set_ylabel('probability density')
        else:
            a.set_ylabel('count')
        a.set_xlabel('correlation coefficient')
        # add stuff to top right of plot:
        uns = get_ipython().user_ns
        a.text(0.99, 0.99, '%s\n'
                           'mean = %.3f\n'
                           'median = %.3f\n'
                           'mode = %.3f\n'
                           'stdev = %.3f\n'
                           'tres = %d ms\n'
                           'phase = %d deg\n'
                           'R = %r um\n'
                           'minrate = %.2f Hz\n'
                           'nneurons = %d\n'
                           'npairs = %d\n'
                           'dt = %d min'
                           % (self.r.name, self.mean, self.median, self.mode, self.stdev,
                              uns['CODETRES']//1000, uns['CODEPHASE'], self.R, uns['MINRATE'],
                              len(self.nids), self.npairs, intround(self.r.dtmin)),
                           transform = a.transAxes,
                           horizontalalignment='right',
                           verticalalignment='top')
        f.tight_layout(pad=0.3) # crop figure to contents
        self.f = f
        return self

    def sort(self, figsize=(7.5, 6.5)):
        """Plot pairwise spike correlations in decreasing order"""
        self.calc()
        f = pl.figure(figsize=figsize)
        a = f.add_subplot(111)
        corrs = self.corrs
        sortis = corrs.argsort()[::-1] # indices to get corrs in decreasing order
        corrs = corrs[sortis] # corrs in decreasing order
        pairs = self.pairs[sortis] # pairs in decreasing corrs order
        npairs = len(pairs)

        # color pairs according to whether they're superficial, deep, or other:
        c, supis, midis, deepis, otheris = self.pair_laminarity(self.nids, pairs)
        # get percentages of each:
        psup = intround(len(supis) / npairs * 100)
        pmid = intround(len(midis) / npairs * 100)
        pdeep = intround(len(deepis) / npairs * 100)
        pother = intround(len(otheris) / npairs * 100)
        
        a.scatter(np.arange(self.npairs), corrs, marker='o', c=c, edgecolor='none',
                  s=10, zorder=100)
        a.set_xlim(left=-10)
        a.set_ylim(bottom=-0.05)
        # underplot horizontal line at y=0:
        a.axhline(y=0, c='e', ls='--', marker=None)
        a.set_xlabel("pair index")
        a.set_ylabel("correlation coefficient")
        titlestr = lastcmd()
        gcfm().window.setWindowTitle(titlestr)
        a.set_title(titlestr)
        self.mean = np.mean(corrs)
        self.median = np.median(corrs)
        self.stdev = np.std(corrs)
        # add stuff to top right of plot:
        uns = get_ipython().user_ns
        a.text(0.99, 0.99, '%s\n'
                           'mean = %.3f\n'
                           'median = %.3f\n'
                           'stdev = %.3f\n'
                           'tres = %d ms\n'
                           'phase = %d deg\n'
                           'R = %r um\n'
                           'minrate = %.2f Hz\n'
                           'nneurons = %d\n'
                           'npairs = %d\n'
                           'sup = %r um\n'
                           'mid = %r um\n'
                           'deep = %r um\n'
                           'dt = %d min'
                           % (self.r.name, self.mean, self.median, self.stdev,
                              uns['CODETRES']//1000, uns['CODEPHASE'], self.R,
                              uns['MINRATE'], len(self.nids), self.npairs,
                              uns['SUPRANGE'], uns['MIDRANGE'], uns['DEEPRANGE'],
                              intround(self.r.dtmin)),
                           transform = a.transAxes,
                           horizontalalignment='right',
                           verticalalignment='top')
        # make proxy line artists for legend:
        sl = mpl.lines.Line2D([1], [1], color='white', marker='o', mfc='r', mec='r')
        ml = mpl.lines.Line2D([1], [1], color='white', marker='o', mfc='g', mec='g')
        dl = mpl.lines.Line2D([1], [1], color='white', marker='o', mfc='b', mec='b')
        ol = mpl.lines.Line2D([1], [1], color='white', marker='o', mfc='y', mec='y')
        # add legend:
        a.legend([sl, ml, dl, ol],
                 ['superficial: %d%%' % psup, 'middle: %d%%' % pmid, 'deep: %d%%' % pdeep,
                  'other: %d%%' % pother],
                 numpoints=1, loc='upper center',
                 handlelength=1, handletextpad=0.5, labelspacing=0.1)
        f.tight_layout(pad=0.3) # crop figure to contents
        self.f = f
        return self

    def scat(self, otherrid, nids=None, crange=[-0.05, 0.25], figsize=(7.5, 6.5)):
        """Scatter plot pairwise spike correlations in this recording vs that of
        another recording. If the two recordings are the same, split it in half and scatter
        plot first half against the second half."""
        ## TODO: add interleave flag which generates a sufficiently interleaved, equally sized,
        ## non-overlapping set of tranges to scatter plot against each other, to eliminate
        ## temporal bias inherent in a simple split in time
        r0 = self.r
        tr = r0.tr
        otherr = tr.r[otherrid]
        r1 = otherr
        # make sure they're from the same track, though the above should guarantee it
        assert r0.tr == r1.tr
        if r0 != r1:
            tranges0 = [r0.trange] # use the usual trange for both
            tranges1 = [r1.trange]
            xlabel = 'correlation coefficient (%s)' % r0.name
            ylabel = 'correlation coefficient (%s)' % r1.name
        else: # same recording, split its trange in half
            start, end = r0.trange
            mid = intround(start + r0.dt / 2)
            tranges0 = [(start, mid)]
            tranges1 = [(mid, end)]
            xlabel = 'correlation coefficient (%s, 1st half)' % r0.name
            ylabel = 'correlation coefficient (%s, 2nd half)' % r0.name
        if nids == None:
            if r0 != r1: # find nids active in both recordings
                nids = tr.get_nids([r0.id, r1.id])
            else: # same recording, find nids active during both tranges
                nids0 = r0.get_nids(tranges0)
                nids1 = r1.get_nids(tranges1)
                nids = np.intersect1d(nids0, nids1)

        # given the same nids, calculate corrs for both, constrained to tranges0
        # and tranges1 respectively, and to the torus described by R:
        sc0 = SpikeCorr(recording=r0, tranges=tranges0, nids=nids, R=self.R)
        sc1 = SpikeCorr(recording=r1, tranges=tranges1, nids=nids, R=self.R)
        sc0.calc()
        sc1.calc()
        # just to be sure:
        if sc0.npairs != sc1.npairs or (sc0.pairs != sc1.pairs).any():
            import pdb; pdb.set_trace()
            raise RuntimeError("sc0 and sc1 pairs don't match")
        pairs = sc0.pairs
        npairs = len(pairs)
        corrs0, corrs1 = sc0.corrs, sc1.corrs
        
        # color pairs according to whether they're superficial, middle, deep, or other
        c, supis, midis, deepis, otheris = self.pair_laminarity(nids, pairs)
        # get percentages of each:
        psup = intround(len(supis) / npairs * 100)
        pmid = intround(len(midis) / npairs * 100)
        pdeep = intround(len(deepis) / npairs * 100)
        pother = intround(len(otheris) / npairs * 100)
        supcorrs0, supcorrs1 = corrs0[supis], corrs1[supis]
        midcorrs0, midcorrs1 = corrs0[midis], corrs1[midis]
        deepcorrs0, deepcorrs1 = corrs0[deepis], corrs1[deepis]
        othercorrs0, othercorrs1 = corrs0[otheris], corrs1[otheris]
        
        # create the scatter plot:
        f = pl.figure(figsize=figsize)
        a = f.add_subplot(111)
        lim = crange
        if crange == None:
            # fit to nearest 0.05 encompassing all corr values on both axes:
            xlim = min(corrs0), max(corrs0)
            ylim = min(corrs1), max(corrs1)
            xlim = [ roundto(val, 0.05) for val in xlim ]
            ylim = [ roundto(val, 0.05) for val in ylim ]
            minlim = min(xlim[0], ylim[0])
            maxlim = max(xlim[1], ylim[1])
            lim = minlim, maxlim

        a.plot(lim, lim, c='e', ls='--', marker=None) # y=x line
        if psup > 0:
            a.errorbar(supcorrs0.mean(), supcorrs1.mean(),
                       xerr=supcorrs0.std(), yerr=supcorrs1.std(), color='r')
        if pmid > 0:
            a.errorbar(midcorrs0.mean(), midcorrs1.mean(),
                       xerr=midcorrs0.std(), yerr=midcorrs1.std(), color='g')
        if pdeep > 0:
            a.errorbar(deepcorrs0.mean(), deepcorrs1.mean(),
                       xerr=deepcorrs0.std(), yerr=deepcorrs1.std(), color='b')
        if pother > 0:
            a.errorbar(othercorrs0.mean(), othercorrs1.mean(),
                       xerr=othercorrs0.std(), yerr=othercorrs1.std(), color='y')
        a.scatter(corrs0, corrs1, marker='o', c=c, edgecolor='none', s=10, zorder=100)
        a.set_xlim(lim)
        a.set_ylim(lim)
        a.set_xlabel(xlabel)
        a.set_ylabel(ylabel)
        titlestr = lastcmd()
        gcfm().window.setWindowTitle(titlestr)
        a.set_title(titlestr)
        # add stuff to top left of plot:
        uns = get_ipython().user_ns
        a.text(0.01, 0.99, 'tres = %d ms\n'
                           'phase = %d deg\n'
                           'R = %r um\n'
                           'minrate = %.2f Hz\n'
                           'nneurons = %d\n'
                           'npairs = %d\n'
                           'sup = %r um\n'
                           'mid = %r um\n'
                           'deep = %r um\n'
                           'r%s.dt = %d min\n'
                           'r%s.dt = %d min'
                           % (uns['CODETRES']//1000, uns['CODEPHASE'], self.R, uns['MINRATE'],
                              len(nids), sc0.npairs,
                              uns['SUPRANGE'], uns['MIDRANGE'], uns['DEEPRANGE'],
                              r0.id, intround(r0.dtmin), r1.id, intround(r1.dtmin)),
                           transform = a.transAxes,
                           horizontalalignment='left',
                           verticalalignment='top')
        # make proxy artists for legend:
        sl = mpl.lines.Line2D([1], [1], color='white', marker='o', mfc='r', mec='r')
        ml = mpl.lines.Line2D([1], [1], color='white', marker='o', mfc='g', mec='g')
        dl = mpl.lines.Line2D([1], [1], color='white', marker='o', mfc='b', mec='b')
        ol = mpl.lines.Line2D([1], [1], color='white', marker='o', mfc='y', mec='y')
        # add legend:
        a.legend([sl, ml, dl, ol],
                 ['superficial: %d%%' % psup, 'middle: %d%%' % pmid, 'deep: %d%%' % pdeep,
                  'other: %d%%' % pother],
                 numpoints=1, loc='lower right',
                 handlelength=1, handletextpad=0.5, labelspacing=0.1)
        f.tight_layout(pad=0.3) # crop figure to contents
        self.f = f
        return self

    def sep(self, figsize=(7.5, 6.5)):
        """Plot pairwise spike correlations as a f'n of pair separation"""
        ## TODO: histogram sc values in say 200 um bins, and plot line with stdev errorbars
        ## vs time, in black
        self.calc()
        f = pl.figure(figsize=figsize)
        a = f.add_subplot(111)
        nids = self.nids
        corrs = self.corrs
        pairs = self.pairs
        npairs = len(pairs)
        n = self.r.n

        # color pairs according to whether they're superficial, middle, deep, or other:
        c, supis, midis, deepis, otheris = self.pair_laminarity(self.nids, pairs)
        # get percentages of each:
        psup = intround(len(supis) / npairs * 100)
        pmid = intround(len(midis) / npairs * 100)
        pdeep = intround(len(deepis) / npairs * 100)
        pother = intround(len(otheris) / npairs * 100)
        supcorrs = corrs[supis]
        midcorrs = corrs[midis]
        deepcorrs = corrs[deepis]
        othercorrs = corrs[otheris]

        # pairwise separations:
        seps = np.zeros(npairs)
        for i, pair in enumerate(pairs):
            nid0, nid1 = nids[pair[0]], nids[pair[1]]
            seps[i] = dist(n[nid0].pos, n[nid1].pos)
        supseps = seps[supis]
        midseps = seps[midis]
        deepseps = seps[deepis]
        otherseps = seps[otheris]

        if psup > 0:
            a.errorbar(supseps.mean(), supcorrs.mean(),
                       xerr=supseps.std(), yerr=supcorrs.std(), color='r', ls='--')
        if pmid > 0:
            a.errorbar(midseps.mean(), midcorrs.mean(),
                       xerr=midseps.std(), yerr=midcorrs.std(), color='g', ls='--')
        if pdeep > 0:
            a.errorbar(deepseps.mean(), deepcorrs.mean(),
                       xerr=deepseps.std(), yerr=deepcorrs.std(), color='b', ls='--')
        if pother > 0:
            a.errorbar(otherseps.mean(), othercorrs.mean(),
                       xerr=otherseps.std(), yerr=othercorrs.std(), color='y', ls='--')
        a.scatter(seps, corrs, marker='o', c=c, edgecolor='none', s=10, zorder=100)
        a.set_xlim(left=0)
        # underplot horizontal line at y=0:
        a.axhline(y=0, c='e', ls='--', marker=None)
        a.set_xlabel("pair separation (um)")
        a.set_ylabel("spike correlation")
        titlestr = lastcmd()
        gcfm().window.setWindowTitle(titlestr)
        a.set_title(titlestr)
        # add stuff to top right of plot:
        uns = get_ipython().user_ns
        a.text(0.99, 0.99, '%s\n'
                           'tres = %d ms\n'
                           'phase = %d deg\n'
                           'R = %r um\n'
                           'minrate = %.2f Hz\n'
                           'nneurons = %d\n'
                           'npairs = %d\n'
                           'sup = %r um\n'
                           'mid = %r um\n'
                           'deep = %r um\n'
                           'dt = %d min'
                           % (self.r.name, uns['CODETRES']//1000, uns['CODEPHASE'], self.R,
                              uns['MINRATE'], len(self.nids), npairs,
                              uns['SUPRANGE'], uns['MIDRANGE'], uns['DEEPRANGE'],
                              intround(self.r.dtmin)),
                           transform=a.transAxes,
                           horizontalalignment='right',
                           verticalalignment='top')
        # make proxy artists for legend:
        sl = mpl.lines.Line2D([1], [1], color='white', marker='o', mfc='r', mec='r')
        ml = mpl.lines.Line2D([1], [1], color='white', marker='o', mfc='g', mec='g')
        dl = mpl.lines.Line2D([1], [1], color='white', marker='o', mfc='b', mec='b')
        ol = mpl.lines.Line2D([1], [1], color='white', marker='o', mfc='y', mec='y')
        # add legend:
        a.legend([sl, ml, dl, ol],
                 ['superficial: %d%%' % psup, 'middle: %d%%' % pmid, 'deep: %d%%' % pdeep,
                  'other: %d%%' % pother],
                 numpoints=1, loc='upper center',
                 handlelength=1, handletextpad=0.5, labelspacing=0.1)
        f.tight_layout(pad=0.3) # crop figure to contents
        self.f = f
        return self

    def sct(self, method='weighted mean', inclusive=False):
        """Calculate pairwise spike correlations for each type of laminarity as a function of
        time. method can be 'weightedmean', 'mean', 'median', 'max', 'min' or 'all'"""
        uns = get_ipython().user_ns
        if self.width == None:
            self.width = intround(uns['SCWIDTH'] * 1000000) # convert from sec to us
        if self.tres == None:
            self.tres = intround(uns['SCTRES'] * 1000000) # convert from sec to us
        self.calc()
        allis = np.arange(self.npairs) # all indices into self.pairs
        c, supis, midis, deepis, otheris = self.pair_laminarity(self.nids, self.pairs,
                                                                inclusive=inclusive)
        laminarcorrs = []
        laminarnpairs = []
        for pairis in (allis, supis, midis, deepis, otheris):
            npairs = len(pairis)
            if npairs == 0:
                laminarcorrs.append(np.zeros(len(self.tranges)))
                laminarnpairs.append(npairs)
                continue
            corrs = self.corrs[pairis] # npairs x ntranges
            if method.startswith('weighted'):
                # weight each pair by its normalized ON count per trange
                counts = self.counts[pairis] # npairs * ntranges
                totalcounts = counts.sum(axis=0) # len(ntranges)
                # avoid div by 0, counts at such timepoints will be uniformly 0 anyway:
                zcountis = totalcounts == 0 # trange indices where totalcounts are 0
                totalcounts[zcountis] = 1
                weights = counts / totalcounts # npairs x ntranges
            if method == 'weighted mean':
                # sum over all weighted pairs:
                corrs = (corrs * weights).sum(axis=0) # len(ntranges)
            elif method == 'weighted median': # not entirely sure this is right:
                corrs = np.median(corrs * weights, axis=0) * self.npairs
            elif method == 'mean':
                corrs = corrs.mean(axis=0)
            elif method == 'median':
                corrs = np.median(corrs, axis=0)
            elif method == 'max':
                corrs = corrs.max(axis=0)
            elif method == 'min':
                corrs = corrs.min(axis=0)
            elif method == 'all':
                corrs = corrs.T # need transpose for some reason when plotting multiple traces
            laminarcorrs.append(corrs)
            laminarnpairs.append(npairs)
        laminarcorrs = np.vstack(laminarcorrs)
        laminarnpairs = np.array(laminarnpairs)
        # get midpoint of each trange, convert from us to sec:
        t = self.tranges.mean(axis=1) / 1000000
        ylabel = method + ' spike correlations'
        return laminarcorrs, laminarnpairs, t, ylabel

    def plot(self, method='weighted mean', inclusive=False, figsize=(20, 6.5)):
        """Plot pairwise spike correlations as a function of time. method can be
        'weightedmean', 'mean', 'median', 'max' or 'min'"""
        corrs, npairs, t, ylabel = self.sct(method=method, inclusive=inclusive)
        f = pl.figure(figsize=figsize)
        a = f.add_subplot(111)
        # underplot horizontal line at y=0:
        a.axhline(y=0, c='e', ls='--', marker=None)
        #if corrs.ndim == 2:
        #    a.plot(t, corrs) # auto colours
        # plot according to laminarity:
        a.plot(t, corrs[0], 'e.-', label='all (%d)' % npairs[0])
        a.plot(t, corrs[1], 'r.-', label='superficial (%d)' % npairs[1])
        a.plot(t, corrs[2], 'g.-', label='middle (%d)' % npairs[2])
        a.plot(t, corrs[3], 'b.-', label='deep (%d)' % npairs[3])
        a.plot(t, corrs[4], 'y.-', label='other (%d)' % npairs[4], zorder=0)
        a.set_xlabel("time (sec)")
        ylabel = ylabel + " (%d pairs)" % self.npairs
        a.set_ylabel(ylabel)
        # limit plot to duration of acquistion, in sec:
        t0, t1 = np.asarray(self.r.trange) / 1000000
        ymax = max([0.1, corrs[[0,1,2,3]].max()])
        ymin = min([0.0, corrs[[0,1,2,3]].min()])
        a.set_ylim(ymin, ymax)
        a.set_xlim(t0, t1)
        #a.autoscale(axis='x', enable=True, tight=True)
        # turn off annoying "+2.41e3" type offset on x axis:
        formatter = mpl.ticker.ScalarFormatter(useOffset=False)
        a.xaxis.set_major_formatter(formatter)
        titlestr = lastcmd()
        gcfm().window.setWindowTitle(titlestr)
        a.set_title(titlestr)
        uns = get_ipython().user_ns
        a.text(0.998, 0.99,
               '%s\n'
               'sup = %r um\n'
               'mid = %r um\n'
               'deep = %r um'
               % (self.r.name, uns['SUPRANGE'], uns['MIDRANGE'], uns['DEEPRANGE']),
               color='k', transform=a.transAxes,
               horizontalalignment='right', verticalalignment='top')
        a.legend(loc='upper left', handlelength=1, handletextpad=0.5, labelspacing=0.1)
        f.tight_layout(pad=0.3) # crop figure to contents

    def si(self, method='weighted mean', inclusive=False, chani=-1, ratio='L/(L+H)',
           lowband=None, highband=None, sirange=None, figsize=(7.5, 6.5), plot=True):
        """Scatter plot spike correlations vs LFP synchrony index"""
        t0 = time.time()
        # ct are center timepoints:
        corrs, npairs, ct, ylabel = self.sct(method=method, inclusive=inclusive)
        print('sct(t) calc took %.3f sec' % (time.time()-t0))
        t0 = time.time()
        si, sit = self.r.lfp.si(chani=chani, lowband=lowband, highband=highband,
                                width=self.width/1e6, tres=self.tres/1e6,
                                ratio=ratio, plot=False) # sit are also center timepoints
        print('SI(t) calc took %.3f sec' % (time.time()-t0))
        # get common time resolution, si typically has finer temporal resolution than corrs:
        if len(sit) > len(ct):
            siti = sit.searchsorted(ct)
            sitii = siti < len(sit) # prevent right side out of bounds indices into si
            ct = ct[sitii]
            corrs = corrs[:, sitii]
            siti = siti[sitii]
            sit = sit[siti]
            si = si[siti]
        else:
            cti = ct.searchsorted(sit)
            ctii = cti < len(ct) # prevent right side out of bounds indices into corrs
            sit = sit[ctii]
            si = si[ctii]
            cti = cti[ctii]
            ct = ct[cti]
            corrs = corrs[:, cti]

        if not plot:
            return corrs, si # return corrs of all laminarities

        f = pl.figure(figsize=figsize)
        a = f.add_subplot(111)
        ylim = corrs[:5].min(), corrs[:5].max()
        yrange = ylim[1] - ylim[0]
        extra = yrange*0.03 # 3 %
        ylim = ylim[0]-extra, ylim[1]+extra

        # keep only those points whose synchrony index falls within sirange:
        if sirange == None:
            sirange = (0, 1)
        sirange = np.asarray(sirange)
        keepis = (sirange[0] <= si) * (si <= sirange[1]) # boolean index array
        si = si[keepis]
        corrs = corrs[:, keepis]

        # plot linear regressions:
        m0, b0, r0, p0, stderr0 = scipy.stats.linregress(si, corrs[0])
        m1, b1, r1, p1, stderr1 = scipy.stats.linregress(si, corrs[1])
        m2, b2, r2, p2, stderr2 = scipy.stats.linregress(si, corrs[2])
        m3, b3, r3, p3, stderr3 = scipy.stats.linregress(si, corrs[3])
        m4, b4, r4, p4, stderr4 = scipy.stats.linregress(si, corrs[4])
        a.plot(sirange, m0*sirange+b0, 'e--')
        a.plot(sirange, m1*sirange+b1, 'r--')
        a.plot(sirange, m2*sirange+b2, 'g--')
        a.plot(sirange, m3*sirange+b3, 'b--')
        a.plot(sirange, m4*sirange+b4, 'y--', zorder=0)

        # scatter plot corrs vs si, one colour per laminarity:
        a.plot(si, corrs[0], 'e.', label='all (%d), m=%.3f, r=%.3f' % (npairs[0], m0, r0))
        a.plot(si, corrs[1], 'r.', label='superficial (%d), m=%.3f, r=%.3f'
                                         % (npairs[1], m1, r1))
        a.plot(si, corrs[2], 'g.', label='middle (%d), m=%.3f, r=%.3f' % (npairs[2], m2, r2))
        a.plot(si, corrs[3], 'b.', label='deep (%d), m=%.3f, r=%.3f' % (npairs[3], m3, r3))
        a.plot(si, corrs[4], 'y.', label='other (%d), m=%.3f, r=%.3f'
                                         % (npairs[4], m4, r4), zorder=0)
        #a.set_xlim(sirange)
        a.set_xlim(0, 1)
        a.set_ylim(ylim)
        #a.autoscale(enable=True, axis='y', tight=True)
        a.set_xlabel("LFP synchrony index (%s)" % ratio)
        ylabel = ylabel + " (%d pairs)" % self.npairs
        a.set_ylabel(ylabel)
        titlestr = lastcmd()
        gcfm().window.setWindowTitle(titlestr)
        a.set_title(titlestr)
        uns = get_ipython().user_ns
        a.text(0.998, 0.99,
               '%s\n'
               'sup = %r um\n'
               'mid = %r um\n'
               'deep = %r um'
               % (self.r.name, uns['SUPRANGE'], uns['MIDRANGE'], uns['DEEPRANGE']),
               color='k', transform=a.transAxes,
               horizontalalignment='right', verticalalignment='top')
        a.legend(loc='upper left', handlelength=1, handletextpad=0.5, labelspacing=0.1)
        f.tight_layout(pad=0.3) # crop figure to contents

    def mua(self, method='weighted mean', inclusive=False, smooth=False, figsize=(7.5, 6.5)):
        """Scatter plot spike correlations vs multiunit activity"""
        corrs, npairs, ct, ylabel = self.sct(method=method, inclusive=inclusive)
        mua, muat, n = self.r.mua(smooth=smooth, plot=False)
        # keep only MUA of all neurons, throw away laminar MUA information (for now at least):
        mua = mua[0] # 1D array
        # get common time resolution:
        if len(muat) > len(ct):
            muati = muat.searchsorted(ct)
            muatii = muati < len(muat) # prevent right side out of bounds indices into mua
            ct = ct[muatii]
            corrs = corrs[:, muatii]
            muati = muati[muatii]
            muat = muat[muati]
            mua = mua[muati]
        else:
            cti = ct.searchsorted(muat)
            ctii = cti < len(ct) # prevent right side out of bounds indices into corrs
            muat = muat[ctii]
            mua = mua[ctii]
            cti = cti[ctii]
            ct = ct[cti]
            corrs = corrs[:, cti]

        f = pl.figure(figsize=figsize)
        a = f.add_subplot(111)
        ylim = corrs[:5].min(), corrs[:5].max()
        yrange = ylim[1] - ylim[0]
        extra = yrange*0.03 # 3 %
        ylim = ylim[0]-extra, ylim[1]+extra
        muarange = np.array([mua.min(), mua.max()])

        # plot linear regressions:
        m0, b0, r0, p0, stderr0 = scipy.stats.linregress(mua, corrs[0])
        m1, b1, r1, p1, stderr1 = scipy.stats.linregress(mua, corrs[1])
        m2, b2, r2, p2, stderr2 = scipy.stats.linregress(mua, corrs[2])
        m3, b3, r3, p3, stderr3 = scipy.stats.linregress(mua, corrs[3])
        m4, b4, r4, p4, stderr4 = scipy.stats.linregress(mua, corrs[4])
        a.plot(muarange, m0*muarange+b0, 'e--')
        a.plot(muarange, m1*muarange+b1, 'r--')
        a.plot(muarange, m2*muarange+b2, 'g--')
        a.plot(muarange, m3*muarange+b3, 'b--')
        a.plot(muarange, m4*muarange+b4, 'y--', zorder=0)

        # scatter plot corrs vs mua, one colour per laminarity:
        a.plot(mua, corrs[0], 'e.', label='all (%d), m=%.3f, r=%.3f' % (npairs[0], m0, r0))
        a.plot(mua, corrs[1], 'r.', label='superficial (%d), m=%.3f, r=%.3f'
                                          % (npairs[1], m1, r1))
        a.plot(mua, corrs[2], 'g.', label='middle (%d), m=%.3f, r=%.3f' % (npairs[2], m2, r2))
        a.plot(mua, corrs[3], 'b.', label='deep (%d), m=%.3f, r=%.3f' % (npairs[3], m3, r3))
        a.plot(mua, corrs[4], 'y.', label='other (%d), m=%.3f, r=%.3f'
                                          % (npairs[4], m4, r4), zorder=0)
        a.set_ylim(ylim)
        #a.autoscale(enable=True, axis='y', tight=True)
        a.set_xlabel("mean MUA (Hz), %d neurons" % n[0])
        ylabel = ylabel + " (%d pairs)" % self.npairs
        a.set_ylabel(ylabel)
        titlestr = lastcmd()
        gcfm().window.setWindowTitle(titlestr)
        a.set_title(titlestr)
        uns = get_ipython().user_ns
        a.text(0.998, 0.99,
               '%s\n'
               'sup = %r um\n'
               'middle = %r um\n'
               'deep = %r um'
               % (self.r.name, uns['SUPRANGE'], uns['MIDRANGE'], uns['DEEPRANGE']),
               color='k', transform=a.transAxes,
               horizontalalignment='right', verticalalignment='top')
        a.legend(loc='upper left', handlelength=1, handletextpad=0.5, labelspacing=0.1)
        f.tight_layout(pad=0.3) # crop figure to contents


class NeuropyWindow(QtGui.QMainWindow):
    """Base class for all of neuropy's tool windows"""
    def __init__(self, parent=None):
        QtGui.QMainWindow.__init__(self, parent)
        self.maximized = False

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_F11:
            self.toggleMaximized()
        else:
            QtGui.QMainWindow.keyPressEvent(self, event) # pass it on

    def mouseDoubleClickEvent(self, event):
        """Doesn't catch window titlebar doubleclicks for some reason (window manager
        catches them?). Have to doubleclick on a part of the window with no widgets in it"""
        self.toggleMaximized()

    def toggleMaximized(self):
        if not self.maximized:
            self.normalPos, self.normalSize = self.pos(), self.size()
            dw = QtGui.QDesktopWidget()
            rect = dw.availableGeometry(self)
            self.setGeometry(rect)
            self.maximized = True
        else: # restore
            self.resize(self.normalSize)
            self.move(self.normalPos)
            self.maximized = False


class RevCorrWindow(NeuropyWindow):
    def __init__(self, parent=None, title='RevCorrWindow', rfs=None,
                 nids=None, ts=None, scale=2.0):
        NeuropyWindow.__init__(self, parent)
        self.title = title
        self.rfs = rfs
        self.nids = nids
        self.ts = ts
        self.scale = scale # setting to a float will give uneven sized pixels

        cmap = mpl.cm.jet(np.arange(256), bytes=True) # 8 bit RGBA colormap
        #cmap[:, [0, 1, 2, 3]] = cmap[:, [3, 0, 1, 2]] # 8 bit ARGB colormap
        # from Qt docs, sounds like I should be using ARGB format, but seems like
        # RGBA is the format that works in PyQt4
        colortable = cmap.view(dtype=np.uint32).ravel().tolist() # QVector<QRgb> colors 
        layout = QtGui.QGridLayout() # can set vert and horiz spacing
        #layout.setContentsMargins(0, 0, 0, 0) # doesn't seem to do anything

        # place time labels along top
        for ti, t in enumerate(ts):
            label = QtGui.QLabel(str(t))
            layout.addWidget(label, 0, ti+1)
        # plot each row, with its nid label
        for ni, nid in enumerate(nids):
            label = QtGui.QLabel('n'+str(nid)) # nid label on left
            label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            layout.addWidget(label, ni+1, 0)
            rf = rfs[ni]
            for ti, t in enumerate(ts):
                #data = np.uint8(np.random.randint(0, 255, size=(height, width)))
                data = rf[ti]
                width, height = data.shape
                image = QImage(data.data, width, height, QImage.Format_Indexed8)
                image.ndarray = data # hold a ref, prevent gc
                image.setColorTable(colortable)
                image = image.scaled(QSize(scale*width, scale*height)) # scale it
                pixmap = QPixmap.fromImage(image)
                label = QtGui.QLabel()
                label.setPixmap(pixmap)
                layout.addWidget(label, ni+1, ti+1) # can also control alignment

        mainwidget = QtGui.QWidget(self)
        mainwidget.setLayout(layout)

        scrollarea = QtGui.QScrollArea()
        scrollarea.setWidget(mainwidget)

        self.setCentralWidget(scrollarea)
        self.setWindowTitle(title)
        #palette = QPalette(QColor(255, 255, 255))
        #self.setPalette(palette) # set white background, or perhaps more

'''
class ReceptiveFieldFrame(wx.Frame):
    """A wx.Frame for plotting a scrollable 2D grid of receptive fields, with neuron and time labels.
    rfs is a list of (nt, width, height) sized receptive fields of uint8 RGB data, one per neuron"""
    def __init__(self, parent=None, id=-1, title='ReceptiveFieldFrame', rfs=None,
                 neurons=None, t=None, scale=2.0):
        self.rfs = rfs
        self.neurons = neurons
        self.t = t
        self.title = title
        wx.Frame.__init__(self, parent=parent, id=id, title=title, style=wx.DEFAULT_FRAME_STYLE)
        self.panel = wx.ScrolledWindow(self, -1, style=wx.TAB_TRAVERSAL)

        self.bitmaps = {}
        for ni, n in enumerate(self.neurons):
            self.bitmaps[ni] = {}
            for ti, t in enumerate(self.t):
                rf = self.rfs[ni][ti]
                im = wx.ImageFromData(width=rf.shape[0], height=rf.shape[1], data=rf.data) # expose rf as databuffer
                im = im.Scale(width=im.GetWidth()*scale, height=im.GetHeight()*scale)
                self.bitmaps[ni][t] = wx.StaticBitmap(parent=self.panel, bitmap=im.ConvertToBitmap())

        #self.Bind(wx.EVT_PAINT, self.OnPaint)
        #self.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)
        self.__set_properties()
        self.__do_layout()
    """
    def OnPaint(self, event):
        #self.canvas.draw()
        event.Skip()
    """
    def OnMouseWheel(self, event):
        """This could be useful..."""
        pass

    def __set_properties(self):
        self.SetTitle(self.title)
        self.panel.SetBackgroundColour(wx.Colour(255, 255, 255))
        self.panel.SetScrollRate(10, 10)

    def __do_layout(self):
        sizer_1 = wx.GridSizer(1, 1, 0, 0)
        grid_sizer_1 = wx.FlexGridSizer(rows=len(self.neurons)+1, cols=len(self.t)+1, vgap=2, hgap=2) # add an extra row and column for the text labels
        grid_sizer_1.Add((1, 1), 0, wx.ADJUST_MINSIZE, 0) # spacer in top left corner
        for t in self.t:
            grid_sizer_1.Add(wx.StaticText(self.panel, -1, "%sms" % t), 0, wx.ADJUST_MINSIZE, 0) # text row along top
        for ni, n in enumerate(self.neurons):
            grid_sizer_1.Add(wx.StaticText(self.panel, -1, "n%d" % n.id), 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL|wx.ADJUST_MINSIZE, 0) # text down left side
            for t in self.t:
                grid_sizer_1.Add(self.bitmaps[ni][t], 1, wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL, 0)
        self.panel.SetAutoLayout(True)
        self.panel.SetSizer(grid_sizer_1)
        grid_sizer_1.Fit(self.panel)
        #grid_sizer_1.SetSizeHints(self.panel) # prevents the panel from being resized to something smaller than the above fit size
        """
        # might be a more direct way to set these:
        for rowi in range(1, len(self.ns)+1):
            print 'rowi:', rowi
            grid_sizer_1.AddGrowableRow(rowi)
        for coli in range(1, len(self.ts)+1):
            print 'coli:', coli
            grid_sizer_1.AddGrowableCol(coli)
        """
        sizer_1.Add(self.panel, 1, wx.ADJUST_MINSIZE|wx.EXPAND, 0)
        self.SetAutoLayout(True)
        self.SetSizer(sizer_1)
        sizer_1.Fit(self)
        #sizer_1.SetSizeHints(self) # prevents the frame from being resized to something smaller than the above fit size
        self.Layout()


class NetstateReceptiveFieldFrame(ReceptiveFieldFrame):
    """A wx.Frame for plotting a scrollable 2D grid of netstate receptive fields, with netstate and time labels.
    rfs is a list of (nt, width, height) sized receptive fields of uint8 RGB data, one per netstate"""
    def __init__(self, parent=None, id=-1, title='NetstateReceptiveFieldFrame',
                 rfs=None, intcodes=None, t=None, scale=2.0):
        self.rfs = rfs
        self.intcodes = tolist(intcodes)
        self.t = t
        self.title = title
        wx.Frame.__init__(self, parent=parent, id=id, title=title, style=wx.DEFAULT_FRAME_STYLE)
        self.panel = wx.ScrolledWindow(self, -1, style=wx.TAB_TRAVERSAL)
        self.bitmaps = {}
        for ii, i in enumerate(self.intcodes):
            self.bitmaps[ii] = {}
            for ti, t in enumerate(self.t):
                rf = self.rfs[ii][ti]
                im = wx.ImageFromData(width=rf.shape[0], height=rf.shape[1], data=rf.data) # expose rf as databuffer
                im = im.Scale(width=im.GetWidth()*scale, height=im.GetHeight()*scale)
                self.bitmaps[ii][t] = wx.StaticBitmap(parent=self.panel, bitmap=im.ConvertToBitmap())
        self.__set_properties()
        self.__do_layout()

    def __set_properties(self):
        self.SetTitle(self.title)
        self.panel.SetBackgroundColour(wx.Colour(255, 255, 255))
        self.panel.SetScrollRate(10, 10)

    def __do_layout(self):
        sizer_1 = wx.GridSizer(1, 1, 0, 0)
        grid_sizer_1 = wx.FlexGridSizer(rows=len(self.intcodes)+1, cols=len(self.t)+1, vgap=2, hgap=2) # add an extra row and column for the text labels
        grid_sizer_1.Add((1, 1), 0, wx.ADJUST_MINSIZE, 0) # spacer in top left corner
        for t in self.t:
            grid_sizer_1.Add(wx.StaticText(self.panel, -1, "%sms" % t), 0, wx.ADJUST_MINSIZE, 0) # text row along top
        for ii, i in enumerate(self.intcodes):
            grid_sizer_1.Add(wx.StaticText(self.panel, -1, "ns%d" % i), 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL|wx.ADJUST_MINSIZE, 0) # text down left side
            for t in self.t:
                grid_sizer_1.Add(self.bitmaps[ii][t], 1, wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL, 0)
        self.panel.SetAutoLayout(True)
        self.panel.SetSizer(grid_sizer_1)
        grid_sizer_1.Fit(self.panel)
        sizer_1.Add(self.panel, 1, wx.ADJUST_MINSIZE|wx.EXPAND, 0)
        self.SetAutoLayout(True)
        self.SetSizer(sizer_1)
        sizer_1.Fit(self)
        self.Layout()
'''

class Ising(object):
    """Maximum entropy Ising model"""
    def __init__(self, means, pairmeans, algorithm='CG'):
        """means is a list of mean activity values [-1 to 1] for each neuron code.
        pairmeans is list of products of activity values for all pairs of neuron codes.
        'Returns a maximum-entropy (exponential-form) model on a discrete sample space'
            -- scipy.maxent.model
        """
        from scipy import maxentropy

        # why are the abs values of these so big, shouldn't they be near 0?:
        #print 'means:\n', means
        #print 'pairmeans:\n', pairmeans

        nbits = len(means)
        npairs = len(pairmeans)
        assert npairs == nCr(nbits, 2) # sanity check
        self.intsamplespace = range(0, 2**nbits)
        table = getbinarytable(nbits=nbits) # words are in the columns, MSB at bottom row
        # all possible binary words (each is MSB to LSB), as arrays of 0s and 1s:
        self.binsamplespace = np.array([ table[::-1, wordi] for wordi in range(0, 2**nbits) ])
        self.samplespace = self.binsamplespace * 2 - 1 # convert 0s to -1s
        # return the i'th bit (LSB to MSB) of binary word x,
        # have to do i=i to statically assign value (gets around scope closure problem):
        f1s = [ lambda x, i=i: x[-1-i] for i in range(0, nbits) ]
        # return product of the i'th and j'th bit (LSB to MSB) of binary word
        f2s = []
        pairmeansi = 0
        for i in range(0, nbits):
            for j in range(i+1, nbits):
                if pairmeans[pairmeansi] != None: # None indicates we should ignore this pair
                    f2s.append(lambda x, i=i, j=j: x[-1-i] * x[-1-j])
                pairmeansi += 1
        #f2s = [ lambda x, i=i, j=j: x[-1-i] * x[-1-j] for i in range(0, nbits)
        #        for j in range(i+1, nbits) if pairmeans[i*nbits+j-1] != None ]
        f = np.concatenate((f1s, f2s))
        self.model = maxentropy.model(f, self.samplespace)
        #self.model.mindual = -10000
        #self.model.log = None # needed to make LBFGSB algorithm work
        # Now set the desired feature expectations
        means = np.asarray(means)
        pairmeans = np.asarray(pairmeans) # if it has Nones, it's an object array
        # remove the Nones, convert to list to get rid of object array, then convert
        # back to array to get a normal, non-object array (probably a float64 array):
        pairmeans = np.asarray(list(pairmeans[pairmeans != [None]]))
        npairs = len(pairmeans) # update npairs
        # add the one half in front of each coefficient, not too sure if
        # this should go here! causes convergence problems:
        #pairmeans /= 2.0
        K = np.concatenate((means, pairmeans))
        self.model.verbose = False

        # Fit the model
        """this has problems in scipy 0.9.0 and 0.10.1 but not 0.5.2. Raises error:
        
        "ValueError: operands could not be broadcast together with shapes (1024) (55)"

        This has to do with the call in model.logpmf() in maxentropy.py of maxentutils.py's
        innerprodtranspose(), which has this code in 0.5.2 around line 361:

            elif sparse.isspmatrix(A):
        return A.rmatvec(v).transpose()

        but was changed to this code in 0.9.0 and later:

        elif sparse.isspmatrix(A):
            return (A.conj().transpose() * v).transpose()

        which I guess returns an array of 1024 instead of the expected 55 (10 means plus 10
        choose 2 == 45 pairmeans). So maybe there's something wrong with this change that
        was made in scipy 0.9.0. Don't know about scipy 0.6.0 through 0.8.0 because I can't
        get any of those to compile without errors.
        """
        self.model.fit(K, algorithm=algorithm)

        self.hi = self.model.params[0:nbits]
        self.Jij = self.model.params[nbits:nbits+npairs]
        self.p = self.model.probdist()
        # sanity checks:
        assert (len(self.hi), len(self.Jij), len(self.p)) == (nbits, npairs, 2**nbits)
        #print 'means:', means
        #print 'pairmeans:', pairmeans
        #print '%d iters,' % self.model.iters
        #print 'hi:', self.hi.__repr__()
        #print 'Jij:', self.Jij.__repr__()

        '''
        # Output the distribution
        print "\nFitted model parameters are:\n" + str(self.model.params)
        print "\nFitted distribution is:"
        for j in range(len(self.model.samplespace)):
            x = np.array(self.model.samplespace[j])
            x = (x+1)/2 # convert from -1s and 1s back to 0s and 1s
            print '\tx:%s, p(x):%s' % (x, p[j])
        '''
        '''
        # Now show how well the constraints are satisfied:
        print
        print "Desired constraints:"
        print "\tp['dans'] + p['en'] = 0.3"
        print ("\tp['dans'] + p['" + a_grave + "']  = 0.5").encode('utf-8')
        print
        print "Actual expectations under the fitted model:"
        print "\tp['dans'] + p['en'] =", p[0] + p[1]
        print ("\tp['dans'] + p['" + a_grave + "']  = " + str(p[0]+p[2])).encode('utf-8')
        # (Or substitute "x.encode('latin-1')" if you have a primitive terminal.)
        '''
'''
class Cat15Movie(object):
    """dimstim >= 0.16 Experiments use the dimstim Experiment (subclassed by say, Movie) object directly"""
    def __init__(self, fname=None, name=None, parent=None):
        """Movies don't need parents, they can just exist on their own and be used by anyone"""
        self.level = 5 # level in the hierarchy
        self.fname = fname
        self.name = name
        self.parent = parent # save parent object, might be an Experiment, might not
        if self.name == None and self.fname != None:
            self.path, self.fname = os.path.split(self.fname) # separate path from fname
            self.name = os.path.splitext(self.fname)[0] # extentionless fname
            if self.name not in _data.movies:
                _data.movies[self.name] = self # add self to _data.movies dictattr
        else:
            pass # both self.name and self.fname are None, this happens when executing Cat 15 textheaders, where you init a movie with m = Movie(), and only later assign its fname field. In this case, the .loadCat15exp() method handles adding movies init'd from textheader to the _data.movies dictattr

    def load(self, asarray=True, flip=False):
        """Load movie frames"""
        try:
            self.frames # movie's already been loaded, don't do anything
            return
        except AttributeError:
            pass
        try:
            self.frames = _data.movies[self.name].frames # if a Movie init'd with the same name already has its data loaded, use it
            return
        except AttributeError:
            pass

        self.f = file(self.fname, 'rb') # open the movie file for reading in binary format
        headerstring = self.f.read(5)
        if headerstring == 'movie': # a header has been added to the start of the file
            self.ncellswide, = struct.unpack('H', self.f.read(2)) # 'H'== unsigned short int
            self.ncellshigh, = struct.unpack('H', self.f.read(2))
            self.nframes, = struct.unpack('H', self.f.read(2))
            if self.nframes == 0: # this was used in Cat 15 mseq movies to indicate 2**16 frames, shouldn't really worry about this, cuz we're using slightly modified mseq movies now that we don't have the extra frame at the end that the Cat 15 movies had (see comment in Experiment module), and therefore never have a need to indicate 2**16 frames
                self.nframes = 2**16
            self.offset = self.f.tell() # header is 11 bytes long
        else: # there's no header at the start of the file, set the file pointer back to the beginning and use these hard coded values:
            self.f.seek(0)
            self.ncellswide = self.ncellshigh = 64
            self.nframes = 6000
            self.offset = self.f.tell() # header is 0 bytes long
        self.framesize = self.ncellshigh*self.ncellswide

        # read in all of the frames
        # maybe check first to see if file is > 1GB, if so, _loadaslist() to prevent trying to allocate one huge piece of contiguous memory and raising a MemoryError, or worse, segfaulting
        if asarray:
            self._loadasarray(flip=flip)
        else:
            self._loadaslist(flip=flip)
        leftover = self.f.read() # check if there are any leftover bytes in the file
        if leftover != '':
            pprint(leftover)
            print self.ncellswide, self.ncellshigh, self.nframes
            raise RuntimeError, 'There are unread bytes in movie file %r. Width, height, or nframes is incorrect in the movie file header.' % self.fname
        self.f.close() # close the movie file
        treestr = self.level*TAB + self.fname
        print treestr

    def _loadasarray(self, flip=False):
        self.frames = np.fromfile(self.f, np.uint8, count=self.nframes*self.framesize)
        self.frames.shape = (self.nframes, self.ncellshigh, self.ncellswide)
        self.f.seek(self.offset + self.nframes*self.framesize) # seek to what should be EOF
        if flip:
            self.frames = self.frames[::, ::-1, ::] # flip all frames vertically for OpenGL's bottom left origin

    def _loadaslist(self, flip=False):
        self.frames = []
        for framei in xrange(self.nframes): # one frame at a time...
            frame = np.fromfile(self.f, np.uint8, count=self.framesize) # load the next frame
            frame.shape = (self.ncellshigh, self.ncellswide)
            if flip:
                frame = frame[::-1, ::] # flip all frames vertically for OpenGL's bottom left origin
            self.frames.append(frame)
'''

class NeuropyScalarFormatter(mpl.ticker.ScalarFormatter):
    """Overloaded from mpl.ticker.ScalarFormatter for 4 reasons:
    1) turn off stupid offset
    2) increase maximum possible number of sigfigs
    3) increase +ve and -ve order of magnitude thresholds before switching to scientific notation
    4) keep exponents in engineering notation, ie multiples of 3
    """
    def __init__(self, useOffset=False, useMathText=False):
        # useOffset allows plotting small data ranges with large offsets:
        # for example: [1+1e-9,1+2e-9,1+3e-9]
        # useMathText will render the offset an scientific notation in mathtext
        #super(NeuropyScalarFormatter, self).__init__(useOffset=useOffset, useMathText=useMathText) # can't use this, cuz derived from an old-style class
        mpl.ticker.ScalarFormatter.__init__(self, useOffset=useOffset, useMathText=useMathText)
        self.thousandsSep = '' # default to not using a thousands separator

    def _set_orderOfMagnitude(self, range):
        # if scientific notation is to be used, find the appropriate exponent
        # if using an numerical offset, find the exponent after applying the offset
        locs = np.absolute(self.locs)
        if self.offset: oom = math.floor(math.log10(range))
        else:
            if locs[0] > locs[-1]: val = locs[0]
            else: val = locs[-1]
            if val == 0: oom = 0
            else: oom = math.floor(math.log10(val))
        if oom < -3: # decreased -ve threshold for sci notation
            self.orderOfMagnitude = (oom // 3)*3 # stick to engineering notation, multiples of 3
        elif oom > 6: # increased +ve threshold for sci notation
            self.orderOfMagnitude = (oom // 3)*3 # stick to engineering notation, multiples of 3
        else:
            self.orderOfMagnitude = 0

    def _set_format(self):
        # set the format string to format all the ticklabels
        locs = (np.array(self.locs)-self.offset) / 10**self.orderOfMagnitude+1e-15
        sigfigs = [len(str('%1.10f'% loc).split('.')[1].rstrip('0')) for loc in locs] # '%1.3f' changed to '%1.10f' to increase maximum number of possible sigfigs
        sigfigs.sort()
        self.format = '%1.' + str(sigfigs[-1]) + 'f'
        if self._usetex or self._useMathText: self.format = '$%s$'%self.format

    def pprint_val(self, x):
        xp = (x-self.offset)/10**self.orderOfMagnitude
        if np.absolute(xp) < 1e-8: xp = 0
        s = self.format % xp
        if self.thousandsSep: # add thousands-separating characters
            if s.count('.'): # it's got a decimal in there
                s = re.sub(r'(?<=\d)(?=(\d\d\d)+\.)', self.thousandsSep, s) # use the regexp for floats
            else: # it's an int
                s = re.sub(r'(?<=\d)(?=(\d\d\d)+$)', self.thousandsSep, s) # use the regexp for ints
        return s


class NeuropyAutoLocator(mpl.ticker.MaxNLocator):
    """A tick autolocator that generates more ticks than the standard mpl autolocator"""
    def __init__(self):
        #mpl.ticker.MaxNLocator.__init__(self, nbins=9, steps=[1, 2, 5, 10]) # standard autolocator
        mpl.ticker.MaxNLocator.__init__(self) # use MaxNLocator's defaults instead


def getargstr(obj):
    """Returns object's argument list as a string. Stolen from wx.py package?"""
    import inspect
    argstr = apply(inspect.formatargspec, inspect.getargspec(obj))
    if inspect.isfunction(obj):
        pass
    elif inspect.ismethod(obj):
        # stolen from wx.py.introspect.getCallTip:
        temp = argstr.split(',')
        if len(temp) == 1:  # No other arguments.
            argstr = '()'
        elif temp[0][:2] == '(*': # first param is like *args, not self
            pass
        else:  # Drop the first argument.
            argstr = '(' + ','.join(temp[1:]).lstrip()
    else:
        argstr = '()'
    return argstr
'''
def frame(**kwargs):
    """Returns a CanvasFrame object"""
    frame = CanvasFrame(**kwargs)
    frame.Show(True)
    return frame
frame.__doc__ += '\n' + CanvasFrame.__doc__
frame.__doc__ += '\n\n**kwargs:\n' + getargstr(CanvasFrame.__init__)

def barefigure(*args, **kwargs):
    """Creates a bare figure with no toolbar or statusbar"""
    figure(*args, **kwargs)
    gcfm().frame.GetStatusBar().Hide()
    gcfm().frame.GetToolBar().Hide()
barefigure.__doc__ += '\n' + figure.__doc__
'''
def lastcmd():
    """Returns a string containing the last command entered by the user in the
    IPython shell"""
    ip = get_ipython()
    return ip._last_input_line

def innerclass(cls):
    """Class decorator for making a class behave as a Java (non-static) inner
    class.

    Each instance of the decorated class is associated with an instance of its
    enclosing class. The outer instance is referenced implicitly when an
    attribute lookup fails in the inner object's namespace. It can also be
    referenced explicitly through the property '__outer__' of the inner
    instance.

    Title: Implementing Java inner classes using descriptors
    Submitter: George Sakkis - gsakkis at rutgers.edu
    Last Updated: 2005/07/08
    Version no: 1.1
    Category: OOP
    http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/409366
    """
    if hasattr(cls, '__outer__'):
        raise TypeError('Cannot set attribute "__outer__" in inner class')
    class InnerDescriptor(object):
        def __get__(self, outer, outercls):
            if outer is None:
                raise AttributeError('An enclosing instance that contains '
                           '%s.%s is required' % (cls.__name__, cls.__name__))
            clsdict = cls.__dict__.copy()
            # explicit read-only reference to the outer instance
            clsdict['__outer__'] = property(lambda self: outer)
            # implicit lookup in the outer instance
            clsdict['__getattr__'] = lambda self,attr: getattr(outer,attr)
            def __setattr__(this, attr, value):
                # setting an attribute in the inner instance sets the
                # respective attribute in the outer instance if and only if
                # the attribute is already defined in the outer instance
                if hasattr(outer, attr): setattr(outer,attr,value)
                else: super(this.__class__,this).__setattr__(attr,value)
            clsdict['__setattr__'] = __setattr__
            return type(cls.__name__, cls.__bases__, clsdict)
    return InnerDescriptor()

def intround(n):
    """Round to the nearest integer, return an integer. Works on arrays.
    Saves on parentheses, nothing more"""
    if iterable(n): # it's a sequence, return as an int64 array
        return np.int64(np.round(n))
    else: # it's a scalar, return as normal Python int
        return int(round(n))

def roundto(val, nearest):
    """Round val to nearest nearest, always rounding away from 0"""
    if val >= 0:
        return np.ceil(val / nearest) * nearest
    else:
        return np.floor(val / nearest) * nearest

def pad0s(val, ndigits=2):
    """Returns a string rep of val, padded with enough leading 0s
    to give you a string rep with ndigits in it"""
    val = str(int(val))
    nzerostoadd = ndigits - len(val) # -ve values add no zeros to val
    val = '0'*nzerostoadd + val
    return val

def txtdin2binarydin(fin, fout):
    """Converts a csv text .din file to an int64 binary .din file"""
    fi = file(fin, 'r') # open the din file for reading in text mode
    fo = file(fout, 'wb') # for writing in binary mode
    for line in fi:
        line = line.split(',')
        '''
        # for old NVS display, converts from NVS condition numbers (which increment with
        # repeats) to dimstim sweepis (which don't)
        nruns = 18
        line[1] = int(line[1]) % nruns
        '''
        # write both values out as a C long longs, using the system's native ('@') byte order:
        fo.write( struct.pack('@qq', int(line[0]), int(line[1])) )
    fi.close()
    fo.close()
    print 'Converted ascii din: %r to binary din: %r' % (fin, fout)

def convertalltxtdin2binarydin(path=None):
    """Converts all text .csv din files in path (or cwd) to 64 bit binary .din files of the
    same name"""
    if path == None:
        path = os.getcwd()

    listing = os.listdir(path)
    dinfnames = []

    for fname in listing:
        if fname.endswith('.csv'):
            # text din filenames without the .csv extension
            dinfnames.append(fname[:-len('.csv')])

    for dinfname in dinfnames:
        fin = os.path.join(path, dinfname) + '.csv'
        fout = os.path.join(path, dinfname) + '.din'
        #os.rename(fout, fin) # rename the csv .din file to .din.txt extension
        txtdin2binarydin(fin, fout) # convert the text .csv file to binary .din file
        #os.remove(fin) # delete the .din.txt file

def renameSpikeFiles(path, newname):
    """Renames all .spk files in path to newname, retaining their '_t##.spk' ending"""
    for fname in os.listdir(path):
        if fname.endswith('.spk'):
            i = fname.find('_t')
            if i != -1:
                newfname = newname+fname[i::]
                print newfname
                os.rename(os.path.join(path, fname), os.path.join(path, newfname))

def csv2binary(fin, multiplier=1e6, skipfirstline=True):
    """Converts spike data in a csv file, with cells in the columns and times down the rows,
    into int64 binary files, one for each neuron. Takes csv values and multiplies them by
    multiplier before saving"""
    fin = os.path.normpath(fin)
    fi = file(fin, 'r') # open csv file for reading in text mode
    print 'Exporting %s to:' % fi.name
    firstline = fi.next()
    nneurons = len(firstline.split(','))
    if not skipfirstline: # ie first line isn't just column headers
        fi.seek(0)
    data = [] # nested list, one entry per neuron
    for ni in range(nneurons):
        data.append([]) # init each neuron's list
    for line in fi:
        line = line.replace('\n', '') # strip the newline character
        line = line.split(',')
        for ni, strval in enumerate(line): # going horizontally across the line
            try:
                data[ni].append(intround(float(strval)*multiplier))
            except ValueError: # strval is empty string
                pass
    fi.close()
    #return data
    path = os.path.splitext(fi.name)[0] # extensionless path + filename
    try:
        os.mkdir(path) # make a dir with that name
    except OSError: # dir already exists
        pass
    # just the extensionless filename, replace spaces with underscores:
    tail = os.path.split(path)[-1].replace(' ', '_')
    for ni, neuron in enumerate(data):
        fname = (os.path.join(path, tail) + '_t' +
                 pad0s(ni, ndigits=len(str(nneurons))) + '.spk')
        fo = file(fname, 'wb') # for writing in binary mode
        print fo.name
        for spiketime in neuron:
            # write each spiketime to the file, there should be a more streamlined way
            # to do this. Write the value out as a C long long, using the system's native
            # ('@') byte order
            fo.write( struct.pack('@q', spiketime) )
        fo.close()

def warn(msg, level=2, exit_val=1):
    """Standard warning printer. Gives formatting consistency. Stolen from IPython.genutils"""
    if level > 0:
        header = ['', '', 'WARNING: ', 'ERROR: ', 'FATAL ERROR: ']
        print >> sys.stderr, '%s%s' % (header[level],msg)
        if level == 4:
            print >> sys.stderr,'Exiting.\n'
            sys.exit(exit_val)
'''
def warn(msg):
    import warnings
    warnings.warn(msg, category=RuntimeWarning, stacklevel=2)

def unique(seq):
    """Return unique items from a 1-dimensional sequence. Stolen from numpy.unique().
    Dictionary setting is quite fast"""
    result = {}
    for item in seq:
        result[item] = None
    return result.keys()

def unique(objlist):
    """Returns the input list minus any repeated objects it may have had.
    Also defined in dimstim"""
    return list(set(objlist)) # this requires Python >= 2.4

def unique(objlist):
    """Does in-place removal of non-unique objects in a list of objects"""
    for (i,obj1) in enumerate(objlist):
        for (j,obj2) in enumerate(objlist):
            if i != j and obj1 == obj2:
                del objlist[j]
'''
def iterable(x):
    """Check if the input is iterable, stolen from numpy.iterable()"""
    try:
        iter(x)
        return True
    except:
        return False

def toiter(x):
    """Convert to iterable. If input is iterable, returns it. Otherwise returns it in a list.
    Useful when you want to iterate over an object (like in a for loop),
    and you don't want to have to do type checking or handle exceptions
    when the object isn't a sequence"""
    if iterable(x):
        return x
    else:
        return [x]

def tolist(x):
    """Convert to list. If input is a dict, returns its values. If it's already a list,
    returns it. Otherwise, input is returned in a list."""
    if type(x) == dict:
        return list(x.values())
    elif type(x) == list:
        return x
    else:
        return [x] # stick it in a list

def to2d(arr):
    """Convert a 1D array to a 2D array with just a singleton row. If arr is already
    2D, just return it. If it's anything more than 2D, raise an error"""
    nd = arr.ndim
    assert nd in [1, 2], 'array rank > 2'
    if nd == 1:
        arr = arr.reshape(1, -1)
    return arr

def joinpath(pathlist):
    """Unlike os.path.join(), take a list of path segments, return them joined in a string
    with local separators"""
    path = ''
    for segment in pathlist:
        path = os.path.join(path, segment)
    return path

def dist(a, b):
    """Return the Euclidean distance between two N-dimensional coordinates"""
    a = np.asarray(a)
    b = np.asarray(b)
    return np.sqrt(((a-b)**2).sum())

def approx(a, b, rtol=1.e-14, atol=1.e-14):
    """Return a boolean array describing which components of a and b are equal
    subject to given tolerances. The relative error rtol must be positive and << 1.0
    The absolute error atol comes into play for those elements of y that are very
    small or zero; it says how small x must be also. Copied and modified from
    numpy.allclose()"""
    x = np.array(a, copy=False)
    y = np.array(b, copy=False)
    #print x.shape
    #print y.shape
    return np.less(np.absolute(x-y), atol + rtol * np.absolute(y))

def pmf(a, bins=10, range=None, weights=None):
    """Return probability mass function of a, where sum of all bins is 1"""
    n, bins = np.histogram(a, bins=bins, range=range, weights=weights, density=False)
    n = n / float(sum(n)) # normalize by sum of bins to get pmf
    return n, bins

def pmf2d(a, bins=10, range=None, weights=None):
    """Return 2D probability mass function of a, where sum of all bins is 1"""
    H, xedges, yedges = np.histogram2d(x, y, bins=bins, range=range, normed=False,
                                       weights=weights)
    H = H / float(sum(H)) # normalize by sum of bins to get pmf
    return H, xedges, yedges

def sah(t, y, ts, keep=False):
    """Resample using sample and hold. Returns resampled values at ts given the original
    points (t,y) such that the resampled values are just the most recent value in y (think
    of a staircase with non-uniform steps). Assumes that t is sorted. t and ts arrays should
    be of the same data type. Contributed by Robert Kern."""
    # find where ts falls in t, dec so you get indices that point to the most
    # recent value in y:
    i = np.searchsorted(t, ts) - 1
    # handle the cases where ts is smaller than the first point.
    '''this has an issue of not keeping the original data point where ts == t'''
    i = np.where(i < 0, 0, i)

    ### NOTE: can probably get around having to do this by using searchsorted's
    ### 'side' keyword

    if keep:
        # The following ensures that the original data point is kept when ts == t,
        # doesn't really work if the shortest ISI is less than tres in ts.
        # find changes in i, nonzero() method returns a tuple, pick the result for the
        # first dim with [0] index
        di = np.diff(i).nonzero()[0]
        # check at those change indices if t ~= ts (ignoring potential floating point
        # representational inaccuracies). If so, inc i at that point so you keep y at that
        # point.
        si = approx(t[1::], ts[di])
        #print i
        i[di[si]] += 1
        #print i
    return y[i]

def corrcoef(x, y):
    """Returns the correlation coefficient of signals x and y. This just uses np.corrcoef(),
    but converts to floats first, cuz np.corrcoef() seems to have issues with integer signals,
    especially those with zeros in them."""
    #assert len(x) == len(y), 'arrays need to be of equal length'
    x = np.float64(x)
    y = np.float64(y)
    # pick one of the 2 entries in the correlation coefficient matrix, on the -ve diagonal
    # (er, the one that goes from bottom left to top right, that's what I mean):
    return np.corrcoef(x, y)[0, 1]
    # this works just fine as well, easier to understand too:
    #return ((x * y).mean() - x.mean() * y.mean()) / (x.std() * y.std())

def bin(i, minbits=8):
    """Return a string with the binary representation of an integer, or sequence of integers.
    If necessary, will append leading zeros if result is less than minbits long.
    Uses np.binary_repr()"""
    ints = toiter(i) # ensure it's iterable
    sints = []
    for i in ints:
        s = np.binary_repr(i)
        nzerostoadd = minbits - len(s) # OK if this is -ve
        s = '0'*nzerostoadd + s # add enough leading zeros to get requested minbits
        sints.append(s)
    if len(sints) == 1:
        sints = sints[0] # pull it out of the list
    return sints

def binslow(i, minbits=8):
    """Return a string with the binary representation of an integer. If necessary, will
    append leading zeros if result is less than minbits long. Seems like np.binary_repr() is
    a somewhat faster alternative. First 2 lines stolen from Andrew Gaul <andrew@gaul.org>
    off the web"""
    l = ['0000', '0001', '0010', '0011', '0100', '0101', '0110', '0111',
         '1000', '1001', '1010', '1011', '1100', '1101', '1110', '1111']
    s = ''.join(map(lambda x, l=l: l[int(x, 16)], hex(i)[2:]))
    s = s.lstrip('0') # strip s of leading zeros
    nzerostoadd = minbits - len(s)
    s = '0'*nzerostoadd + s # add enough leading zeros to get requested minbits
    return s

# an alternative would be to use int('10110', base=2) for each column, probably slower though
def binarray2int(bin):
    """Takes a 2D binary array (only 1s and 0s, with rows LSB to MSB from top to bottom)
    and returns the base 10 integer representations of the columns"""
    #assert type(bin) == type(np.array)
    bin = to2d(bin) # ensure it's 2D. If it's 1D, force it into having a singleton row
    nbits = bin.shape[0] # length of the first dimension, ie the number of rows
    multiplier = []
    for i in range(nbits):
        multiplier.append(2**i)
    # convert from list and transpose to a column vector (have to make it 2D to transpose):
    multiplier = np.array(multiplier, ndmin=2).transpose()
    #print multiplier
    x = bin*multiplier
    #print x
    # sum over the first dimension (the rows), that way, you're left with only columns in
    # a row vector:
    return x.sum(axis=0)

def getbinarytable(nbits=8):
    """Generate a 2D binary table containing all possible words for nbits, with bits in the
    rows and words in the columns (LSB to MSB from top to bottom)"""
    rowlength = 2**nbits
    '''
    x = np.zeros((nbits, 2**nbits)) # init an array
    for bit in range(nbits):
        pattern = [0]*2**bit
        pattern.extend([1]*2**bit)
        npatterns = rowlength / len(pattern) # == 2**nbits / len(pattern) == 2**nbits /
                                             # 2**(bit+1) == 2**(nbits-bit-1)
        row = pattern*npatterns
        x[bit]=row
    return x
    '''
    '''
    x = np.zeros((nbits, 2**nbits), dtype=np.int8) # init an array
    for bit in range(nbits): # one row at a time
        pattern = np.array(0, dtype=np.int8).repeat(2**bit)
        pattern = np.concatenate((pattern, np.array(1, dtype=np.int8).repeat(2**bit)))
        npatterns = rowlength / len(pattern) # == 2**nbits / len(pattern) == 2**nbits /
                                             # 2**(bit+1) == 2**(nbits-bit-1)
        row = np.tile(pattern, [1, npatterns])
        x[bit::,::] = row
    return x
    '''
    # this seems to be the fastest method:
    x = []
    for bit in range(nbits): # one row at a time
        pattern = np.array(0, dtype=np.int8).repeat(2**bit)
        pattern = np.concatenate((pattern, np.array(1, dtype=np.int8).repeat(2**bit)))
        # == 2**nbits / len(pattern) == 2**nbits / 2**(bit+1) == 2**(nbits-bit-1)
        npatterns = rowlength / len(pattern)
        row = np.tile(pattern, [1, npatterns])
        x.append(row)
    return np.concatenate(x)

def enlarge(a, x=2, y=None):
    """Enlarges 2D image array a using simple pixel repetition in both dimensions.
    Enlarges by factor x horizontally and factor y vertically.
    If y is left as None, uses factor x for both dimensions."""
    a = np.asarray(a)
    assert a.ndim == 2
    if y == None:
        y = x
    for factor in (x, y):
        assert factor.__class__ == int
        assert factor > 0
    return a.repeat(y, axis=0).repeat(x, axis=1)

def charfind(string, char):
    """Finds char in string, returns matching indices. There's gotta be a built-in way to do
    this somewhere..."""
    assert len(char) == 1
    i = []
    # maybe more efficient to use .find() method on successively smaller slices of string
    for si, s in enumerate(string):
        if s == char:
            i.append(si)
    return i
'''
def shuffle(x):
    """Takes an input list x and returns a shuffled (without replacement) copy. Its only
    benefit over and above random.sample() is that you don't have to pass a second argument
    len(x) every time you use it. In NumPy, it's better (and faster) to use
    np.random.shuffle()"""
    return random.sample(x, len(x))
'''
def shuffle(seq):
    """Takes a sequence and returns a shuffled (without replacement) copy. Its only benefit
    over np.random.shuffle is that it returns a copy instead of shuffling in-place"""
    result = copy(seq)
    np.random.shuffle(result) # shuffles in-place, doesn't convert to an array
    return result
'''
def randomize(x):
    """Takes an input list x and returns a randomized (with replacement) output list of
    the same length, sampled from the input sequence"""
    y = [] # init output list
    for i in range(0, len(x)):
        y.append(random.choice(x))
    return y
'''
def randomize(seq):
    """Returns a randomized (with replacement) output sequence sampled from
    (and of the same length as) the input sequence"""
    n = len(seq)
    i = np.random.randint(n, size=n) # returns random ints from 0 to len(seq)-1
    if seq.__class__ == np.ndarray:
        return np.asarray(seq)[i] # use i as random indices into seq, return as an array
    else:
        return list(np.asarray(seq)[i]) # return as a list

def randsign(size=1):
    """Return random array of -1 and 1 integers"""
    rand = np.random.random(size)
    signs = np.ones(size, dtype=np.int)
    signs[rand < 0.5] = -1
    return signs

def fact(n):
    """Factorial!"""
    assert n.__class__ == int
    assert n >= 0
    if n == 0:
        n = 1 # 0! == 1!
    result = n
    for i in range(1, n):
        result *= i
    return result

def nPr(n, r):
    """n Pick r"""
    assert n >= r
    return fact(n) // fact(n-r)

def nCr(n, r):
    """n Choose r"""
    assert n >= r
    return nPr(n, r) // fact(r)

ncr = nCr # convenience f'ns
npr = nPr

def combgen(objects, r=2, i=None, level=0):
    """Generator that yields, without replacement, all length r possible combinations of
    objects from a length n sequence. Eg, if objects=[0,1,2] and r=2, this yields [0,1],
    [0,2], and [1,2], one at a time. A recursive generator is used in order to create the
    necessary r number of nested for loops. This is cool (my first generator!), but deep
    recursion is slow"""
    objects = np.asarray(objects)
    assert r <= len(objects)
    try: # recursive case
        if i == None:
            i = [0]*r # stores all the current index values for all r nested for loops
        if level == 0: # handles special case for starting index of top level for loop
            starti = 0
        else:
            # start this level's loop index at one greater than the previous level's
            # current loop index:
            starti = i[level-1] + 1
        # not too sure why this is n+1, but it works:
        for i[level] in range(starti, len(objects)+1):
            # iterate over next level's generator:
            for comb in combgen(objects, r=r, i=i, level=level+1):
                # yield whatever the next level (level+1) yields, pass it on up to the
                # previous level (level-1)
                yield comb 
    except IndexError:
        # base case, we're at the deepest recursion level (innermost for loop). IndexError
        # comes from i[level] being out of range:
        #if len(i) == 1:
        #    yield objects[i[0]] # no need to yield them in a list
        #else:
            # use the current index state for all levels to yield a combination of objects:
            yield objects[i]

def combs(objects, r=2):
    """Returns all nCr possible combinations of items in objects, in a 1D array of arrays.
    Generates code with the right number of nested for loops, faster than combgen()"""
    objects = np.asarray(objects)
    dtype = objects.dtype
    n = len(objects)
    assert r <= n
    i = np.asarray([0]*r)
    # stores all combinations, will be a 1D array of arrays:
    combs = np.empty(nCr(n, r), dtype=np.object)
    combi = -1

    code = ''
    tabs = ''
    code += tabs+'for i[0] in range(0, n):\n' # this is the outermost for loop
    tabs += '\t'
    for level in range(1, r): # here come the inner nested for loops...
        code += tabs+'for i['+str(level)+'] in range(i['+str(level-1)+']+1, n):\n'
        tabs += '\t'

    # here's the innermost part of the nested for loops
    code += tabs + 'combi += 1\n'
    code += tabs + 'combs[combi] = objects[i]\n'
    #print code

    exec(code) # run the generated code
    return combs
    '''
    # example of what the generated code looks like for r==3:
    for i[0] in range(0, n):
        for i[1] in range(i[0]+1, n):
            for i[2] in range(i[1]+1, n):
                combi += 1
                combs[combi] = objects[i]
    '''

def argcombs(objects, r=2):
    """Returns all nCr possible combinations of indices into objects.
    You'd think this would be faster than combs(), but it doesn't seem to be"""
    n = len(objects)
    assert n < 2**8 # this way, we can use uint8's instead of int32's to save memory
    assert r <= n
    i = np.asarray([0]*r)
    argcombs = np.zeros((nCr(n, r), r), dtype=np.uint8)
    combi = -1

    code = ''
    tabs = ''
    code += tabs+'for i[0] in range(0, n):\n' # this is the outermost for loop
    tabs += '\t'
    for level in range(1, r): # here come the inner nested for loops...
        code += tabs+'for i['+str(level)+'] in range(i['+str(level-1)+']+1, n):\n'
        tabs += '\t'

    # here's the innermost part of the nested for loops
    code += tabs + 'combi += 1\n'
    code += tabs + 'argcombs[combi, :] = i\n'
    #print code

    exec(code) # run the generated code
    return argcombs
    '''
    # example of what the generated code looks like for r==3:
    for i[0] in range(0, n):
        for i[1] in range(i[0]+1, n):
            for i[2] in range(i[1]+1, n):
                combi += 1
                argcombs[combi, :] = i
    '''

def nCrsamples(objects, r, nsamples=None):
    """Returns a list of nsamples unique samples, each of length r, sampled from objects"""
    maxnsamples = nCr(len(objects), r)
    if nsamples == None:
        nsamples = maxnsamples # return all possible combinations
    if nsamples > maxnsamples:
        # make sure we're not being asked for more than the maximum possible number of
        # unique samples
        raise ValueError('requested unique nsamples (%d) is larger than len(objects) choose '
                         'r (%d C %d == %d)' % (nsamples, len(objects), r, maxnsamples))
    # I've set the criteria for generating a table to be never, because generating the table
    # and then sampling it almost always takes longer (at least for maxnsamples as high as
    # 325, say) than just picking combs at random and making sure they're unique
    if maxnsamples < 0:
        # generate a table of all possible combinations, and then just pick nsamples from
        # it without replacement
        table = combs(objects, r)
        samples = random.sample(table, nsamples)
    elif r == 1: # we're just choosing one item from objects at a time
        samples = random.sample(objects, nsamples)
    else:
        # the number of possible combs is inconveniently large to completely tabulate,
        # pick some combinations at random and make sure each comb is unique
        samples = []
        samplei = 0
        while samplei < nsamples:
            sample = random.sample(objects, r) # choose r objects at random
            # sort for sake of comparison with other samples, important because this
            # removes any differences due to permuatations (as opposed to combs)
            sample.sort()
            if sample not in samples:
                # make sure they're not the same set of objects as any previous set in samples
                samples.append(sample) # add it to the list of samples
                samplei += 1
    return samples

'''
# this f'n isn't really needed, just use objlist.sort(key=lambda obj: obj.attrib)
def sortby(objs, attrib, cmp=None, reverse=False):
    """Returns objects list sorted according to the specified object attribute.
    attrib should be passed as a string"""
    # sort in-place:
    objs.sort(key=lambda obj: obj.__getattribute__(attrib), cmp=cmp, reverse=reverse)
    return objs
'''
def intersect1d(arrays, assume_unique=False):
    """Find the intersection of any number of 1D arrays.
    Return the sorted, unique values that are in all of the input arrays.
    Adapted from numpy.lib.arraysetops.intersect1d"""
    N = len(arrays)
    if N == 0:
        return np.asarray(arrays)
    arrays = list(arrays) # allow assignment
    if not assume_unique:
        for i, arr in enumerate(arrays):
            arrays[i] = np.unique(arr)
    aux = np.concatenate(arrays) # one long 1D array
    aux.sort() # sorted
    if N == 1:
        return aux
    shift = N-1
    return aux[aux[shift:] == aux[:-shift]]

def mean_accum(data):
    """Takes mean by accumulating over 0th axis in data,
    much faster than np.mean() because it avoids making any copies of the data
    Suggested by Tim Hochberg"""
    result = np.zeros(data[0].shape, np.float64) # init output array
    for dataslice in data:
        # this for loop isn't such a bad thing cuz the massive add step inside the loop
        # is the limiting factor
        result += dataslice
    result /= len(data)
    return result

def mean_accum2(data, indices):
    """A variant of mean_accum(), where you provide all the data and the indices into it
    to average over. This was Tim Hochberg's version"""
    result = np.zeros(data[0].shape, np.float64)
    for i in indices:
        result += data[i]
    result /= len(indices)
    return result

def normalize_range(a):
    """Normalize a such that all of its values span the interval [0, 1]"""
    a = a - a.min()
    a = a / a.max()
    return a

def normalize(p):
    """Normalize distribution p such that sum(p) == 1. Return zeros if sum(p) == 0"""
    p = np.asarray(p)
    if p.sum() == 0:
        return np.zeros(p.shape) # just return zeros
    else:
        return p / float(p.sum()) # return it normalized

def ensurenormed(p, atol=1e-8):
    """Ensures p is normalized. Returns p unchanged if it's already normalized,
    otherwise, prints a warning and returns it normalized. atol is how close to 1.0
    p.sum() needs to be"""
    p = np.asarray(p)
    psum = p.sum()
    if not approx(psum, 1.0, atol=atol): # make sure the probs sum to 1
        print 'ps don''t sum to 1, they sum to %f instead, normalizing for you' % psum
        p /= float(psum)
    return p

def logn(x, base=10):
    """Performs log of x with specified base"""
    return np.log(x) / np.log(base)

def log_no_sing(x, subval=0.0, base=np.e):
    """Performs log on array x, ignoring any zeros in x to avoid singularities,
    and returning subval in their place in the result"""
    x = np.asarray(x)
    singi = x==0 # find the singularities
    x[singi] = 1 # replace 'em with 1s, or anything else that's safe to take the log of
    result = logn(x, base=base) # now it's safe to take the log
    # substitute the result where the singularities were with the substitution value:
    result[singi] = subval
    return result

def log10_no_sing(x, subval=0.0):
    """Performs log10 on x, ignoring singularities"""
    return log_no_sing(x, subval=subval, base=10)

def log2_no_sing(x, subval=0.0):
    """Performs log2 on x, ignoring singularities"""
    return log_no_sing(x, subval=subval, base=2)

def entropy(p):
    """Returns the entropy (in bits) of the prob distribution described by the prob
    values in p"""
    p = ensurenormed(p)
    return -(p * np.log2(p)).sum()

def entropy_no_sing(p):
    """Returns the entropy (in bits) of the prob distribution described by the prob values in p
    Ignore singularities in p (assumes their contribution to entropy is zero)"""
    p = ensurenormed(p)
    return -(p * log2_no_sing(p, subval=0.0)).sum()

def MI(XY):
    """Given the joint PDF of two variables, return the mutual information (in bits)
    between the two.
    I = sum_X sum_Y P(x, y) * log2( P(x, y) / (P(x) * P(y)) )
    where P(x) and P(y) are the marginal distributions taken from the joint
    Is this slow? Needs optimization? Already implemented in scipy?"""
    XY = np.asarray(XY)
    assert XY.ndim == 2
    XY = ensurenormed(XY)
    # calculate the marginal probability distributions for X and Y from the joint
    X = XY.sum(axis=1) # sum over the rows of the joint, get a vector nrows long
    Y = XY.sum(axis=0) # sum over the cols of the joint, get a vector ncols long
    I = 0.0
    for xi, x in enumerate(X):
        for yi, y in enumerate(Y):
            if XY[xi, yi] == 0 or (x * y) == 0: # avoid singularities
                pass # just skip it, assume info contributed is 0 (?????????????????)
            else:
                I += XY[xi, yi] * np.log2( XY[xi, yi] / (x * y) )
    return I

def MIbinarrays(Nbinarray=None, Mbinarray=None, verbose=False):
    """Calculates information that N cells provide about M cells (ie,
    their mutual information), as a fraction of the M cells' marginal entropy.
    Takes cell activities as binary arrays (on or off), with
    cells in the rows and time bins in the columns."""
    Nbinarray = to2d(Nbinarray) # make it 2D if it's 1D
    N = len(Nbinarray) # gets the number of rows
    Nintcodes = binarray2int(Nbinarray)
    Mbinarray = to2d(Mbinarray) # make it 2D if it's 1D
    M = len(Mbinarray) # gets the number of rows
    Mintcodes = binarray2int(Mbinarray)
    # build up joint pdf of all the possible N words, and the two possible N+1th values
    # (0 and 1)
    # values 0 to 2**N - 1, plus 2**N which is needed as the rightmost bin edge for
    # histogram2d:
    xedges = np.arange(2**N+1)
    yedges = np.arange(2**M+1)
    bins = [xedges, yedges]
    # generate joint pdf
    jpdf, xedgesout, yedgesout = pmf2d(Nintcodes, Mintcodes, bins)
    #print 'jpdf\n', jpdf.__repr__()
    #print 'jpdf.sum()', jpdf.sum()
    assert (np.float64(xedges) == xedgesout).all() # sanity check
    assert (np.float64(yedges) == yedgesout).all()
    # pdf of N cells
    #Npdf, Nedges = pmf(Nintcodes, bins=range(2**N))
    #print 'first 100 Npdf\n', Npdf[:100].__repr__()
    # pdf of M cells
    #Mpdf, Medges = pmf(Mintcodes, bins=range(2**M))
    #print 'first 100 Mpdf\n', Mpdf[:100].__repr__()
    marginalMpdf = jpdf.sum(axis=0)
    # make sure what you get from the joint is what you get when just building up the
    # pdf straight up on its own:
    #assert approx(Mpdf, marginalMpdf).all()
    I = MI(jpdf)
    # mutual info as fraction of entropy in M group of cells:
    IdivS = I / entropy(marginalMpdf)
    if verbose:
        print 'nids', nids
        print 'mids', mids
        #print 'Mpdf', Mpdf
        #print 'entropy(Mpdf)', entropy(Mpdf)
        print 'marginal Mpdf', marginalMpdf
        print 'entropy(marginal Mpdf)', entropy(marginalMpdf)
        print 'I', I
        print 'I/entropy', IdivS
    if not 0.0 <= IdivS <= 1.0+1e-10:
        import pdb; pdb.set_trace()
        print 'IdivS is out of range'
        print 'IdivS is %.16f' % IdivS

    return dictattr(I=I, IdivS=IdivS)

def DKL(p, q):
    """Kullback-Leibler divergence from true probability distribution p
    to arbitrary distribution q"""
    assert len(p) == len(q)
    p = ensurenormed(p)
    q = ensurenormed(q)
    # avoid singularities:
    return sum([ pi * np.log2(pi/float(qi)) for pi, qi in zip(p, q) if pi != 0 and qi != 0 ] ) 

def DJS(p, q):
    """Jensen-Shannon divergence, a symmetric measure of divergence between
    distributions p and q"""
    p = np.asarray(p) # required for adding p and q
    q = np.asarray(q)
    m = 1 / 2.0 * (p + q)
    return 1 / 2.0 * ( DKL(p, m) + DKL(q, m) )

def lstrip(s, strip):
    """What I think str.lstrip should really do"""
    if s.startswith(strip):
        return s[len(strip):] # strip it
    else:
        return s

def rstrip(s, strip):
    """What I think str.rstrip should really do"""
    if s.endswith(strip):
        return s[:-len(strip)] # strip it
    else:
        return s

def strip(s, strip):
    """What I think str.strip should really do"""
    return rstrip(lstrip(s, strip), strip)

def lrstrip(s, lstr, rstr):
    """Strip lstr from start of s and rstr from end of s"""
    return rstrip(lstrip(s, lstr), rstr)

def pathdecomp(path):
    """Decompose (fully split) all components of path into a list of strings
    If the first string is empty, that means the second string was relative to
    filesystem root"""
    return path.split(os.path.sep)

def eof(f):
    """Return whether file pointer is a end of file"""
    orig = f.tell()
    f.seek(0, 2) # seek 0 bytes from end
    return f.tell() == orig

def td2usec(td):
    """Convert datetime.timedelta to microseconds"""
    sec = td.total_seconds() # float
    usec = intround(sec * 1000000) # round to nearest us
    return usec

def issorted(x):
    """Check if x is sorted"""
    try:
        if x.dtype.kind == 'u':
            # x is unsigned int array, risk of int underflow in np.diff
            x = np.int64(x)
    except AttributeError:
        pass # no dtype, not an array
    return (np.diff(x) >= 0).all() # is difference between consecutive entries >= 0?
    # or, you could compare the array to an explicitly sorted version of itself,
    # and see if they're identical

def inverse_uquadratic_cdf(y, a=0, b=1):
    assert b > a
    alpha = 12 / ((b - a)**3)
    beta = (b + a) / 2
    print (y * 3 / alpha - (beta - a)**3)
    return cbrt(y * 3 / alpha - (beta - a)**3) + beta

def sample_uquadratic(a=0, b=1, size=None):
    """Randomly sample the U-quadratic distribution. Good for modelling
    bimodal distributions. a and b specify upper and lower bounds.
    See:
    http://en.wikipedia.org/wiki/UQuadratic_distribution
    http://distributome.org/js/exp/UQuadraticExperiment.html
    """
    assert b > a
    x = np.random.random(size=size) # sample uniform distrib
    x = (b - a) * x + a # scale so that min(x) == a and max(x) == b
    return inverse_uquadratic_cdf(x, a, b)

def split_tranges(tranges, width, tres):
    """Split up tranges into lots of smaller ones, with width and tres"""
    newtranges = []
    for trange in tranges:
        t0, t1 = trange
        assert width < (t1 - t0)
        # calculate left and right edges of subtranges that fall within trange:
        ledges = np.arange(t0, t1-width, tres)
        redges = ledges + width
        subtranges = [ (le, re) for le, re in zip(ledges, redges) ]
        newtranges.append(subtranges)
    return np.vstack(newtranges)

def laminarity(ys):
    """Return boolean arrays indicating whether a given depth is superficial, middle,
    or deep layer (or none of the above)"""
    uns = get_ipython().user_ns
    sup0, sup1 = uns['SUPRANGE']
    mid0, mid1 = uns['MIDRANGE']
    deep0, deep1 = uns['DEEPRANGE']
    # boolean neuron indices:
    supis = (sup0 <= ys) * (ys < sup1) # True values are superficial
    midis = (mid0 <= ys) * (ys < mid1) # True values are middle
    deepis = (deep0 <= ys) * (ys < deep1) # True values are deep
    #otheris = not(supis + deepis) # True values are other, not needed
    return supis, midis, deepis

def rainbow_text(a, x, y, words, colors, **kwargs):
    """
    Take a list of ``words`` and ``colors`` and place them next to each other, with
    words[i] being shown in colors[i]. All keyword arguments are passed to plt.text, so you
    can set the font size, family, etc. Note that horizontal and vertical alignment
    kwargs don't seem to work very well. Also note that although it looks pretty good in the
    QtAgg backend, in some of the important backends, like PNG and PDF, this doesn't space the
    words properly.

    Adapted from Paul Ivanov:
    https://github.com/matplotlib/matplotlib/issues/697#issuecomment-3859591
    """
    f = a.figure
    t = a.transData
    #t = a.transAxes

    # draw horizontal text:
    for w, c in zip(words, colors):
        text = a.text(x, y, " "+w+" ", color=c, transform=t, **kwargs)
        text.draw(f.canvas.get_renderer())
        ex = text.get_window_extent()
        t = mpl.transforms.offset_copy(text._transform, x=ex.width, units='dots')
