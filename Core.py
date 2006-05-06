'''Core neuropy functions and classes'''

DEFAULTDATAPATH = 'C:/data/' # the convention in neuropy will be that all 'path' var names have a trailing slash
DEFAULTCATID    = 15
DEFAULTTRACKID  = '7c'
DEFAULTRIPNAME  = 'liberal spikes' # a rip is the name of a spike sorting extraction; rips with the same name should have been done with the same templates, and possibly the same ripping thresholds
SLASH = '/' # use forward slashes instead of having to use double backslashes

import os, types, pprint, numpy, struct

pp = pprint.pprint

# need to delete the extra lines in all the textheaders, and uncomment some lines too!
# need to renumber .din filenames to have 0-based ids
# Rips should really have ids to make them easier to reference to: r[83].rip[0] instead of r[83].rip['conservative spikes'] - this means adding id prefixes to rip folder names (or maybe suffixes: 'conservative spikes.0.rip', 'liberal spikes.1.rip', etc...). Prefixes would be better cuz they'd force sorting by id in explorer (which uses alphabetical order) - ids should be 0-based of course
# worry about conversion of ids to strings: some may be only 1 digit and may have a leading zero!
# maybe make two load() f'ns for Experiment and Neuron: one from files, and a future one from a database
# make a save() f'n that pickles the object (including any of its results, like its STA, tuning curve points, etc)?

"""
def str2(data):
	if type(data) is types.IntTypes:
		s = str(data)
		if len(s) == 1:
			s = '0'+s # add a leading zero for single digits
"""

def txtdin2binarydin(fin,fout):
	fi = file(fin, 'r') # open the din file for reading in text mode
	fo = file(fout,'wb') # for writing in binary mode
	for line in fi:
		line = line.split(',')
		#print line[0], line[1]
		fo.write( struct.pack('@QQ',int(line[0]),int(line[1])) ) # read both values in as a C long longs, using the system's native ('@') byte order
	fi.close()
	fo.close()
	print 'Converted ascii din: ', fin, ' to binary din: ', fout
	# Code placed in Experiments class to convert all ascii .din to binary of the same filename:
	"""
		os.rename(self.path + self.name + '.din', self.path + self.name + '.din.txt')
		fin = self.path + self.name + '.din.txt'
		fout = self.path + self.name + '.din'
		txtdin2binarydin(fin,fout)
		os.remove(self.path + self.name + '.din.txt')
	"""


class Data(object): # use 'new-style' classes
	'''Data can have multiple Cats'''
	def __init__(self, dataPath=DEFAULTDATAPATH):
		self.path = dataPath
	def load(self):
		self.c = {} # store Cats in a dictionary
		catNames = [ dirname for dirname in os.listdir(self.path) if os.path.isdir(self.path+dirname) and dirname.startswith('Cat ') ] # os.listdir() returns all dirs AND files
		for catName in catNames:
			cat = Cat(id=None, name=catName, parent=self) # make an instance using just the catName (let it figure out the cat id)
			cat.load() # load the Cat
			self.c[cat.id] = cat # save it

class Cat(object):
	'''A Cat can have multiple Tracks'''
	def __init__(self, id=DEFAULTCATID, name=None, parent=Data):
		try:
			self.d = parent() # init parent Data object
		except TypeError: # parent is an instance, not a class
			self.d = parent # save parent Data object
		if id is not None:
			name = self.id2name(self.d.path,id) # use the id to get the name
		elif name is not None:
			id = self.name2id(name) # use the name to get the id
		else:
			raise ValueError, 'cat id and name can\'t both be None'
		self.id = id
		self.name = name
		self.path = self.d.path + self.name + SLASH
	def id2name(self, path, id):
		name = [ dirname for dirname in os.listdir(path) if os.path.isdir(path+dirname) and dirname.startswith('Cat '+str(id)) ]
		if len(name) != 1:
			raise NameError, 'Ambiguous or non-existent Cat id: '+str(id)
		else:
			name = name[0] # pull the string out of the list
		return name
	def name2id(self, name):
		id = name.replace('Cat ','',1) # replace first occurrence of 'Cat ' with nothing
		if not id:
			raise NameError, 'Badly formatted Cat name: '+name
		try:
			id = int(id) # convert string to int if possible
		except ValueError:
			pass # it's alphanumeric, leave it as a string
		return id
	def load(self):
		self.t = {} # store Tracks in a dictionary
		trackNames = [ dirname for dirname in os.listdir(self.path) if os.path.isdir(self.path+dirname) and dirname.startswith('Track ') ]
		for trackName in trackNames:
			track = Track(id=None, name=trackName, parent=self) # make an instance using just the track name (let it figure out the track id)
			track.load() # load the Track
			self.t[track.id] = track # save it

