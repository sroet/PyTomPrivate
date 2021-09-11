'''
Created on Jan 12, 2010

macros.py : Collection of macros

@author: hrabe
'''

def volumesSameSize(v1,v2):
    """
    volumesSameSize: checks sizes of v1 and v2
    @return: True if both volumes have the same size.
    """
    return (v1.sizeX() == v2.sizeX() and v1.sizeY() == v2.sizeY() and v1.sizeZ() == v2.sizeZ())

def frange(start,stop,step):
    """
    frange: Generate a list of float values 
    @param start:    
    @param stop:    
    @param step:    
    @return: List of float values
    """
    step *= 2*((stop>start)^(step<0))-1
    return [start+i*step for i in range(int((stop-start)/step))]