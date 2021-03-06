"""
# pseudo.py
#
# Contains functions:
#   y,DM    = chebdif(N,M),     Differentiation matrices (Chebyshev collocation)
#   DM      = poldif(x,M),      Differentiation matrices (Lagrange polynomial collocation)
#   w       = clencurt(N),      Clenshaw-Curtis weights
#   norm2   = chebnorm(vec,N),  2-norm using Clenshaw-Curtis weights
#   norm2   = chebnorm2(vec,N), 2-norm using Clenshaw-Curtis weights
#   norm1   = chebnorm1(vec,N), 1-norm using Clenshaw-Curtis weights
#   coeffs  = chebcoeffs(f),    Chebyshev coefficients from collocation
#   coll    = chebcoll_vec(a),  Collocation values from Chebyshev coefficients
#   interp  = chebint(fk,x),    Interpolation from Chebyshev grid to a general grid
#   integral= chebintegrate(f), Integrate function values with BC f(y=-1) = 0
"""
## ----------------------------------------------------
## ACKNOWLEDGEMENT

# Implementation for chebdif and poldif is based on Weideman and Reddy's differentiation suite for Matlab.
# Most of the code is A line-by-line translation of their functions.
# This translation is done, in spite of available pseudo-spectral differentiation codes since the Matlab
# suite incorporates features that improve accuracy, which becomes important for calculating higher derivatives.
# Notably, the chebdif function uses trigonometric identities in [0,pi/2] to calculate x(k)-x(j), and higher 
# derivatives are explicitly calculated, instead of using D*D*..

# The webpage for the differentiation suite:
# http://dip.sun.ac.za/~weideman/research/differ.html

# 'clencurt' is from a blog by Dr. Greg von Winckel:
#	http://www.scientificpython.net/pyblog/clenshaw-curtis-quadrature	
# However, a minor change has been made- only the weight matrix is returned, as opposed to returning both the weights
#		and the nodes, as in the origion version on the blog


# Sabarish Vadarevu
# Aerodynamics and Flight Mechanics group
# University of Southampton, United Kingdom
# Email: SBV1G13@SOTON.AC.UK
###--------------------------------------------------------

import numpy as np
from scipy.linalg import toeplitz
from scipy.fftpack import ifft

def chebdif(N,M):
    """ y,DM =chebdif(N,M):  Differentiation matrices for Chebyshev collocation.
    Inputs: 
        N:  Number of nodes
        M:  Number of derivatives
    Outputs:
        y:  Chebyshev collocation nodes on [1,-1], 1d np.ndarray of size N
        DM: Differentiation matrices of shape (N,N,M).
                Extract m^th differentiation matrix as Dm = DM[:,:,m-1].reshape((N,N))
                For m^th derivative, invoke as 
                    f_m = np.dot(Dm, f), where f is a vector of function values on nodes 'y'
    """
    I = np.identity(N)		# Identity matrix
    #L = bool(I)

    n1 = np.int(np.floor(N/2.))		# Indices for flipping trick
    n2 = np.int(np.ceil(N/2.))

    # Theta vector as column vector
    k=np.vstack(np.linspace(0.,N-1.,N))		
    th=k*np.pi/(N-1.)

    x=np.sin( np.pi* np.vstack( np.linspace(N-1.,1.-N,N) ) /2./(N-1.) )	# Chebyshev nodes

    T = np.tile(th/2.,(1,N))
    DX= 2.*np.sin(T.T+T)*np.sin(T.T-T)	# Compute dx using trigonometric identity, improves accuracy

    DX= np.vstack((DX[0:n1,:], np.flipud(np.fliplr([-1.*el for el in DX[0:n2,:]]))))
    DX = DX+I			# Replace 0s in diagonal by 1s (required for calculating 1/dx)

    C= toeplitz(pow(-1,k))			# Matrix with entries c(k)/c(j)
    C[0,:] = [2.*el for el in C[0,:]]	
    C[N-1,:] = [2.*el for el in C[N-1,:]]
    C[:,0] = [el/2. for el in C[:,0]]
    C[:,N-1] = [el/2. for el in C[:,N-1]]


    Z = [1./el for el in DX]		# Z contains 1/dx, with zeros on diagonal
    Z = Z - np.diag(np.diag(Z))

    D = np.identity(N)
    DM = np.zeros((N,N,M))			# Output matrix, contains 'M' derivatives

    for ell in range(0,M):
        D[:,:] = Z*(C*(np.tile(np.diag(D),(N,1)).T)-D)	
        D[:,:] = [(ell+1)*l for l in D]			# Off-diagonal elements
        trc = np.array([-1.*l for l in np.sum(D.T,0)])
        D = D - np.diag(np.diag(D)) + np.diag(trc)	# Correcting the main diagonal
        DM[:,:,ell] = D

    # Return collocation nodes as a 1-D array
    return  x[:,0] , DM


