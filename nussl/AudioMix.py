"""
This module implements an audio mixture generator. The mixture types include: instantaneous,
anechoic, and convolutive. 

Required packages:
1. Numpy
2. Scipy
3. Matplotlib
"""

import numpy as np
from scipy.fftpack import fft,ifft
import matplotlib.pyplot as plt


def mkmixture(sn, mixparam, fs, rsch=False):
    """"
    The function mkmixture synthesizes an M-channel convolutive mixture of N sources
    
    Parameters:
        sn: Numpy N by Ls array. Each row contains a single channel time-domain source signal.
        mixparam: list containing locations of sources/mics and room parameters
                  - Ps: Numpy N by 3 array containing source locations (x,y,z coordinates)
                  - Pm: Numpy M by 3 array containing mic locations (x,y,z, coordinates)
                  - RoomParams: Numpy 1 by 2 array containing room characteristics
                                - number of virtual sources
                                - reflection coefficients in (-1,1)
                  - RoomDim: Numpy 1 by 3 array containing room dimensions

        fs: sampling rate (in Hz)
        rsch: logical argument indicating whether the room schematic should be generated or not. Default is False.
          
    Returns:
        Mixtures, a Numpy M by Lx array. Each row contains a single channel time-domain mixture

        SourceIMS, a Numpy N by M by Lx array containing time-domain samples of source images

        H, a M by N list containing impulse responses of M*N accoustic channels between sources and mics
    """
    
    # find the number of sources and signal lengths
    N,Ls=np.shape(sn)
     
    # extract locations of sources and mics
    Ps=mixparam[0]    
    Pm=mixparam[1]
    M=Pm.shape[0]
    
    # extract room parameters
    NumVir=mixparam[2][0]
    RefCoeff=mixparam[2][1]
    Rdim=mixparam[3]
    
    # compute room impulse response for source-mic pairs
    
    H=[]
    Lh=np.zeros((M,N))
    for i in range(0,M):
        hm=[]
        for j in range(0,N):
            hmn=rir(Rdim,Pm[i,:],Ps[j,:],NumVir,RefCoeff,fs)
            hm.append(hmn)
            Lh[i,j]=np.size(hmn)
        H.append(hm)
    
    # compute mixtures
    Lhmax=int(Lh.max())
    Lx=Ls+Lhmax-1
    Mixtures=np.zeros((M,Lx))
    SourceIMS=np.zeros((N,M,Lx))
    
    for i in range(0,M):
        for j in range(0,N):
            hmn=H[i][j]
            xm=fastconv(np.array(sn[j,:],ndmin=2),hmn)
            Lxm=np.shape(xm)[1]
            SourceIMS[j,i,0:Lxm]=xm
            Mixtures[i,0:Lxm]=Mixtures[i,0:Lxm]+xm
            
            
    # plot the recording setup if specified

    if rsch==True:
        
       SMarker = dict(color='red', linestyle='', marker='o',
                    markersize=10, markerfacecoloralt='red')
       plt.plot(Ps[:,0],Ps[:,1],**SMarker)
       
       MMarker = dict(color='blue', linestyle='', marker='s',
                    markersize=6, markerfacecoloralt='blue') 
                    
       plt.plot(Pm[:,0],Pm[:,1],**MMarker)
       plt.grid()
       plt.xlim((0,Rdim[0]))
       plt.ylim((0,Rdim[1]))
       plt.legend(['Sources','Mics'])
     
    return Mixtures,SourceIMS,H
    

def fastconv(x, h):
    """
    The function fastconv performs fast convolution (in freq. domain rather than in time domain). The original MATLAB
    implementation can be found on the Mathworks File Exchange at:
    http://www.mathworks.com/matlabcentral/fileexchange/5110-fast-convolution
    
    Parameters:
        x: Numpy row vector containing samples of the time-domain signal x[n]
        h: Numpy row vector containing samples of the time-domain signal h[n] which here is considered to be the impulse
         response of a channel

    Returns:
        y, a Numpy row vector containing samples of the time-domain signal y[n], the output of the
        channel h to an input signal x

    """
    
    Ly=x.shape[1]+h.shape[1]-1 
    Ly2=int(2**(np.ceil(np.log2(Ly)))) 
    
    X=fft(x,n=Ly2)
    H=fft(h,n=Ly2)
    Y=X*H
    y=np.real(ifft(Y,n=Ly2))
    y=np.array(y[0,0:Ly],ndmin=2)
    
    y=y*(np.abs(x).max()/np.abs(y).max())
   
    return y


def rir(Rdim, Mcoords, Scoords, Numvs, Rcoef, fs):
    """
    The function 'rir' computes the room impulse response given the recording setup 
    and the room features, using the mirror image method, 
    
    The original MATLAB implementation by Stephen G. McGovern can be found on the 
    Mathworks File Exchange at: 
    http://www.mathworks.com/matlabcentral/fileexchange/5116-room-impulse-response-generator
    
    References:
        McGovern, Stephen G. "Fast image method for impulse response calculations of box-shaped rooms."
        Applied Acoustics 70.1 (2009): 182-189.
    
    Parameters:
        Rdim: Numpy array containing the dimensions of the room (in meter)
        Mcoords: Numpy 1 by 3 array containing the x,y,z coordinates of the microphone (in meter)
        Scoords: Numpy 1 by 3 array containing the x,y,z coordinates of the sound source (in meter)
        Numvs: number of virtual sources will be (2*Numvs+1)**3
        Rcoef: reflection coefficinet for the walls, taking on a value in (-1,1)
        fs: sampling rate
    
    Returns:
        h, a Numpy 1 by Lh array containing the room impulse response

    Example:
        Rdim=np.array([20,19,21])
        Mcoords=np.array([19,18,1.6])
        Scoords=np.array([5,2,1])
        Numvs=1
        Rcoef=0.3
        fs=44100
        h = rir(Rdim,Mcoords,Scoords,Numvs,Rcoef,fs)
     
    """
    
    Ind=np.arange(-Numvs,Numvs+1)
    RMS=Ind+0.5-0.5*((-1)**Ind)
    SRCS=(-1)**Ind
    
    xi=SRCS*Scoords[0]+RMS*Rdim[0]-Mcoords[0]
    yj=SRCS*Scoords[1]+RMS*Rdim[1]-Mcoords[1]
    zk=SRCS*Scoords[2]+RMS*Rdim[2]-Mcoords[2]
    
    i,j,k=np.meshgrid(xi,yj,zk)
    d=np.sqrt(i**2+j**2+k**2)
    time=(np.round(fs*d/343)+1).astype(int)
    
    e,f,g=np.meshgrid(Ind,Ind,Ind)
    c=Rcoef**(np.abs(e)+np.abs(f)+np.abs(g))
    E=c/d
    
    time=np.reshape(time,(time.shape[0]*time.shape[1]*time.shape[2],1))
    E=np.reshape(E,(E.shape[0]*E.shape[1]*E.shape[2],1))
    
    h=np.zeros((1,time.max()))
    h[0,time[:,0]-1]=E.T
       
    return h

