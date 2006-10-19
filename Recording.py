"""Defines the Recording class and all of its support classes"""

#print 'importing Recording'

from Core import *
from Core import _data # ensure it's imported, in spite of leading _

class BaseRecording(object):
    """A Recording corresponds to a single SURF file, ie everything recorded between when
    the user hits record and when the user hits stop and closes the SURF file, including any
    pauses in between Experiments within that Recording. A Recording can have multiple Experiments,
    and multiple spike extractions, called Rips"""
    def __init__(self, id=None, name=None, parent=None):

        from Track import Track

        self.level = 3 # level in the hierarchy
        self.treebuf = StringIO.StringIO() # create a string buffer to print tree hierarchy to
        if parent == None:
            try:
                self.t = _data.c[DEFAULTCATID].t[DEFAULTTRACKID] # see if the default Track has already been init'd
            except KeyError:
                self.t = Track() # init the default Track...
                _data.c[DEFAULTCATID].t[self.t.id] = self.t  # ...and add it to the default Cat object's list of Tracks
        else:
            self.t = parent # save parent Track object
        if id is not None:
            name = self.id2name(self.t.path, id) # use the id to get the name
        elif name is not None:
            id = self.name2id(name) # use the name to get the id
        else:
            raise ValueError, 'Recording id and name can\'t both be None'
        self.id = id
        self.name = name
        self.path = self.t.path + self.name + SLASH
        self.t.r[self.id] = self # add/overwrite this Recording to its parent's dict of Recordings, in case this Recording wasn't loaded by its parent
        self.e = {} # store Experiments in a dictionary
        self.rip = {} # store Rips in a dictionary
    def tree(self):
        """Print tree hierarchy"""
        print self.treebuf.getvalue(),
    def writetree(self, string):
        """Write to self's tree buffer and to parent's too"""
        self.treebuf.write(string)
        self.t.writetree(string)
    def id2name(self, path, id):
        if len(str(id)) == 1: # if id is only 1 digit long
            id = '0'+str(id) # add a leading zero
        name = [ dirname for dirname in os.listdir(path) if os.path.isdir(path+dirname) and dirname.startswith(str(id)+' - ') ]
        if len(name) != 1:
            raise NameError, 'Ambiguous or non-existent Recording id: %s' % id
        else:
            name = name[0] # pull the string out of the list
        return name
    def name2id(self, name):
        try:
            id = name[0:name.index(' - ')] # everything before the first ' - ', index() raises ValueError if it can't be found
        except ValueError:
            raise ValueError, 'Badly formatted Recording name: %s' % name
        try:
            id = int(id) # convert string to int if possible
        except ValueError:
            pass # it's alphanumeric, leave it as a string
        return id
    def load(self):

        from Experiment import Experiment
        from Rip import Rip

        treestr = self.level*TAB + self.name + '/'
        self.writetree(treestr+'\n'); print treestr # print string to tree hierarchy and screen
        experimentNames = [ fname[0:fname.rfind('.din')] for fname in os.listdir(self.path) if os.path.isfile(self.path+fname) and fname.endswith('.din') ] # returns din filenames without their .din extension
        for (experimentid, experimentName) in enumerate(experimentNames): # experimentids will be according to alphabetical order of experimentNames
            experiment = Experiment(id=experimentid, name=experimentName, parent=self) # pass both the id and the name
            experiment.load() # load the Experiment
            self.e[experiment.id] = experiment # save it
        #if len(self.e) == 1:
        #   self.e = self.e.values[0] # pull it out of the dictionary
        ripNames = [ dirname[0:dirname.rfind('.rip')] for dirname in os.listdir(self.path) if os.path.isdir(self.path+dirname) and dirname.endswith('.rip') ] # returns rip folder names without their .rip extension
        defaultRipNames = [ ripName for ripName in ripNames for ripkeyword in RIPKEYWORDS if ripName.count(ripkeyword) ]
        if len(defaultRipNames) < 1:
            warn('Couldn\'t find a default Rip for Recording(%s)' % self.id)
        if len(defaultRipNames) > 1: # This could just be a warning instead of an exception, but really, some folder renaming is in order
            raise RuntimeError, 'More than one Rip folder in Recording(%s) has a default keyword: %s' %(self.id, defaultRipNames)
        for (ripid, ripName) in enumerate(ripNames): # ripids will be according to alphabetical order of ripNames
            rip = Rip(id=ripid, name=ripName, parent=self) # pass both the id and the name
            rip.load() # load the Rip
            self.rip[rip.name] = rip # save it
            # make the Neurons from the default Rip (if it exists in the Recording path) available in the Recording, so you can access them via r.n[nid] instead of having to do r.rip[name].n[nid]. Make them just another pointer to the data in r.rip[ripName].n
            for ripkeyword in RIPKEYWORDS[::-1]: # reverse the keywords so first one gets processed last
                if rip.name.count(ripkeyword): # if the keyword is in the ripName
                    self.n = self.rip[rip.name].n # make it the default Rip
                    self.cn = self.rip[rip.name].cn # make it the default Rip for ConstrainedNeurons too
        #if len(self.rip) == 1:
        #   self.rip = self.rip.values[0] # pull it out of the dictionary
        try:
            firstexp = min(self.e.keys())
            lastexp = max(self.e.keys())
            self.trange = self.e[firstexp].trange[0], self.e[lastexp].trange[1] # start of the first experiment to end of the last one
        except ValueError: # self.e is empty, no Experiments in this Recording, use first and last spike across all Neurons
            tranges = [ n.trange for n in self.n.values() ]
            self.trange = min(tranges[:][0]), max(tranges[:][1])
        # then, maybe add other info about the Recording, stored in the same folder, like skull coordinates, angles, polytrode name and type...


