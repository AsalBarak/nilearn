"""
Common functions and base classes. Used by more specialized modules like
tv.py, smooth_lasso.py, etc.

"""
# Author: DOHMATOB Elvis Dopgima,
#         Gaspar Pizarro,
#         Fabian Pedragosa,
#         Gael Varoquaux,
#         Alexandre Gramfort,
#         Bertrand Thirion,
#         and others.
# License: simplified BSD

from functools import partial
import numpy as np
from scipy import linalg


def spectral_norm_squared(X):
    """Computes square of the operator 2-norm (spectral norm) of X

    This corresponds to the lipschitz constant of the gradient of the
    squared-loss function:

        w -> .5 * ||y - Xw||^2

    Parameters
    ----------
    X : np.ndarray,
      Input map.

    Returns
    -------
    lipschitz_constant : float,
      The square of the spectral norm of X.

    """
    # On big matrices like those that we have in neuroimaging, svdvals
    # is faster than a power iteration (even when using arpack's)
    return linalg.svdvals(X)[0] ** 2


def logistic_loss_lipschitz_constant(X):
    """Compute the Lipschitz constant (upper bound) for the gradient of the
    logistic sum:

         w -> \sum_i log(1+exp(-y_i*(x_i*w + v)))

    """
    # N.B: we handle intercept!
    X = np.hstack((X, np.ones(X.shape[0])[:, np.newaxis]))
    return spectral_norm_squared(X)


def squared_loss(X, y, w, compute_energy=True, compute_grad=False):
    """Compute the MSE error, and optionally, its gradient too.

    The energy is

        MSE = .5 * ||y - Xw||^2

    A (1 / n_samples) factor is applied to the MSE.

    Parameters
    ----------
    X : 2D array of shape (n_samples, n_features)
        Design matrix.

    y : 1D array of length n_samples
        Target / response vector.

    w : 1D array of length n_features
        Unmasked, ravelized weights map.

    compute_energy : bool, optional (default True)
        If set then energy is computed, otherwise only gradient is computed.

    compute_grad : bool, optional (default True)
        If set then gradient is computed, otherwise only energy is computed.

    Returns
    -------
    energy : float
        Energy (returned if `compute_energy` is set).

    gradient : 1D array
        Gradient of energy (returned if `compute_grad` is set).

    """
    assert compute_energy or compute_grad

    residual = np.dot(X, w) - y

    # compute energy
    if compute_energy:
        energy = .5 * np.dot(residual, residual)
        if not compute_grad:
            return energy

    grad = np.dot(X.T, residual)

    if not compute_energy:
        return grad

    return energy, grad


def tv_l1_from_gradient(spatial_grad):
    """Energy contribution due to penalized gradient, in TV-l1 model.

    Parameters
    ----------
    spatial_grad : array
       precomputed "gradient + id" array

    Returns
    -------
    out : float
        Energy contribution due to penalized gradient.
    """

    tv_term = np.sum(np.sqrt(np.sum(spatial_grad[:-1] * spatial_grad[:-1],
                                    axis=0)))
    l1_term = np.abs(spatial_grad[-1]).sum()
    return l1_term + tv_term


def div_id(grad, l1_ratio=.5):
    """Compute divergence + id of image gradient + id

    Parameters
    ----------
    grad : ndarray of shape (n_axes + 1, *img_shape).
        where `img_shape` is the shape of the brain bounding box, and
        n_axes = len(img_shape).

    l1_ratio : float, optional (default .5)
        Relative weight of l1; float between 0 and 1 inclusive.
        TV+L1 penalty will be (alpha not shown here):
        (1 - l1_ratio) * ||w||_TV + l1_ratio * ||w||_1

    Returns
    -------
    res : ndarray of shape grad.shape[1:]
        The computed divergence + id operator.

    """

    assert 0. <= l1_ratio <= 1., (
        "l1_ratio must be in the interval [0, 1]; got %s" % l1_ratio)

    res = np.zeros(grad.shape[1:])

    # the divergence part
    for d in range((grad.shape[0] - 1)):
        this_grad = np.rollaxis(grad[d], d)
        this_res = np.rollaxis(res, d)
        this_res[:-1] += this_grad[:-1]
        this_res[1:-1] -= this_grad[:-2]
        if len(this_grad) > 1:
            this_res[-1] -= this_grad[-2]

    res *= (1. - l1_ratio)

    # the identity part
    res -= l1_ratio * grad[-1]

    return res


