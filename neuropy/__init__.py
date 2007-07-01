r"""Experimental and model neuronal and stimulus data analysis in Python

                         object hierarchies:

                                level:

                Data              0                Model
                  |                                  |
                Animal            1               System
                  |                                  |
                Track             2                  |
                  |                                  |
              Recording           3                 Run
             /         \                           /   \
       Experiment      Rip        4       Experiment    Rip
            |           |                      |         |
          Movie       Neuron      5          Movie     Neuron
"""

__author__ = "Martin Spacek"

#print 'importing neuropy'

from Core import *
from Core import _data # ensure it's imported, in spite of leading _, useful for user examination of default Data object

from Animal import Cat, Rat
from System import System
from Track import Track
from Recording import Recording
from Run import Run
from Experiment import Experiment
from Rip import Rip
from Movie import Movie, MSEQ32, MSEQ16
from Neuron import Neuron

from Test import test

# init and load some neuropy objects:
'''
print 'Initing and loading Track(\'7c\'):'
t = Track('7c')
t.load()'''
'''
print 'Initing and loading Recording(71):'
r71 = Recording(71)
r71.load()
''''''
print 'Initing and loading Recording(75):'
r75 = Recording(75)
r75.load()
''''''
print 'Initing and loading Recording(76):'
r76 = Recording(76)
r76.load()
''''''
print 'Initing and loading Recording(92):'
r92 = Recording(92)
r92.load()
'''