class PopulationRaster(object):
    """A population spike raster plot. 'sortby' is the neuron attribute name to sort the raster by.
    Useful attributes to sort by: 'id', 'nspikes', 'trange'"""
    def __init__(self, recording=None, experiments=None, sortby='id'):
        self.r = recording
        if experiments == None:
            self.e = recording.e # dictionary
        else:
            self.e = experiments # should also be a dict
        firstexp = min(self.e.keys())
        self.t0 = self.e[firstexp].trange[0]
        experimentmarkers = [] # a list of all experiment start and stop times, in sorted order
        for e in self.e.values():
            experimentmarkers.extend(e.trange)
        self.experimentmarkers = asarray(experimentmarkers) - self.t0 # make 'em relative to t0
        self.experimentmarkers.sort() # just in case exps weren't in sorted order for some reason
        self.sortby = sortby
        self.neurons = list(self.r.n.values()) # convert to a list to allow sorting
        self.sort()
        self.f = figure(figsize=(14, 6))
        self.a = self.f.add_subplot(111)
        self.a.xaxis.set_major_locator(neuropyAutoLocator()) # better behaved tick locator
        self.a.xaxis.set_major_formatter(neuropyScalarFormatter()) # better behaved tick label formatter
        gcfm().frame.SetTitle(lastcmd())
        #gcfm().frame.SetTitle('r%d.raster(sortby=%s)' % (self.r.id, repr(self.sortby)))
        self.tooltip = wx.ToolTip(tip='tip with a long %s line and a newline\n' % (' '*100)) # create a long tooltip with newline to get around bug where newlines aren't recognized on subsequent self.tooltip.SetTip() calls
        self.tooltip.Enable(False) # leave disabled for now
        self.tooltip.SetDelay(0) # set popup delay in ms
        gcfm().canvas.SetToolTip(self.tooltip) # connect the tooltip to the canvas
        self.a.set_xlabel('time (msec)')
        self.a.set_yticks([]) # turn off y axis
        self.yrange = (0, len(self.neurons))
        self.a.set_ylim(self.yrange)
        self.a.set_position([0.02, 0.1, 0.96, 0.88])
        self.f.canvas.mpl_connect('motion_notify_event', self.onmotion)
        self.f.canvas.mpl_connect('key_press_event', self.onkeypress)
    def sort(self):
        """Sorts self.neurons according to the neuron attribute specified by self.sortby"""
        if self.sortby != None:
            self.neurons.sort(key=lambda n: n.__getattribute__(self.sortby))
            print 'sorted by %s: %s' % (self.sortby, repr([ n.__getattribute__(self.sortby) for n in self.neurons ]))
    def plot(self, left=0, width=200000):
        """Plots the raster, units are us wrt beginning of first experiment"""
        self.left = left
        self.width = width
        # plot experiment start and endpoints
        for e in self.e.values():
            estart = e.trange[0]-self.t0
            eend = e.trange[1]-self.t0
            if left <=  estart and estart <= left+width: # experiment start point is within view
                startlines = self.a.vlines(x=estart/1000.0, ymin=self.yrange[0], ymax=self.yrange[1], fmt='k-') # marks exp start, convert to ms
                startlines[0].set_color((0, 1, 0)) # set to bright green
            if left <= eend and eend <= left+width: # experiment end point is within view
                endlines = self.a.vlines(x=eend/1000.0, ymin=self.yrange[0], ymax=self.yrange[1], fmt='k-') # marks exp end, convert to ms
                endlines[0].set_color((1, 0, 0)) # set to bright red
        # plot the rasters
        for nii, neuron in enumerate(self.neurons):
            x = (neuron.cut((self.t0+left, self.t0+left+width)) - self.t0) / 1000.0 # make spike times always relative to t0, convert to ms
            self.a.vlines(x=x, ymin=nii, ymax=nii+1, fmt='k-')
        self.a.set_xlim(left/1000.0, (left+width)/1000.0) # convert from us to ms
    def panx(self, npages=None, left=None):
        """Pans the raster along the x axis by npages, or to position left"""
        self.a.lines=[] # first, clear all the vlines, this is easy but a bit innefficient, since we'll be redrawing most of the ones we just cleared
        if left != None: # use left
            self.plot(left=left, width=self.width)
        else: # use npages instead
            self.plot(left=self.left+self.width*npages, width=self.width)
        self.f.canvas.draw() # redraw the figure
    def zoomx(self, factor):
        """Zooms the raster along the x axis by factor"""
        self.a.lines=[] # first, clear all the vlines, this is easy but a bit innefficient, since we'll be redrawing most of the ones we just cleared
        centre = (self.left + self.left+self.width) / 2.0
        width = self.width / factor
        left = centre - width / 2.0
        self.plot(left=left, width=width)
        self.f.canvas.draw() # redraw the figure
    def onmotion(self, event):
        """Called during mouse motion over figure. Pops up neuron and
        experiment info in a tooltip when hovering over a neuron row."""
        if event.xdata != None and event.ydata != None: # if mouse is inside the axes
            nii = int(math.floor(event.ydata)) # use ydata to get index into sorted list of neurons
            currentexp = None
            for e in self.e.values(): # for all experiments
                estart = (e.trange[0]-self.t0)/1000.0
                eend = (e.trange[1]-self.t0)/1000.0
                if estart < event.xdata  < eend:
                    currentexp = e
                    break # don't need to check any of the other experiments
            tip = 't: %.3f ms\n' % event.xdata # print timepoint down to nearest us, in units of ms
            tip += 'n%d: %d spikes' % (self.neurons[nii].id, self.neurons[nii].nspikes)
            if currentexp == None:
                tip += '\nno experiment'
            else:
                tip += '\nexperiment %s: %s' % (currentexp.id, repr(currentexp.name))
            self.tooltip.SetTip(tip) # update the tooltip
            self.tooltip.Enable(True) # make sure it's enabled
        else: # mouse is outside the axes
            self.tooltip.Enable(False) # disable the tooltip
    def onkeypress(self, event):
        """Called during a figure keypress"""
        key = event.guiEvent.GetKeyCode() # wx dependent
        # you can also just use the backend-neutral event.key, but that doesn't recognize as many keypresses, like pgup, pgdn, etc.
        if not event.guiEvent.ControlDown(): # wx dependent
            if key == wx.WXK_RIGHT:
                self.panx(+0.1)
            elif key == wx.WXK_LEFT:
                self.panx(-0.1)
            elif key == wx.WXK_UP:
                self.zoomx(1.2)
            elif key == wx.WXK_DOWN:
                self.zoomx(1/1.2)
            elif key == wx.WXK_NEXT: # PGDN (page right)
                self.panx(+1)
            elif key == wx.WXK_PRIOR: # PGUP (page left)
                self.panx(-1)
            elif key == wx.WXK_HOME: # go to start of first Experiment
                self.panx(left=0)
            elif key == wx.WXK_END: # go to end of last Experiment
                lastexp = max(self.e.keys())
                self.panx(left=self.e[lastexp].trange[1]-self.t0-self.width)
        else: # Ctrl key is down, skip backwards or forwards to next experiment marker
            if key == wx.WXK_LEFT:
                i = self.experimentmarkers.searchsorted(self.left, side='left') # current position of left edge of the window in experimentmarkers list
                i = max(0, i-1) # decrement by 1, do bounds checking
                self.panx(left=self.experimentmarkers[i])
            elif key == wx.WXK_RIGHT:
                i = self.experimentmarkers.searchsorted(self.left, side='right') # current position of left edge of the window in experimentmarkers list
                i = min(i, len(self.experimentmarkers)-1) # bounds checking
                self.panx(left=self.experimentmarkers[i])
            elif key == wx.WXK_UP: # zoom in faster
                self.zoomx(3.0)
            elif key == wx.WXK_DOWN: # zoom out faster
                self.zoomx(1/3.0)