def gradient_id(img, l1_ratio=.5):
    """Compute gradient + id of an image

    Parameters
    ----------
    img : ndarray
        N-dimensional image

    l1_ratio : float, optional (default .5)
        relative weight of l1; float between 0 and 1 inclusive.
        TV+L1 penalty will be (alpha not shown here):

        (1 - l1_ratio) * ||w||_TV + l1_ratio * ||w||_1

    Returns
    -------
    gradient : ndarray of shape (img.ndim, *img.shape).
        Spatial gradient of the image: the i-th component along the first
        axis is the gradient along the i-th axis of the original
        array img.

    """

    assert 0. <= l1_ratio <= 1., (
        "l1_ratio must be in the interval [0, 1]; got %s" % l1_ratio)

    shape = [img.ndim + 1] + list(img.shape)
    gradient = np.zeros(shape, dtype=np.float)  # xxx: img.dtype?

    # the gradient part: 'Clever' code to have a view of the gradient
    # with dimension i stop at -1
    slice_all = [0, slice(None, -1)]
    for d in range(img.ndim):
        gradient[slice_all] = np.diff(img, axis=d)
        slice_all[0] = d + 1
        slice_all.insert(1, slice(None))

    gradient[:-1] *= (1. - l1_ratio)

    # the identity part
    gradient[-1] = l1_ratio * img

    return gradient


def _unmask(w, mask):
    """Unmask an image into whole brain, with off-mask voxels set to 0.

    Parameters
    ----------
    w : 1d array,
      The image to be unmasked.

    mask : np.ndarray or None,
      The mask used in the unmasking operation.

    Returns
    -------
    out : ndarry of same shape as `mask`.
        The unmasked version of `w`
    """

    out = np.zeros(mask.shape, dtype=w.dtype)
    out[mask] = np.ravel(w)

    return out


def _sigmoid(t, copy=True):
    """Helper function: return 1. / (1 + np.exp(-t))"""
    if copy:
        t = np.copy(t)
    t *= -1.
    t = np.exp(t, t)
    t += 1.
    t = np.reciprocal(t, t)
    return t


def logistic(X, y, w):
    """Compute the logistic function of the data: sum(sigmoid(yXw))

    Parameters
    ----------
    X : 2D array of shape (n_samples, n_features)
        Design matrix.

    y : 1D array of length n_samples
        Target / response vector.

    w : array_like, shape (n_voxels,)
        Unmasked, ravelized input map.

    Returns
    -------
    energy : float
        Energy contribution due to logistic data-fit term.
    """

    z = np.dot(X, w[:-1]) + w[-1]
    yz = y * z
    idx = yz > 0
    out = np.empty_like(yz)
    out[idx] = np.log1p(np.exp(-yz[idx]))
    out[~idx] = -yz[~idx] + np.log1p(np.exp(yz[~idx]))
    out = out.sum()
    return out


def logistic_loss_grad(X, y, w):
    """Computes the derivative of logistic"""
    z = np.dot(X, w[:-1]) + w[-1]
    yz = y * z
    z = _sigmoid(yz, copy=False)
    z0 = (z - 1.) * y
    grad = np.empty(w.shape)
    grad[:-1] = np.dot(X.T, z0)
    grad[-1] = np.sum(z0)
    return grad

# Wrappers.
# XXX div (see below) could be computed more efficienty!
gradient = lambda w: gradient_id(w, l1_ratio=0.)[:-1]  # pure nabla
div = lambda v: div_id(np.vstack((v, [np.zeros_like(v[0])])), l1_ratio=0.)
squared_loss_grad = partial(squared_loss, compute_energy=False,
                            compute_grad=True)
