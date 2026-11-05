"""Standard convex L1 linear trend filtering, for an isolated B1 pilot.

Native meter-bin means only: H=I. No sub-bin latent trajectory, offset fitted
from this event, clipping, truth, template, or fallback is used. This module
reproduces a mature objective; it is not a new general estimator.

P(x) = .5 (x-y)' Sigma^-1 (x-y) + penalty ||D2 x||_1
dual(u) = u'D2 y - .5 u'D2 Sigma D2'u, |u| <= penalty
x = y - Sigma D2'u.

covariance is a full symmetric positive-definite matrix or a positive scalar
variance (not standard deviation). Complete non-event forecast residuals
already include meter noise; callers must not add that noise a second time.
The study uses n=60, while n>=3 is allowed for independent small controls.
"""
from numbers import Real
import numpy as np
from scipy.linalg import solve_triangular
from scipy.optimize import lsq_linear

VERSION = 'native-bin-convex-l1tf-pilot-v1'
GAP_ABSOLUTE_TOL = 1e-8
GAP_RELATIVE_TOL = 1e-8
KKT_RELATIVE_TOL = 1e-7


def second_difference(n):
    """Second differences on equally spaced native bins, no resampling."""
    if isinstance(n, bool) or not isinstance(n, (int, np.integer)) or n < 3:
        raise ValueError('n_must_be_integer_at_least_three')
    out = np.zeros((n-2, n))
    idx = np.arange(n-2)
    out[idx, idx] = 1.
    out[idx, idx+1] = -2.
    out[idx, idx+2] = 1.
    return out


def _numeric_array(value):
    obj = np.asarray(value, dtype=object)
    if any(isinstance(v, (bool, np.bool_)) or not isinstance(v, Real) for v in obj.flat):
        raise ValueError('numeric_values_required_without_bool')
    result = np.asarray(value, dtype=float)
    if not np.isfinite(result).all():
        raise ValueError('finite_input_required')
    return result