class RecordingRaster(BaseRecording):
    """Mix-in class that defines the raster related Recording methods"""
    def raster(self, **kwargs):
        """Creates a population spike raster plot"""
        sortby = kwargs.pop('sortby', 'id')
        pr = PopulationRaster(recording=self, sortby=sortby)
        pr.plot(**kwargs)
    raster.__doc__ += '\n\n'+PopulationRaster.__doc__
    raster.__doc__ += '\n\n**kwargs:'
    raster.__doc__ += '\n__init__: '+getargstr(PopulationRaster.__init__)
    raster.__doc__ += '\n    plot: '+getargstr(PopulationRaster.plot)


class Codes(object):
    """A 2D array where each row is a neuron code, and each column
    is a binary population word for that time bin, sorted LSB to MSB from top to bottom.
    neurons is a list of Neurons. Order in neurons is preserved."""
    def __init__(self, neurons=None, kind='binary', tranges=None, tres=20000, phase=0):
        self.neurons = neurons
        self.kind = kind
        self.tranges = tolist(tranges)
        self.tres = tres
        self.phase = phase
    def calc(self):
        self.s = [] # stores the corresponding spike times for each neuron, just for reference
        self.c = [] # stores the 2D code array
        # append neurons in their order in self.neurons, from top to bottom (LSB to MSB right to left if you tilt your head to the left)
        for neuron in self.neurons:
            codeo = neuron.code(kind=self.kind, tranges=self.tranges, tres=self.tres, phase=self.phase)
            self.s.append(codeo.s) # each is a nested list (ie, 2D), each row will have different length
            self.c.append( [ codeo.c ] ) # each is a nested list (ie, 2D)
        self.t = codeo.t # stores the bin edges, just for reference. all timepoints should be the same for all neurons, cuz they're all given the same trange. use the timepoints of last neuron
        self.c = tuple(self.c) # required for concatenate
        self.c = cat(self.c)
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
        self.tranges = [ trange for codeso in codesos for trange in codeso.tranges ] # this tranges potentially holds multiple tranges from each codes objects, times the number of codes objects
        self.calc() # recalculate this code with its new set of tranges
    '''
'''
class CodeWords(object):
    """What's this supposed to do?"""
    pass