def poldif(x,M):
    """DM = poldif(x,M): Differentiation on nodes using Lagrange interpolation polynomials
    Inputs:
        x:  Collocation nodes
        M:  Number of derivatives needed
    Outputs:
        DM: Differentiation matrices of shape (x.size,x.size,M).
                Extract m^th differentiation matrix as Dm = DM[:,:,m-1].reshape((x.size,x.size))
                For m^th derivative, invoke as 
                    f_m = np.dot(Dm, f), where f is a vector of function values on nodes 'x'
    """
    N= np.size(x)
    x = np.vstack(np.array(x))
    a,b = x.shape
    if b != 1:
            print ('x is not a vector')

    alpha = np.ones((N,1))
    B = np.zeros((M,N))

    I = np.identity(N)

    XX = np.tile(x,(1,N))
    DX=XX-XX.T
    DX = DX + I

    c = np.ones((N,1))
    np.prod(DX,axis=1,out=c)

    C = np.tile(c, (1,N))
    C = C/C.T

    Z = np.array([1./l for l in DX])
    Z = Z - np.diag(np.diag(Z))

    X = Z.T

    X = np.delete(X.T,np.linspace(0,N*N-1,N))
    X = (X.reshape((N,N-1))).T

    Y = np.ones((N-1,N))
    D = np.identity(N)
    DM = np.ones((N,N,M))

    for ell in range(0,M):
        Y = np.cumsum(np.vstack((B[ell,:], (ell+1.)*Y[0:N-1,:]*X)) , axis=0,dtype=float)
        D = (ell+1.)*Z*(C*(np.tile(np.diag(D),(N,1)).T)-D)
        D = D - np.diag(np.diag(D)) + np.diag(Y[N-1,:])
        DM[:,:,ell] = D

    return DM
	
	
	
def clencurt(N):
    """ w = clencurt(N): Computes the Clenshaw Curtis weights on Chebyshev nodes
    Inputs:
        N:  Number of Chebyshev collocation nodes
    Outputs:
        w:  1-d numpy array of weights
    To integrate a function, given as a 1-d array of values 'f' on 'N' Chebyshev nodes 'y', 
        f_int = np.dot(w,f)"""
    n1 = N
    if n1 == 1:
        x = 0
        w = 2
    else:
        n = n1 - 1
        C = np.zeros((n1,2),dtype=np.float)
        k = 2*(1+np.arange(int(np.floor(n/2))))
        C[::2,0] = 2/np.hstack((1., 1.-k*k))
        C[1,1] = -n
        V = np.vstack((C,np.flipud(C[1:n,:])))
        F = np.real(ifft(V, n=None, axis=0))
        x = F[0:n1,1]
        w = np.hstack((F[0,0],2*F[1:n,0],F[n,0]))
    return w

