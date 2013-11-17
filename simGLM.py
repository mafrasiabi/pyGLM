import numpy as np
from scipy.stats import poisson

"""
simulates a coupled GLM model
author: Niru Maheswaranathan
4:31 PM Nov 13, 2013
"""

def f_df(theta, data, params):
    """
    log-likelihood objective and gradient, assuming Poisson noise

    function [fval grad] = f_df(theta, data, params)
    % Computes the Poisson log-likelihood objective and gradient
    % for the generalized linear model (GLM)
    """

    # offset for numerical stability
    epsilon = 1e-20

    # number of data samples in this batch
    m = data['x'].shape[0]

    ## simulate the model at theta
    rhat = simulate(theta, params, data)
    rdt  = rhat*params['dt']                        # rdt is: m by 1

    ## compute objective value (negative log-likelihood)
    fval = sum(rdt - data['n']*np.log(rdt + epsilon)) / m

    ## compute gradient
    grad = dict()

    # temporarily store different in rate vs. observed spike count (used for gradient computations)
    rateDiff = (rdt - data['n']).T                  # rateDiff is: 1 by m

    # gradient for stimulus parameters
    grad['w'] = rateDiff.dot(data['x']).T / m       # grad['w'] is: ds by 1

    # gradient for the offset term
    grad['b'] = sum(np.squeeze(rateDiff)) / m       # grad['b'] is a scalar

    # gradient for history terms
    grad['h'] = np.zeros((params['dh'],1))          # grad['h'] is: dh by 1

    # cross-correlate rate vector
    spkCountArray = np.squeeze(data['n'])
    rateDiffArray = np.squeeze(rateDiff)

    #grad['h'] = np.zeros( (m,1) )
    dh = params['dh']
    for delta in np.arange(1,dh+1):
        grad['h'][dh-delta] = sum( spkCountArray[:-delta] * rateDiffArray[delta:] ) / m
        #grad['h'][dh-delta] = np.mean( spkCountArray[:-delta] * rateDiffArray[delta:] )

    return fval, grad

def setParameters(n = 10, ds = 500, dh = 10, m = 1000, dt = 0.1):

    """
    Parameters
    ----------
    n : number of neurons
    ds: dimension of the stimulus
    dh: dimension of the coupling filters
    m : minibatch size (number of training examples)

    """

    # define the parameters dictionary
    params = {'numNeurons': n, 'stim_dim': ds, 'hist_dim': dh, 'numSamples': m, 'dt': dt}
    return params

def generateModel(params, filterType='sinusoid'):

    """

    Generates model parameters
    --------------------------

    Returns a theta dictionary:
    theta['w']:    stimulus filters for the n neurons, (ds x n) matrix
    theta['b']:    stimulus offset  for the n neurons, (ds x n) matrix
    theta['h']:    history  filters for the n neurons, (dh x n) matrix

    """

    ## get out parameters
    ds = params['stim_dim']
    dh = params['hist_dim']
    N  = params['numNeurons']
    M  = params['numSamples']

    ## store model as dictionary
    theta = {}

    ## build the filters:

    # stimulus filters for each of n neurons
    if filterType is 'random':
        theta['w'] = np.random.randn(ds, N)
    elif filterType is 'sinusoid':
        theta['w'] = np.zeros((ds, N))
        for neuronIndex in range(N):
            theta['w'][:,neuronIndex] = np.sin( np.linspace(0,2*np.pi,ds) + 2*np.pi*np.random.rand() )
    else:
        print('WARNING: unrecognized filter type. Using random values instead.')
        theta['w'] = 0.2*np.random.randn(ds, N)

    # normalize filters
    #theta['w'] = theta['w'] / np.linalg.norm( theta['w'], axis=0 )
    theta['w'] = theta['w'] / np.sqrt(np.sum(theta['w']**2, axis=0))

    # offset (scalar)
    theta['b'] = -1*np.ones((1,N))

    # history (self-coupling) filters for each of n neurons
    theta['h'] = -0.1*np.ones((dh, N))

    # coupling filters - stored as a big n by (n x dh) matrix
    #theta['h'] = np.zeros((params['dh']*params['n'], params['n']))

    #for idx in range(0,params['n']):

        ## generate coupling terms with other neurons
        #theta['h'][:,idx] = np.random.randn(params['dh']*params['n'])

        ## zero out self-coupling
        #theta['h'][np.arange(idx*params['dh'],(idx+1)*params['dh']),idx] = 0

    return theta

def generateData(theta, params):

    """
    Generates stimuli and draws spike counts from the model
    -------------------------------------------------------
    """

    ## get out parameters
    ds = params['stim_dim']
    dh = params['hist_dim']
    N  = params['numNeurons']
    M  = params['numSamples']

    # offset for numerical stability
    epsilon = 1e-20

    ## store output in a dictionary
    data = {}

    # input / output
    data['x'] = 0.2*np.random.randn(M, ds) # stimulus
    data['n'] = np.zeros( (M, N) )                   # spike history

    # compute stimulus projection
    u = theta['w'].T.dot(data['x'].T).T            # (u is: M by 1)

    # the initial rate (no history)
    data['n'][0] = poisson.rvs( np.exp( u[0] + theta['b'] ) )

    # the next rate (one history point)
    data['n'][1] = poisson.rvs( np.exp( u[1] + data['n'][0]*theta['h'][-1] + theta['b'] ) )

    # simulate the model (in time)
    for j in np.arange(2,M):

        # compute history weights
        if j < dh+1:
            n1 = np.squeeze(data['n'][0:j])
            n2 = np.squeeze(theta['h'])
            v = np.correlate( n1 , n2 , 'valid' )[0]
        else:
            v = data['n'][j-dh:j].T.dot(theta['h'])

        # compute model firing rate
        r = np.exp( u[j] + v + theta['b'] ) + epsilon

        # draw spikes
        data['n'][j] = poisson.rvs(r)

    return data


def simulate(theta, params, data):

    """
    Simulates the output of the GLM given true stimulus/response
    ------------------------------------------------------------
    """

    # get stimuli, offset, and spike counts
    x = data['x']           # (x is: m by ds)
    n = data['n']           # spike counts

    # number of samples
    m = data['x'].shape[0]

    # make sure we have a reasonable number of samples
    if m < params['dh']:
        print('error: minibatch size is too small (smaller than history term)')

    # compute stimulus projection for the n neurons     # (u is: m by 1)
    u = theta['w'].T.dot(data['x'].T).T

    # compute history terms                             # (uh is: m by 1)
    v = np.reshape( np.correlate(np.squeeze(n), np.squeeze(theta['h']), 'full')[0:n.size-1], (m-1,1) )
    v = np.vstack(( np.zeros((1,1)) , v ))

    # response of the n neurons (stored as an n by m matrix)
    return np.exp( u + v + theta['b'] )

if __name__=="__main__":

    print('Initializing parameters...')
    p = setParameters(m = 1e4)

    print('Generating model...')
    theta = generateModel(p)

    print('Simulating model...')
    data = generateData(theta, p)

    print('Evaluating objective...')
    fval, grad = f_df(theta, data, p)