'''

class CodeCorrPDF(object):
    """A PDF of the correlations of the codes of all cell pairs in this Recording
    See 2006 Schneidman fig 1d"""
    def __init__(self, recording=None, experiments=None, **kwargs):
        self.r = recording
        if experiments != None:
            assert experiments.__class__ == dict
        self.e = experiments # save it, should be a dict if not None
        if self.e != None: # specific experiments were specified
            self.tranges = [ e.trange for e in self.e.values() ]
        else:
            self.tranges = [ self.r.trange ] # use the Recording's trange
        self.kwargs = kwargs
    def __eq__(self, other):
        selfd = self.__dict__.copy()
        otherd = other.__dict__.copy()
        # Delete their n and c attribs, if they exist, to prevent comparing them below, since those attribs may not have yet been calculated
        [ d.__delitem__(key) for d in [selfd, otherd] for key in ['corrs', 'n', 'c', 'crange', 'nbins', 'normed'] if d.has_key(key) ]
        if type(self) == type(other) and selfd == otherd:
            return True
        else:
            return False
    def calc(self):
        """Works on ConstrainedNeurons, but is constrained even further if experiments
        were passed and their tranges were used to generate self.tranges (see __init__)"""
        cnis = self.r.cn.keys() # ConstrainedNeuron indices
        ncneurons = len(cnis)
        self.corrs = [ self.r.codecorr(cnis[cnii1], cnis[cnii2], tranges=self.tranges, **self.kwargs)
                       for cnii1 in range(0,ncneurons) for cnii2 in range(cnii1,ncneurons)
                       if cnii1 != cnii2 ]
    def plot(self, figsize=(7.5, 6.5), crange=None, nbins=100, normed='pdf'):
        self.crange = crange
        self.nbins = nbins
        self.normed = normed
        f = figure(figsize=figsize)
        a = f.add_subplot(111)
        try: # figure out the bin edges
            c = np.linspace(start=self.crange[0], stop=self.crange[1], num=self.nbins, endpoint=True)
        except TypeError: # self.crange is None, let histogram() figure out the bin edges
            c = self.nbins
        self.n, self.c = histogram(self.corrs, bins=c, normed=self.normed)
        try:
            barwidth = (self.crange[1] - self.crange[0]) / float(self.nbins)
        except TypeError: # self.crange is None, take width of first bin in self.c
            barwidth = self.c[1] - self.c[0]
        a.bar(left=self.c, height=self.n, width=barwidth, bottom=0, color='k', yerr=None, xerr=None, ecolor='k', capsize=3)
        try:
            a.set_xlim(self.crange)
        except TypeError: # self.crange is None
            pass
        gcfm().frame.SetTitle(lastcmd())
        #gcfm().frame.SetTitle('r%d.codecorrpdf(nbins=%d)' % (self.r.id, self.nbins))
        titlestring = 'neuron pair code correlation pdf'
        if self.e != None:
            print self.e
            titlestring += '\nexperiments: %s' % repr(self.e.keys())
        a.set_title(titlestring)
        if self.normed:
            if self.normed == 'pmf':
                a.set_ylabel('probability mass')
            else:
                a.set_ylabel('probability density')
        else:
            a.set_ylabel('count')
        a.set_xlabel('correlation coefficient')


class RecordingCode(BaseRecording):
    """Mix-in class that defines the spike code related Recording methods"""
    def code(self, cneuron=None, kind='binary', tranges=None, tres=20000, phase=0):
        """Returns a ConstrainedNeuron.Code object, constrained to the time
        ranges of the Experiments in this Recording, as well as by tranges. Takes either a
        ConstrainedNeuron object or just a ConstrainedNeuron id"""
        try:
            return cneuron.code(kind='binary', tranges=None, tres=20000, phase=0) # see if cneuron is a ConstrainedNeuron
        except AttributeError:
            return self.cn[cneuron].code(kind='binary', tranges=None, tres=20000, phase=0) # cneuron is probably a ConstrainedNeuron id

    def codes(self, neurons=None, experiments=None, kind='binary', tres=20000, phase=0):
        """Returns a Codes object, a 2D array where each row is a neuron code constrained to the time range of this Recording,
        or if specified, to the time ranges of Experiments in this Recording"""
        if neurons != None:
            if neurons.__class__ == list: # is a list of neuron ids, preserve their order
                neurons = [ self.n[ni] for ni in neurons ] # build up list of Neurons, ordered according to the id list in neurons
            else: # assume neurons is a dict of neurons
                neurons = list(neurons.values()) # convert to list of Neurons
        else:
            neurons = list(self.n.values()) # list of Neurons
        if experiments != None:
            # need to preserve order of expids as specified
            if experiments.__class__ == list:
                try:  # assume is a list of Experiment ids?
                    tranges = [ self.e[ei].trange for ei in experiments ]
                except: # assume is a list of Experiments
                    tranges = [ e.trange for e in experiments ]
            else: # assume experiments is a dict of Experiments
                tranges = [ e.trange for e in experiments.values() ]
        else: # no experiments specified, use whole Recording trange
            tranges = [self.trange]
        codeso = Codes(neurons=neurons, kind=kind, tranges=tranges, tres=tres, phase=phase)
        codeso.calc()
        return codeso
    codes.__doc__ += '\n\nCodes object:\n' + Codes.__doc__

    def codecorr(self, neuron1, neuron2, **kwargs):
        """Calculates the correlation of two Neuron.Code (or ConstrainedNeuron.Code)
        objects. Uses naive corrcoef() f'n defined by me. SLOWWWWWWWWWWWW!!!!!!!!!!!!!!!!!!!!!!!!!"""
        code1 = self.code(neuron1, **kwargs)
        code2 = self.code(neuron2, **kwargs)
        return corrcoef(code1.c, code2.c)
    codecorr.__doc__ += '\n\n**kwargs:'
    #codecorr.__doc__ += '\nNeuron.code: '+getargstr(Neuron.Neuron.code) # causes import problems
    #codecorr.__doc__ += '\nbinary: '+getargstr(Neuron.BinaryCode.__init__) # causes import problems

    def codecorrpdf(self, experiments=None, **kwargs):
        """Returns an existing CodeCorrPDF object, or creates a new one if necessary"""
        try:
            self._codecorrpdfs
        except AttributeError: # doesn't exist yet
            self._codecorrpdfs = [] # create a list that'll hold CodeCorrPDF objects
        cco = CodeCorrPDF(recording=self, experiments=experiments, **kwargs) # init a new one
        for ccpdf in self._codecorrpdfs:
            if cco == ccpdf: # need to define special == method for class CodeCorrPDF()
                return ccpdf # returns the first object whose attributes match what's desired. This saves on calc() time and avoids duplicates in self._codecorrpdfs
        cco.calc() # no matching object was found, calculate it
        self._codecorrpdfs.append(cco) # add it to the object list
        return cco
    codecorrpdf.__doc__ += '\n\n**kwargs:'
    codecorrpdf.__doc__ += '\nCodeCorrPDF: '+getargstr(CodeCorrPDF.__init__)
    #codecorrpdf.__doc__ += '\nNeuron.code: '+getargstr(Neuron.Neuron.code) # causes import problems
    #codecorrpdf.__doc__ += '\nbinary: '+getargstr(Neuron.BinaryCode.__init__) # causes import problems

    '''
    def codewords(self, **kwargs):
        cw = CodeWords(tranges=self.tranges)
        cw.calc()
        return cw
    '''


class Schneidman(object):
    """see 2006 Schneidman figs 1e and 1f"""
    def __init__(self, recording, experiments=None):
        self.r = recording
        if experiments == None:
            self.tranges = [self.r.trange] # or should we check to see if this Recording has a tranges field due to appending Neurons?
        else:
            experiments = tolist(experiments)
            try:
                self.tranges = [ e.trange for e in experiments ] # is experiments a list of Experiments?
            except AttributeError:
                self.tranges = [ self.r.e[ei].trange for ei in experiments ] # assume experiments is a list of experiment ids
                experiments = [ self.r.e[ei] for ei in experiments ] # convert to a list of Experiments
        self.experiments = experiments # save list of Experiments (could potentially be None)
        self.neurons = self.r.n

    def codes(self, nis=None, kind='binary', tres=20000, phase=0):
        """Returns the appropriate Codes object, depending on the recording
        and experiments defined for this Schneidman object"""
        return self.r.codes(neurons=nis, experiments=self.experiments, kind=kind, tres=tres, phase=phase)

    def intcodes(self, nis=None, **kwargs):
        """Given neuron indices (ordered LSB to MSB top to bottom), returns an array of the integer representation
        of the neuronal population binary code for each time bin"""
        if nis == None:
            nis = self.neurons.keys()
        return binaryarray2int(self.codes(nis=nis, kind='binary', **kwargs).c)

    def intcodesPDF(self, nis=None, **kwargs):
        """Returns the pdf across all possible population binary code words,
        labelled according to their integer representation"""
        if nis == None:
            nis = self.neurons.keys()
        intcodes = self.intcodes(nis=nis, **kwargs)
        nbits = len(nis)
        p, bins = histogram(intcodes, bins=arange(2**nbits), normed='pmf')
        return p, bins

    def intcodesFPDF(self, nis=None, **kwargs):
        """Returns the probability of getting each population binary code word, assuming independence between neurons,
        taking into account each neuron's spike (and no spike) probability"""
        if nis == None:
            nis = self.neurons.keys()
        nbits = len(nis)
        intcodes = arange(2**nbits)
        #neurons = dict( (ni, self.neurons[ni]) for ni in nis )
        codeso = self.codes(nis=nis, kind='binary', **kwargs)
        spikeps = [] # list spike probabilities for all neurons
        for neuroncode in codeso.c: # for each neuron, ie each row
            spikeps.append( neuroncode.sum() / float(neuroncode.size) ) # calc the average p of getting a spike for this neuron, within any time bin
        spikeps = array(spikeps, ndmin = 2) # convert to an nbits*1 array, make sure it's explicitly treated as a 2D array that can be transposed, or something
        nospikeps = 1 - spikeps
        #print 'spikesps: ', spikeps.__repr__()
        #print 'nospikesps: ', nospikeps.__repr__()
        binarytable = getbinarytable(nbits)
        pon = binarytable * spikeps.transpose() # 2D array of probs of having a 1 in the right place for all possible population code words
        poff = (1 - binarytable) * nospikeps.transpose() # 2D array of probs of having a 0 in the right place for all possible population code words
        #print 'pon', pon.__repr__()
        #print 'poff', poff.__repr__()
        x = pon + poff # add the 2D arrays, each has zero prob values where the other has non-zero prob values
        #print 'x', x.__repr__()
        intcodeps = x.prod(axis=0) # take the product along the 0th axis (the columns) to get the prob of each population code word
        return intcodeps, intcodes

    def scatter(self, nis=None, nbits=DEFAULTCODEWORDLENGTH, randomneurons=False, shufflecodes=False, **kwargs):
        """Scatterplots the expected probabilities of all possible population codes (y axis) vs their observed probabilities (x axis)
        See Schneidman Figure 1f"""
        print 'shufflecodes ain''t implemented yet, eh'
        if nis == None:
            nis = self.neurons.keys()
            nis.sort() # make sure they're in increasing order
        if nbits == None: # use all neuron ids specified in nis
            nbits = len(nis)
        if randomneurons:
            nis = random.sample(nis, nbits) # randomly sample nbits of the nis
        else:
            nis = nis[:nbits] # use just the first nbits neurons to make your words
        self.nbits = nbits
        print 'neurons:', nis
        self.pobserved, self.observedwords = self.intcodesPDF(nis=nis, **kwargs)
        self.pexpected, self.expectedwords = self.intcodesFPDF(nis=nis, **kwargs) # expected, assuming independence
        assert (self.observedwords == self.expectedwords).all() # make sure we're comparing apples to apples
        f = figure()
        a = f.add_subplot(111)
        a.plot([10**-6, 1], [10**-6, 1], 'b-') # plot an x=y line
        a.hold(True)

        self.tooltip = wx.ToolTip(tip='tip with a long %s line and a newline\n' % (' '*100)) # create a long tooltip with newline to get around bug where newlines aren't recognized on subsequent self.tooltip.SetTip() calls
        self.tooltip.Enable(False) # leave disabled for now
        self.tooltip.SetDelay(0) # set popup delay in ms
        gcfm().canvas.SetToolTip(self.tooltip) # connect the tooltip to the canvas
        f.canvas.mpl_connect('motion_notify_event', self.onmotion)

        # pylab.scatter(pobserved, pexpected), followed by setting the x and y axes to log scale freezes the figure and runs 100% cpu
        # gca().set_xscale('log')
        # gca().set_yscale('log')
        # use loglog() instead

        # colour each scatter point according to how many 1s are in the population code word it represents.
        # This is done a bit nastily, could use a cleanup:
        inds = []
        for nspikes in range(0,5):
            inds.append([])
            [ inds[nspikes].append(i) for i in range(0,2**nbits) if bin(i).count('1') == nspikes ]
        pobserved = self.pobserved.copy() # make local copies that are safe to modify for colour plotting and shit
        pexpected = self.pexpected.copy()
        pobserved1 = pobserved[inds[1]]; pexpected1 = pexpected[inds[1]]
        pobserved2 = pobserved[inds[2]]; pexpected2 = pexpected[inds[2]]
        pobserved3 = pobserved[inds[3]]; pexpected3 = pexpected[inds[3]]
        pobserved4 = pobserved[inds[4]]; pexpected4 = pexpected[inds[4]]
        pobserved[inds[1]], pexpected[inds[1]] = None, None # remove all these
        pobserved[inds[2]], pexpected[inds[2]] = None, None
        pobserved[inds[3]], pexpected[inds[3]] = None, None
        pobserved[inds[4]], pexpected[inds[4]] = None, None
        a.loglog(pobserved, pexpected, 'k.') # plots what's left in black
        a.loglog(pobserved4, pexpected4, 'm.')
        a.loglog(pobserved3, pexpected3, 'c.')
        a.loglog(pobserved2, pexpected2, 'y.')
        a.loglog(pobserved1, pexpected1, 'r.')

        gcfm().frame.SetTitle(lastcmd())
        #gcfm().frame.SetTitle('r%d.e[%d].schneidman.scatter(nbits=%s, randomneurons=%s, shufflecodes=%s)' % (self.e.r.id, self.e.id, nbits, randomneurons, shufflecodes))
        title('neurons: %s' % repr(nis))
        a.set_xlabel('observed population code probability')
        a.set_ylabel('expected population code probability')

    def onmotion(self, event):
        """Called during mouse motion over scatterplot figure. Pops up the corresponding
        population code word and its int representation when hovering over a neuron scatter point"""
        if event.xdata != None and event.ydata != None: # if mouse is inside the axes
            i  = approx(event.xdata, self.pobserved, rtol=5e-2, atol=0).nonzero()[0] # find for what indices (if any) xdata == pobserved
            ii = approx(event.ydata, self.pexpected[i], rtol=1e-1, atol=0).nonzero()[0] # for those above, find for what index (if any) ydata == pexpected
            codeis = i[ii]
            if codeis.size != 0:
                #tip += 'i: %s' % repr(i)
                #tip += '\nii: %s' % repr(ii)
                #tip += '\ncodeis: %s' % repr(codeis)
                intcodes = self.observedwords[codeis] # get the int rep for those indices from self.observedwords[i] or self.expectedwords[i]
                tip = 'intcodes: %s' % repr(intcodes)
                codes = [ bin(intcode, minbits=self.nbits) for intcode in intcodes ]
                tip += '\ncodes: %s' % repr(codes)
                self.tooltip.SetTip(tip) # update the tooltip
                self.tooltip.Enable(True) # make sure it's enabled
            else:
                self.tooltip.Enable(False) # disable the tooltip
        else: # mouse is outside the axes
            self.tooltip.Enable(False) # disable the tooltip

    def nspikingPDF(self, nbits=None, **kwargs):
        """Returns the PDF of observing n cells spiking in the same population code time bin"""
        print 'INCOMPLETE!!!!!!!!!!!!!!!!!!!!!!!!'
        pobserved, observedwords = self.intcodesPDF(nbits=nbits, **kwargs)
        nspiking = [] # collect observances of the number of cells spiking for each pop code time bin
        for observedword in observedwords: # slow hack
            nspiking.append( np.binary_repr(observedword).count('1') ) # convert words to binary, count the number of 1s in each
        pnspiking, bins = histogram(nspiking, bins=arange(nbits), normed='pmf') # histogram 'em
        return pnspiking, bins

    def nspikingFPDF(self, nbits=None, **kwargs):
        """Returns the PDF of observing n cells spiking in the same population code time bin, assuming independence by shuffling each cell's code train"""
        print 'INCOMPLETE!!!!!!!!!!!!!!!!!!!!!!!!'
        pass

    def plot_pdf(self, nbits=None, **kwargs):
        """Plots nspikingPDF and nspikingFPDF together. See 2006 Schneidman fig 1e"""
        print 'INCOMPLETE!!!!!!!!!!!!!!!!!!!!!!!!'
        nspikingPDF
        nspikingFPDF
    '''
    class plot(object):
        """Would allow you to do r92.e[0].schneidman().plot().scatter()"""
        def scatter():
            pass
        def pdf():
            pass
    '''

class RecordingSchneidman(BaseRecording):
    """Mix-in class that defines the spike code related Schneidman methods"""
    def schneidman(self, experiments=None):
        """Returns a Schneidman object"""
        so = Schneidman(recording=self, experiments=experiments)
        return so


class Recording(RecordingRaster,
                RecordingCode,
                RecordingSchneidman,
                BaseRecording):
    """Inherits all the Recording classes into a single Recording class"""
    pass
