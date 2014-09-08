from nose.tools import assert_equal, assert_true
import numpy as np
from ..fista import mfista
from ..operators import prox_l1
from ..objective_functions import (squared_loss, logistic,
                                   squared_loss_grad,
                                   logistic_loss_lipschitz_constant,
                                   squared_loss_lipschitz_constant)
from ..fista import check_lipschitz_continuous


def test_logistic_lipschitz(n_samples=4, n_features=2, random_state=42):
    rng = np.random.RandomState(random_state)

    for scaling in np.logspace(-3, 3, num=7):
        X = rng.randn(n_samples, n_features) * scaling
        y = rng.randn(n_samples)
        n_features = X.shape[1]

        L = logistic_loss_lipschitz_constant(X)
        check_lipschitz_continuous(lambda w: logistic(
            X, y, w), n_features + 1, L)


def test_squared_loss_lipschitz(n_samples=4, n_features=2, random_state=42):
    rng = np.random.RandomState(random_state)

    for scaling in np.logspace(-3, 3, num=7):
        X = rng.randn(n_samples, n_features) * scaling
        y = rng.randn(n_samples)
        n_features = X.shape[1]

        L = squared_loss_lipschitz_constant(X)
        check_lipschitz_continuous(lambda w: squared_loss_grad(
            X, y, w), n_features, L)


def test_input_args_and_kwargs():
    p = 125
    noise_std = 1e-1
    sig = np.zeros(p)
    sig[[0, 2, 13, 4, 25, 32, 80, 89, 91, 93, -1]] = 1
    sig[:6] = 2
    sig[-7:] = 2
    sig[60:75] = 1
    y = sig + noise_std * np.random.randn(*sig.shape)
    X = np.eye(p)
    mask = np.ones((p,)).astype(np.bool)
    alpha = .01
    alpha_ = alpha * X.shape[0]
    l1_ratio = .2
    l1_weight = alpha_ * l1_ratio
    f1 = lambda w: squared_loss(X, y, w, mask, compute_grad=False)
    f1_grad = lambda w: squared_loss(X, y, w, mask, compute_grad=True,
                               compute_energy=False)
    f2_prox = lambda w, l, *args, **kwargs: (prox_l1(w, l * l1_weight),
                                             dict(converged=True))
    total_energy = lambda w: f1(w) + l1_weight * np.sum(np.abs(w))
    for pure_ista in [True, False]:
        for cb_retval in [0, 1]:
            for verbose in [0, 1]:
                for bt in [0, 1]:
                    for cm in [True, False]:
                        for dgap_factor in [1., None]:
                            best_w, objective, init = mfista(
                                f1, f1_grad, f2_prox, total_energy, 1., p,
                                dgap_factor=dgap_factor, pure_ista=pure_ista,
                                callback=lambda _: cb_retval, verbose=verbose,
                                backtracking=bt, max_iter=100,
                                check_monotonous=cm
                                )
                            assert_equal(best_w.shape, mask.shape)
                            assert_true(isinstance(objective, list))
                            assert_true(isinstance(init, dict))
                            for key in ["w", "t", "dgap_tol", "stepsize"]:
                                assert_true(key in init)