class Track(object):
	'''A Track can have multiple Recordings'''
	def __init__(self, id=DEFAULTTRACKID, name=None, parent=Cat):
		try:
			self.c = parent() # init parent Cat object
		except TypeError: # parent is an instance, not a class
			self.c = parent # save parent Cat object
		if id is not None:
			name = self.id2name(self.c.path,id) # use the id to get the name
		elif name is not None:
			id = self.name2id(name) # use the name to get the id
		else:
			raise ValueError, 'track id and name can\'t both be None'
		self.id = id
		self.name = name
		self.path = self.c.path + self.name + SLASH
	def id2name(self, path, id):
		name = [ dirname for dirname in os.listdir(path) if os.path.isdir(path+dirname) and dirname.startswith('Track '+str(id)) ]
		if len(name) != 1:
			raise NameError, 'Ambiguous or non-existent Track id: '+str(id)
		else:
			name = name[0] # pull the string out of the list
		return name
	def name2id(self, name):
		id = name.replace('Track ','',1) # replace first occurrence of 'Track ' with nothing
		if not id:
			raise NameError, 'Badly formatted Track name: '+name
		try:
			id = int(id) # convert string to int if possible
		except ValueError:
			pass # it's alphanumeric, leave it as a string
		return id
	def load(self):
		self.r = {} # store Recordings in a dictionary
		recordingNames = [ dirname for dirname in os.listdir(self.path) if os.path.isdir(self.path+dirname) and dirname[0:2].isdigit() and dirname.count(' - ') == 1 ] # 1st 2 chars in dirname must be digits, must contain exactly 1 occurrence of ' - '
		pp(recordingNames)
		for recordingName in recordingNames:
			recording = Recording(id=None, name=recordingName, parent=self) # make an instance using just the recording name (let it figure out the recording id)
			recording.load() # load the Recording
			self.r[recording.id] = recording # save it

class Recording(object):
	'''A Recording corresponds to a single SURF file, ie everything recorded between when
	the user hits record and when the user hits stop and closes the SURF file, including any
	pauses in between Experiments within that Recording. A Recording can have multiple Experiments,
	and multiple spike extractions, called Rips'''
	def __init__(self, id=None, name=None, parent=Track):
		try:
			self.t = parent() # init parent Track object
		except TypeError: # parent is an instance, not a class
			self.t = parent # save parent Track object
		if id is not None:
			name = self.id2name(self.t.path,id) # use the id to get the name
		elif name is not None:
			id = self.name2id(name) # use the name to get the id
		else:
			raise ValueError, 'recording id and name can\'t both be None'
		self.id = id
		self.name = name
		self.path = self.t.path + self.name + SLASH
	def id2name(self, path, id):
		name = [ dirname for dirname in os.listdir(path) if os.path.isdir(path+dirname) and dirname.startswith(str(id)+' - ') ]
		if len(name) != 1:
			raise NameError, 'Ambiguous or non-existent Recording id: '+str(id)
		else:
			name = name[0] # pull the string out of the list
		return name
	def name2id(self, name):
		try:
			id = name[0:name.index(' - ')] # everything before the first ' - ', index() raises ValueError if it can't be found
		except ValueError:
			raise ValueError, 'Badly formatted Recording name: '+name
		try:
			id = int(id) # convert string to int if possible
		except ValueError:
			pass # it's alphanumeric, leave it as a string
		return id
	def load(self):
		self.e = {} # store Experiments in a dictionary
		experimentNames = [ fname[0:fname.rfind('.din')] for fname in os.listdir(self.path) if os.path.isfile(self.path+fname) and fname.endswith('.din') ] # returns din filenames without their .din extension
		for (experimentid, experimentName) in enumerate(experimentNames): # experimentids will be according to alphabetical order of experimentNames
			experiment = Experiment(id=experimentid, name=experimentName, parent=self) # pass both the id and the name
			experiment.load() # load the Experiment
			self.e[experiment.id] = experiment # save it
		self.rip = {} # store Rips in a dictionary
		ripNames = [ dirname[0:dirname.rfind('.rip')] for dirname in os.listdir(self.path) if os.path.isdir(self.path+dirname) and dirname.endswith('.rip') ] # returns rip folder names without their .rip extension
		for ripName in ripNames:
			rip = Rip(name=ripName, parent=self) # pass just the name, ain't no such thing as a ripid, at least for now
			rip.load() # load the Rip
			self.rip[rip.name] = rip # save it
		try: # make the Neurons from the default rip (if it exists in the Recording path) available in the Recording, so you can access them via r.n[nid] instead of having to do r.rip[name].n[nid]. Make them just another pointer to the data in r.rip[DEFAULTRIPNAME].n
			self.n = self.rip[DEFAULTRIPNAME].n
			self.defaultrippath = self.path + DEFAULTRIPNAME + SLASH
		except:
			pass

