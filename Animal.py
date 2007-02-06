"""Defines the Animal, Cat, and Rat classes"""

#print 'importing Animal'

from Core import *
from Core import _data # ensure it's imported, in spite of leading _

class Animal(object):
    """An abstract Animal class, not meant to be instantiated directly.
    An Animal can have multiple Tracks. Animals are identified by their full name
    for clarity, since ids could be confusing (would id==5 mean Cat 5 or Rat 5?)"""
    def __init__(self, name=None, parent=None):
        self.level = 1 # level in the hierarchy
        self.treebuf = StringIO.StringIO() # create a string buffer to print tree hierarchy to
        self.d = parent # save the parent Data object
        self.name = name
        self.path = self.d.path + self.name + SLASH
        self.d.a[self.name] = self # add/overwrite this Animal to its parent's dict of Animals, in case this Animal wasn't loaded by its parent
        self.t = {} # store Tracks in a dictionary
    def tree(self):
        """Print tree hierarchy"""
        print self.treebuf.getvalue(),
    def writetree(self, string):
        """Write to self's tree buffer and to parent's too"""
        self.treebuf.write(string)
        self.d.writetree(string)
    def load(self):

        from Track import Track

        treestr = self.level*TAB + self.name + '/'
        self.writetree(treestr+'\n'); print treestr # print string to tree hierarchy and screen
        trackNames = [ dirname for dirname in os.listdir(self.path) if os.path.isdir(self.path+dirname) and dirname.startswith('Track ') ]
        for trackName in trackNames:
            track = Track(id=None, name=trackName, parent=self) # make an instance using just the track name (let it figure out the track id)
            track.load() # load the Track
            self.t[track.id] = track # save it
        #if len(self.t) == 1:
        #   self.t = self.t.values[0] # pull it out of the dictionary


class Cat(Animal):
    """This Animal is a Cat"""
    def __init__(self, id=DEFAULTCATID, parent=_data):
        id = pad0s(id, ndigits=2) # returns a string
        name = 'Cat ' + id
        self.id = int(id) # save it as an int
        super(Cat, self).__init__(name=name, parent=parent)
        #self.kind = 'Cat'


class Rat(Animal):
    """This Animal is a Rat"""
    def __init__(self, id=DEFAULTRATID, parent=_data):
        id = pad0s(id, ndigits=2) # returns a string
        name = 'Rat ' + id
        self.id = int(id) # save it as an int
        super(Rat, self).__init__(name=name, parent=parent)
        #self.kind = 'Rat'