def _chebdotvec(arr1,arr2,N):
    # This function computes inner products of vectors ONLY.
    assert (arr1.ndim == 1) and (arr2.ndim == 1), "For dot products of non-1d-arrays, use chebdot()"

    prod = (np.array(arr1) * np.array(arr2).conjugate() )
    prod = prod.reshape((arr1.size//N, N))
    wvec = clencurt(N).reshape((1,N))

    return 0.5* np.sum( (prod*wvec).flatten() )


def chebnorm(arr,N):
    """ norm2 = chebnorm(arr,N): Returns 2-norm of array 'arr', weighted by clencurt weights (see clencurt(N)) 
    Inputs:
        arr:    np.ndarray whose size is an integral multiple of N
                    Can be multi-dimensional.
        N:      Number of Chebyshev collocation nodes
    Outputs:
        norm:   2-norm, weighted by clenshaw-curtis weights."""
    return np.sqrt(np.abs(_chebdotvec(arr.flatten(),arr.flatten(),N) ))


def chebdot(arr1,arr2,N):
    """ dotArr = chebdot(arr1, arr2, N): Dot products on Chebyshev nodes using clencurt weights
    Inputs:
        arr1: np.ndarray (possibly 2-d) whose size is an integral multiple of N
        arr2: np.ndarray (possibly 2-d) whose size is an integral multiple of N
            arr1 and arr2 must have same size in their last axis
    Outputs:
        dotArr : float of dot product if arr1 and arr2 are 1d
                 2-d array otherwise
        """
    if (arr1.ndim==1) and (arr2.ndim == 1): return _chebdotvec(arr1,arr2,N)
    # Nothing special to be done if both are 1d arrays

    # The arguments arr1 and arr2 can either be vectors or matrices
    if (arr1.ndim ==1):
        arr1 = arr1.reshape((1,arr1.size))
    if (arr2.ndim ==1):
        arr2 = arr2.reshape((1,arr2.size))
    dotArr = np.zeros((arr1.shape[0], arr2.shape[0]))
    for ind1 in range(arr1.shape[0]):
        for ind2 in range(arr2.shape[0]):
            dotArr[ind1,ind2] = _chebdotvec(arr1[ind1],arr2[ind1],N)
    
    return dotArr 

def chebnorm1(arr,N):
    """ norm1 = chebnorm(arr,N): Returns 1-norm of array 'arr', weighted by clencurt weights (see clencurt(N)) 
    Inputs:
        arr:    np.ndarray whose size is an integral multiple of N
                    Can be multi-dimensional.
        N:      Number of Chebyshev collocation nodes
    Outputs:
        norm:   1-norm, weighted by clenshaw-curtis weights."""
    return _chebdotvec( np.abs(arr.flatten())   , np.ones(arr.size) , N) 

def chebnorm2(vec,N):
    """ norm2 = chebnorm(arr,N): Returns 2-norm of array 'arr', weighted by clencurt weights (see clencurt(N)) 
    Inputs:
        arr:    np.ndarray whose size is an integral multiple of N
                    If multi-dimensional, arr is flattened.
                    If size > N, each 'N' elements are normed individually, and their total is added.
        N:      Number of Chebyshev collocation nodes
    Outputs:
        norm:   2-norm, weighted by clenshaw-curtis weights."""
    return chebnorm(vec,N)

def _chebcoeffsvec(f):
    f = f.flatten(); N = f.size
    a =  np.fft.fft(np.append(f,f[N-2:0:-1]))  
    a = a[:N]/(N-1.)*np.concatenate(([0.5],np.ones(N-2),[0.5]))
    return a


def chebcoeffs(f):
    """coeffs = chebcoeffs(f): Coefficients of Chebyshev polynomials (first kind) for given collocated values.
    Inputs:
        f: Function values on 'N' Chebyshev nodes (N= f.size if f is 1d)
            Can be multi-dimensional
            If f is multidimensional, the last axis size is taken as N
    Outputs:
        coeffs: Array of coefficients of Chebyshev polynomials (first kind) from 0 to N-1""" 
    if (f.ndim == 1):
        return _chebcoeffsvec(f)
    
    shape = f.shape
    N= f.shape[-1]
    f = f.reshape((f.size//N, N))

    coeffArr = f.copy()
    for ind in range(f.shape[0]):
        coeffArr[ind] = _chebcoeffsvec(f[ind])
    coeffArr = coeffArr.reshape(shape)

    return coeffArr


def _chebcoll_vec_vec(a):
    a = a.flatten()
    
    N = a.size
    a = a*(N-1.)/np.concatenate(([0.5],np.ones(N-2),[0.5]))

    f = np.fft.ifft(np.append(a,a[N-2:0:-1]))
    
    return f[:N]
	
def chebcoll_vec(a):
    """coll = chebcoll_vec(f): Function values on Chebyshev nodes, given coefficients of Chebyshev polynomials (first kind).
    Inputs:
        a: N Chebyshev polynomial coefficients (N= a.size if a is 1d)
            Can be multi-dimensional
            If a is multidimensional, the last axis size is taken as N
    Outputs:
        coeffs: Array of function values on Chebyshev nodes, same shape as 'a' """ 
    if (a.ndim == 1):
        return _chebcoll_vec_vec(a)
    
    shape = a.shape
    N= a.shape[-1]
    a = a.reshape((a.size//N, N))

    f = a.copy()
    for ind in range(a.shape[0]):
        f[ind] = _chebcoll_vec_vec(a[ind])
    f = f.reshape(shape)
    return f



def chebint(fk, x):
    """ interp = chebint(fk,x): Interpolate function 'fk' from Chebyshev nodes to 'x'
    Inputs:
        fk: Function values on 'N' Chebyshev nodes, N = fk.size
        x:  Nodes on which f has to be interpolated (in [1,-1])
    Outputs:
        interp: Function values on x
    """
    assert fk.ndim == 1
    speps = np.finfo(float).eps # this is the machine epsilon
    N = np.size(fk)
    M = np.size(x)
    xk = np.sin(np.pi*np.arange(N-1,1-N-1,-2)/(2*(N-1)))
    w = np.ones(N) * (-1)**(np.arange(0,N))
    w[0] = w[0]/2
    w[N-1] = w[N-1]/2
    D = np.transpose(np.tile(x,(N,1))) - np.tile(xk,(M,1))
    D = 1/(D+speps*(D==0))
    p = np.dot(D,(w*fk))/(np.dot(D,w))
    return p
    
def _chebintegratevec(v):
    assert v.ndim == 1
    coeffs = chebcoeffs(v)
    int_coeffs = np.zeros(v.size, dtype=coeffs.dtype)
    N = v.size

    # T_0 = 1,  T_1 = x, T_2 = 2x^2 -1
    # \int T_0 dx = T_1
    int_coeffs[1] = coeffs[0]

    # \int T_1 dx = 0.25*T_2 + 0.25*T_0
    int_coeffs[2] += 0.25*coeffs[1]
    int_coeffs[0] += 0.25*coeffs[1]

    # \int T_n dx = 0.5*[T_{n+1}/(n+1) - T_{n-1}/(n-1)]
    nvec = np.arange(0,N)
    int_coeffs[3:] += 0.5/nvec[3:]*coeffs[2:N-1]
    int_coeffs[1:N-1] -= 0.5/nvec[1:N-1]*coeffs[2:]

    int_coll_vec = chebcoll_vec(int_coeffs)
    return int_coll_vec - int_coll_vec[-1]

def chebintegrate(v):
    """ int_coll_vec = chebintegrate(v): Integral of function 'v', supposing BC v(y=-1) = 0
    Inputs: 
        v:  Function values on Chebyshev grid with N=v.size points if v is 1d
            If v is multi-dimensional, N = v.shape[-1], and integration is performed on all other axes
    Outputs:
        int_coll_vec: Integral of v, supposing BC v(y=-1) = 0
                        same shape as v""" 
    if v.ndim == 1:
        return _chebintegratevec(v)
    
    shape = v.shape
    N = v.shape[-1]

    v = v.reshape((v.size//N, N))
    integral = v.copy()
    for ind in range(v.shape[0]):
        integral[ind] = _chebintegratevec(v[ind])
    
    return integral.reshape(shape)