def fit_curve(y, covariance, penalty):
    """Return checked standard trend filtering; unavailable => prediction=None.

    A bounded dual least-squares problem is solved by SciPy BVLS. Both the
    optimizer termination and an independently calculated primal-dual gap are
    checked. All diagnostics are JSON-native; failures never return raw y as
    a substitute curve. Lambda=0 is the exact unpenalized solution.
    """
    answer = dict(status='unavailable', prediction=None, version=VERSION,
        observation_operator='identity_on_native_interval_means',
        original_estimator=False, raw_fallback=False, success=False,
        primal=None, objective=None, dual=None, gap=None, raw_gap=None,
        gap_tolerance=None, gap_pass=False, optimality=None, kkt_residual=None,
        iterations=None, finite=False, reason=None)
    try:
        y = _numeric_array(y)
        if y.ndim != 1 or len(y) < 3:
            raise ValueError('finite_one_dimensional_y_length_at_least_three_required')
        if isinstance(penalty, (bool, np.bool_)) or not isinstance(penalty, Real):
            raise ValueError('finite_nonnegative_penalty_required')
        penalty = float(penalty)
        if not np.isfinite(penalty) or penalty < 0:
            raise ValueError('finite_nonnegative_penalty_required')
        n = len(y)
        if isinstance(covariance, Real) and not isinstance(covariance, (bool, np.bool_)):
            variance = float(covariance)
            if not np.isfinite(variance) or variance <= 0:
                raise ValueError('positive_finite_covariance_variance_required')
            sigma = variance*np.eye(n)
            kind = 'isotropic_variance'
        else:
            sigma = _numeric_array(covariance)
            if sigma.shape != (n, n):
                raise ValueError('matching_square_covariance_required')
            scale = max(float(np.max(np.abs(sigma))), np.finfo(float).tiny)
            if not np.allclose(sigma, sigma.T, rtol=1e-11, atol=1e-12*scale):
                raise ValueError('symmetric_covariance_required')
            sigma = (sigma+sigma.T)/2.
            kind = 'full_covariance'
        chol = np.linalg.cholesky(sigma)
        D = second_difference(n)
        answer.update(n=n, penalty=penalty, covariance_kind=kind,
            solver='scipy_lsq_linear_bvls_dual',
            covariance_condition_number=float(np.linalg.cond(sigma)))
        if penalty == 0:
            prediction = y.copy()
            u = np.zeros(n-2)
            solver_success = True
            iterations = 0
            optimality = 0.
            solver_status = 0
            solver_message = 'exact_lambda_zero_solution'
        else:
            A = chol.T @ D.T
            b = solve_triangular(chol, y, lower=True, check_finite=False)
            solved = lsq_linear(A, b, bounds=(-penalty, penalty),
                method='bvls', tol=1e-12, max_iter=max(500, 10*n))
            u = solved.x
            prediction = y-sigma @ D.T @ u
            solver_success = bool(solved.success)
            iterations = int(solved.nit)
            optimality = float(solved.optimality)
            solver_status = int(solved.status)
            solver_message = str(solved.message)
        correction = prediction-y
        whitened = solve_triangular(chol, correction, lower=True, check_finite=False)
        Dx = D @ prediction
        primal = float(.5*(whitened @ whitened)+penalty*np.sum(np.abs(Dx)))
        dual = float(u @ (D@y)-.5*u @ (D@sigma@D.T@u))
        raw_gap = primal-dual
        tolerance = GAP_ABSOLUTE_TOL+GAP_RELATIVE_TOL*max(1., abs(primal), abs(dual))
        bound_violation = max(0., float(np.max(np.abs(u)))-penalty)
        if penalty == 0:
            kkt = 0.
        else:
            gradient = D@sigma@D.T@u-D@y
            boundary_tol = min(.25*penalty, 1e-9*max(1., penalty))
            upper = u >= penalty-boundary_tol
            lower = u <= -penalty+boundary_tol
            residual = gradient.copy()
            residual[upper] = np.maximum(gradient[upper], 0.)
            residual[lower] = np.minimum(gradient[lower], 0.)
            kkt = max(float(np.max(np.abs(residual))), bound_violation)
        finite = bool(np.isfinite(prediction).all() and np.isfinite(u).all() and
            np.isfinite([primal, dual, raw_gap, optimality, kkt, tolerance]).all())
        gap_pass = finite and -tolerance <= raw_gap <= tolerance
        kkt_tolerance = KKT_RELATIVE_TOL*max(1., float(np.max(np.abs(D@y))))
        kkt_pass = finite and kkt <= kkt_tolerance
        accepted = bool(solver_success and finite and gap_pass and kkt_pass and
            bound_violation <= 1e-10*max(1., penalty))
        answer.update(success=bool(solver_success), primal=primal,
            objective=primal, dual=dual, raw_gap=raw_gap, gap=max(0., raw_gap),
            gap_tolerance=tolerance, gap_pass=bool(gap_pass),
            optimality=optimality, kkt_residual=kkt, kkt_tolerance=kkt_tolerance,
            kkt_pass=bool(kkt_pass), bound_violation=bound_violation,
            iterations=iterations, finite=finite, solver_status=solver_status,
            solver_message=solver_message,
            dual_solution=[float(v) for v in u])
        if accepted:
            answer.update(status='ok', prediction=[float(v) for v in prediction], reason='checked_convex_dual_solution')
        else:
            answer['reason'] = ('solver_termination_failed' if not solver_success else
                'nonfinite_solution' if not finite else
                'primal_dual_gap_failed' if not gap_pass else 'dual_kkt_or_bound_failed')
    except (ValueError, TypeError, OverflowError, np.linalg.LinAlgError, FloatingPointError) as exc:
        answer['reason'] = type(exc).__name__+': '+str(exc)
    # Diagnostics must remain serializable even if an attempted solve overflowed.
    def finite_json(value):
        if isinstance(value, dict):
            return {k:finite_json(v) for k,v in value.items()}
        if isinstance(value, list):
            return [finite_json(v) for v in value]
        if isinstance(value, float) and not np.isfinite(value):
            return None
        return value
    return finite_json(answer)
