#%%writefile utils.py
"""

"""
import numpy as np
from lib import pseudo
from warnings import warn

_dealiasFun = lambda arr, y ,yDealias : pseudo.chebint(pseudo.chebint(arr,yDealias), y)
_kxFun = lambda a0, L0: a0 * np.concatenate((np.arange(L0), -L0 + np.arange(L0) ))
_kzFun = lambda b0, M0: b0 * np.arange(M0+1)

rowVec = lambda arr: arr.reshape((1,arr.size))
colVec = lambda arr: arr.reshape((arr.size,1))


def qdot_vm(vec, mat,q=None):
    """ Vector matrix dot product, q*( vec @ mat) returned as 1d array"""
    if q is None:
        q = pseudo.clencurt(vec.size)

    return ( (q*vec).reshape((1,vec.size)) @ mat ).ravel()

def qdot_mv(vec,mat,q=None):
    """ Matrix vector dot product, q*( mat @ vec) returned as 1d array"""
    if q is None:
        q = pseudo.clencurt(vec.size)

    return q * (mat @ vec.reshape((vec.size,1))).ravel()

def qnorm(arr,*args,**kwargs):
    if 'q' not in kwargs:
        if len(args) != 0 :
            N = args[0]
        else: 
            N = kwargs.get('N', arr.size)
        q = pseudo.clencurt(N)
    return np.linalg.norm( arr.reshape((-1,q.size)) * np.sqrt(q).reshape((1,q.size)),ord=2 )

def vel2state(vel, diffDict={}):
    """ 
        Get velocity-elements in state vector from velocity field
        Because velocity =  (1-y^2) * state, 
            going from state to velocity is fine, but the otherway is indeterminate at y=+- 1
        Match second derivatives at the walls to obtain state(y= +- 1)
    """
    if ('y' in diffDict) and ('D1' in diffDict) and ('D2' in diffDict):
        y = diffDict['y']; D1 = diffDict['D1']; D2 = diffDict['D2']
        N = diffDict.get('N', y.size)
    else :
        N = u.size
        y , DM = pseudo.chebdif(N,2)
        warn("Calling chebdif 2...")
        D1 = DM[:,:,0]
        D2 = DM[:,:,1]

    state = np.zeros(vel.shape, dtype=vel.dtype)
    state[1:-1] = vel[1:-1]/(1.-y**2)[1:-1] # Internal values are straight-forward
    vel_yy = D2 @ vel 
    
    # Coefficients of state[y= +- 1] to solve for second derivatives
    # See notebook for details
    coeffMat = np.zeros((2,2))
    coeffMat[0,0] = 2. + 4.*D1[0,0]
    coeffMat[0,1] = 4.*D1[0,-1]
    coeffMat[1,0] = -4.*D1[-1,0]
    coeffMat[1,1] = 2.-4.*D1[-1,-1]

    bVec = np.zeros((2,1))
    bVec[0] = -vel_yy[0 ] - 4.*np.sum(D1[0 ,1:-1] * state[1:-1])
    bVec[1] = -vel_yy[-1] + 4.*np.sum(D1[-1,1:-1] * state[1:-1])

    state_walls = np.linalg.solve(coeffMat, bVec)
    state[0 ] = state_walls[0]
    state[-1] = state_walls[-1]
    return state  