class Experiment(object):
	'''An Experiment corresponds to a single contiguous VisionEgg stimulus session.
	It contains information about the stimulus during that session, including
	the DIN values and the text header'''
	def __init__(self, id=None, name=None, parent=Recording): # Experiment IDs are 1-based in the .din filenames, at least for now. They should be renamed to 0-based. Here, they're treated as 0-based
		try:
			self.r = parent() # init parent Recording object
		except TypeError: # parent is an instance, not a class
			self.r = parent # save parent Recording object
		if name is None:
			raise ValueError, 'experiment name can\'t be None'
		self.id = id # not really used by the Experiment class, just there for user's info
		self.name = name
		self.path = self.r.path
	# doesn't need a id2name or name2id method, neither can really be derived from the other in an easy, the id is just alphabetical order
	def load(self):
		f = file(self.path + self.name + '.din', 'rb') # open the din file for reading in binary mode
		self.din = numpy.fromfile(f, dtype=numpy.uint64).reshape(-1,2) # reshape to nrows x 2 columns
		f.close()
		f = file(self.path + self.name + '.textheader', 'r') # open the textheader file for reading
		self.textheader = f.read() # read it all in
		f.close()
		# then, for each line in the textheader, exec() it so you get self.varname saved directly within in the Experiment object - watch out, will try and make Movie() objects and Bar() objects, etc?

class Rip(object):
	def __init__(self, name=DEFAULTRIPNAME, parent=Recording):
		try:
			self.r = parent() # init parent Recording object
		except TypeError: # parent is an instance, not a class
			self.r = parent # save parent Recording object
		if name is None:
			raise ValueError, 'rip name can\'t be None'
		# rips don't have ids, at least for now. Just names
		self.name = name
		self.path = self.r.path + self.name + '.rip' + SLASH # have to add .rip extension to rip name to get its actual folder name
	def load(self):
		self.n = {} # store Neurons in a dictionary
		neuronNames = [ fname[0:fname.rfind('.spk')] for fname in os.listdir(self.path) if os.path.isfile(self.path+fname) and fname.endswith('.spk') ] # returns spike filenames without their .spk extension
		for neuronName in neuronNames:
			neuron = Neuron(id=None, name=neuronName, parent=self) # make an instance using just the neuron name (let it figure out the neuron id)
			neuron.load() # load the neuron
			self.n[neuron.id] = neuron # save it
		# then, maybe add something that loads info about the rip, say from some file describing the template used, and all the thresholds, exported to the same folder by SURF
		# maybe also load the template used for the rip, perhaps also stored in the same folder

class Neuron(object):
	'''A Neuron object's spike data spans all the Experiments within a Recording.
	If different Recordings have Rips with the same name, you can assume that the
	same spike template was used for all of those Recordings, and that therefore
	the neuron ids are the same'''
	def __init__(self, id=None, name=None, parent=Rip): # neuron names don't include the '.spk' ending, although neuron filenames do
		try:
			self.rip = parent() # init parent Rip object
		except TypeError: # parent is an instance, not a class
			self.rip = parent # save parent Rip object
		if id is not None:
			name = self.id2name(self.rip.path,id) # use the id to get the name
		elif name is not None:
			id = self.name2id(name) # use the name to get the id
		else:
			raise ValueError, 'neuron id and name can\'t both be None'
		self.id = id
		self.name = name
		self.path = self.rip.path
	def id2name(self, path, id):
		name = [ fname[0:fname.rfind('.spk')] for fname in os.listdir(path) if os.path.isfile(path+fname) and \
		             ( fname.find('_t'+str(id)+'.spk')!=-1 or fname.find('_t0'+str(id)+'.spk')!=-1 or fname.find('_t00'+str(id)+'.spk')!=-1 ) ] # have to deal with leading zero ids, go up to 3 digit ids, should really use a re to do this properly...
		if len(name) != 1:
			raise NameError, 'Ambiguous or non-existent Neuron id: '+str(id)
		else:
			name = name[0] # pull the string out of the list
		return name
	def name2id(self, name):
		try:
			id = name[name.rindex('_t')+2::] # everything from just after the last '_t' to the end of the neuron name, index() raises ValueError if it can't be found
		except ValueError:
			raise ValueError, 'Badly formatted Neuron name: '+name
		try:
			id = int(id) # convert string to int if possible
		except ValueError:
			pass # it's alphanumeric, leave it as a string
		return id
	def load(self): # or loadspikes()?
		f = file(self.path + self.name + '.spk', 'rb') # open the spike file for reading in binary mode
		self.spikes = numpy.fromfile(f, numpy.uint64) # read it all in
		f.close()
"""
class Stim(Experiment):
	'''A Stim contains the visual stimulus information for a single Experiment. A Stim corresponds
	to a single contiguous VisionEgg stimulus session'''
	def __init__(self,fname):
		pass
	def load(self,fname):
		pass
"""