def calcDerivatives(state, kxArr, kzArr, flowDict={}, wavy=False):
    """
        Return fields and their y-derivatives after accounting for implicit BC on velocities
    Arguments:
        state: array of shape (2L, M+1,4,N) containing u,v,w,p, or flattened vector; 
            L is the number of positive streamwise Fourier modes
            M is the number positive spanwise Fourier modes
    Output:
        Array of shape (3,4,N). First index is derivative order; 0th index is the field itself
            Second index is the field: u,v,w,p. Third index is wall-normal profile. 
    """
    L = kxArr.size//2; M = kzArr.size -1
    
    state = state.reshape((2*L, M+1, 4, -1))
    
    diffDict = flowDict
    if (('y' in diffDict) and ('D1' in diffDict) and ('D2' in diffDict) ) :
        y = diffDict['y']
        D1 = diffDict['D1']
        D2 = diffDict['D2']
        N = y.size
    else :
        N = state.shape[-1]
        y, DM = pseudo.chebdif(N,2)
        warn("Calling chebdif 3...")
        D1 = np.ascontiguousarray(DM[:,:,0])
        D2 = np.ascontiguousarray(DM[:,:,1])
    
    
    #================================================
    # y-derivatives
    
    dy_state = state @ D1.T
    dy2_state = state @ D2.T
    
    y_derivatives = np.zeros((kxArr.size, kzArr.size, 3, 4, N),dtype=np.complex) # Third index corresponds to order of derivative
    # Third index = 0 is the original field (0th derivative)
    
    # Extract pressure first because the velocities will be transformed later
    y_derivatives[:,:,0,3] = state[:,:,3]   # 0th derivative of pressure
    y_derivatives[:,:,1,3] = dy_state[:,:,3]
    y_derivatives[:,:,2,3] = dy2_state[:,:,3] # We never need pressure, but keep it for completion
    
    # The actual velocities, u,v,w, are defined as (1-y^2)* corresponding entries. 
    # The derivatives will have to be correspondingly modified
    yRow = y.reshape((1,1,1,N))
    yQuadRow =(1.-y**2).reshape((1,1,1,N)) 
    
    y_derivatives[:,:,0,:3] =  yQuadRow * state[:,:,:3]           # 0th derivative of velocities 
    y_derivatives[:,:,1,:3] = -2.*yRow *state[:,:,:3] + yQuadRow * dy_state[:,:,:3]  # First derivative
    y_derivatives[:,:,2,:3] = -2.*state[:,:,:3] - 4.*yRow*dy_state[:,:,:3] + yQuadRow * dy2_state[:,:,:3] #Second
    
    #====================================================
    # x-derivatives
    x_derivatives = np.zeros((kxArr.size, kzArr.size, 3, 4, N),dtype=np.complex) # Same as y_derivatives
    
    x_derivatives[:,:,0] = y_derivatives[:,:,0]  # zeroth derivative
    
    # First derivative: i*kx* field
    x_derivatives[:,:,1] = 1.j* kxArr.reshape((kxArr.size, 1,1,1)) * x_derivatives[:,:,0]
    # Second derivative: - kx^2 * field
    x_derivatives[:,:,2] = -1.* (kxArr**2).reshape((kxArr.size, 1,1,1)) * x_derivatives[:,:,0]
    
    #====================================================
    # z-derivatives
    z_derivatives = np.zeros((kxArr.size, kzArr.size, 3, 4, N),dtype=np.complex) # Same as y_derivatives
    
    z_derivatives[:,:,0] = y_derivatives[:,:,0]  # zeroth derivative
    
    # First derivative: i*kz* field
    z_derivatives[:,:,1] = 1.j* kzArr.reshape((1, kzArr.size,1,1)) * z_derivatives[:,:,0]
    # Second derivative: - kx^2 * field
    z_derivatives[:,:,2] = -1.* (kzArr**2).reshape((1, kzArr.size, 1,1)) * z_derivatives[:,:,0]
    
    if wavy:
        eps = flowDict['eps']; beta = flowDict['beta']
        field_y = np.copy(y_derivatives[:,:,1])
        field_y[0,0,0] += flowDict['Uy'] # Add U_y when calculating $z$-derivatives
        dzAdd = np.zeros(field_y.shape, dtype=field_y.dtype)
        dzAdd[:,1:] = field_y[:,:-1]
        dzAdd[:,:-1] -= field_y[:,1:]

        dzAdd = -1.j* eps * beta * dzAdd 
        
        dz2 = np.copy(z_derivatives[:,:,2])
        tempField1 = z_derivatives[:,:,1] @ D1.T
        tempField2 = field_y 
        
        sumTemp = -2.j*eps*beta*tempField1 + eps*beta*beta*tempField2
        dz2[:,1:] += sumTemp[:,:-1] 
        sumTemp = 2.j*eps*beta*tempField1 + eps*beta*beta*tempField2
        dz2[:,:-1] += sumTemp[:,1:]
       
        # Need U_yy. Get that first
        if np.allclose(flowDict['U'], 1.-y**2): Uyy = -2.*np.ones(y.size)
        elif np.allclose(flowDict['U'], -2.*y): Uyy = np.zeros(y.size)
        else : 
            print("Something's wrong with U in flowDict, using 1-y^2")
            Uyy = -2.*np.ones(y.size)
        field_yy = np.copy(y_derivatives[:,:,2])
        field_yy[0,0,0] += Uyy

        tempField = -(eps**2)*(beta**2)*field_yy
        dz2[:,2:] += tempField[:,:-2]
        dz2[:,:-2] += tempField[:,2:]
        dz2 += -2.*tempField

        z_derivatives[:,:,1] += dzAdd 
        z_derivatives[:,:,2] =  dz2
        
        
    
    return x_derivatives, y_derivatives, z_derivatives


