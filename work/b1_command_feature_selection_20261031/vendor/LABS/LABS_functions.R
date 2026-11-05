################################################################################
# LABS_functions.R
#
# Look-Ahead Binary Segmentation (LABS) for piecewise-linear trend change-point
# detection.
#
# Algorithm overview:
#   1. Prefix sums PY, PY1, and PAD2 are precomputed once from the normalised
#      input.
#   2. max_kink_contrast computes the linear-trend contrast at every interior
#      point of a sub-interval via prefix-sum lookups (no vector copying) and
#      returns the position and value of the maximum.
#   3. max_kink_contrast_grid locates the position and value of the maximum
#      absolute contrast across a grid of sub-intervals (no thresholding).
#   4. labs_recursion implements the LABS recursion: after proposing a change-
#      point it recurses into the two sub-intervals (scrutiny step) and then
#      re-tests the candidate over a possibly narrowed interval to correct the
#      bias inherent in standard binary segmentation.  The proposal-stage grid
#      size and the retest-stage grid size can be chosen separately.
#   5. labs is the user-facing wrapper that normalises the input, precomputes
#      prefix sums, applies the recursion, and returns detected change-points
#      together with a piecewise-linear fit.
#
# The standalone function kink_contrast is retained at the top for external
# use and testing; the internal recursion uses prefix sums exclusively.
################################################################################


# ------------------------------------------------------------------------------
# default_initial_false_multiplier
#
# Return the default threshold multiplier used when labs() is called with
# initial_test = FALSE and thresh = NULL.
#
# The ordinary universal threshold uses sqrt(2 log n), appropriate for roughly
# n candidate locations.  Without the initial test, recursion can generate up to
# n - 2 retest gates, so we use a Bonferroni-style effective count n * (n - 2)
# and multiply the ordinary threshold by
#   sqrt(log(n * (n - 2)) / log(n)).
# ------------------------------------------------------------------------------
default_initial_false_multiplier <- function(n) {
  n_eff <- n * max(n - 2L, 1L)
  max(1, sqrt(log(n_eff) / log(n)))
}


# ------------------------------------------------------------------------------
# kink_contrast
#
# Compute the linear-trend (kink) contrast statistic for every interior
# location of a numeric vector x.  Standalone version (no prefix sums needed).
#
# The contrast at position b (2 <= b <= n-1) compares the left-side and
# right-side weighted-least-squares linear fits and returns a signed measure of
# the kink magnitude.  Positions 1 and n always receive contrast value 0.
#
# Arguments:
#   x        Numeric vector of observations (length >= 1).
#   num_zero Threshold below which second differences are treated as exactly
#            zero, in which case all contrasts are set to 0.  Defaults to 1e-15.
#
# Returns:
#   Numeric vector of length n containing the contrast values.
# ------------------------------------------------------------------------------
kink_contrast <- function(x, num_zero = 1e-15) {
  
  if (!is.numeric(x))     stop("The input in `x' should be a numeric vector.")
  if (anyNA(x))           stop("`x' must not contain NA values.")
  if (any(!is.finite(x))) stop("`x' must not contain Inf or NaN values.")
  
  n <- length(x)
  
  if (n <= 2) return(rep(0, n))
  
  # Short-circuit for signals that are already (numerically) piecewise-linear.
  if (max(abs(diff(x, differences = 2))) < num_zero) return(rep(0, n))
  
  b  <- 2:(n - 1)
  y1 <- cumsum(x * seq_len(n))   # cumulative sum of t * x_t
  y  <- cumsum(x)                # cumulative sum of x_t
  
  a  <- sqrt(6 / ((n - 1) * n * (n + 1) * (2 - 2*b^2 + 2*b*n - 1 + 2*b - n)))
  be <- sqrt(((n - b + 1) * (n - b)) / ((b - 1) * b))
  
  res    <- numeric(n)
  res[b] <- (a * be  * ((2*b + n - 1) * y1[b] - (n + 1) * b  * y[b])) -
    (a / be  * ((3*n - 2*b + 1) * (y1[n] - y1[b]) -
                  (n + 1) * (2*n - b) * (y[n] - y[b])))
  res
}


# ------------------------------------------------------------------------------
# max_kink_contrast
#
# Compute the linear-trend (kink) contrast at every interior point of a
# sub-interval [si, ei] using precomputed prefix sums, and return the position
# and value of the maximum absolute contrast.
#
# This is the prefix-sum equivalent of
#   abs(kink_contrast(x[si:ei]))
# but avoids vector subsetting, copying, and redundant cumulative-sum
# computation.
#
# Arguments:
#   PY, PY1  Prefix-sum vectors of length n+1 with a leading zero:
#              PY[k+1]  = sum(y[1:k]),   PY[1]  = 0
#              PY1[k+1] = sum(y[1:k] * (1:k)), PY1[1] = 0
#   PAD2     Prefix-sum vector of length n-1 with a leading zero:
#              PAD2[k+1] = sum(ad2[1:k]), PAD2[1] = 0
#            where ad2[t] = |y[t+2] - 2*y[t+1] + y[t]| for t = 1, ..., n-2.
#   si, ei   Integer start and end indices (1-based) of the sub-interval.
#   num_zero Threshold below which absolute second differences are treated as
#            zero.  The sub-interval is deemed numerically linear when the
#            average absolute second difference is below num_zero (checked in
#            O(1) via the prefix sum PAD2).  Defaults to 1e-15.
#
# Returns:
#   A list with components:
#     pos  Integer giving the best change-point location (global index),
#          or integer(0) if no valid contrast exists.
#     val  The corresponding absolute contrast value (-Inf if none).
# ------------------------------------------------------------------------------
max_kink_contrast <- function(PY, PY1, PAD2, si, ei, num_zero = 1e-15) {
  
  m <- ei - si + 1L
  if (m <= 2L) return(list(pos = integer(0), val = -Inf))
  
  # Short-circuit for sub-intervals that are already (numerically) linear.
  # Second differences of y within [si, ei] exist at y-indices si+1, ..., ei-1,
  # corresponding to ad2 indices si, ..., ei-2 (a total of ei-si-1 terms).
  # Using the prefix sum PAD2 we check whether the average absolute second
  # difference is below num_zero — an O(1) test.
  # sum(ad2[a:b]) = PAD2[b+1] - PAD2[a], so sum(ad2[si:(ei-2)]) is:
  n_d2    <- ei - si - 1L            # number of second-difference terms
  sum_d2  <- PAD2[ei - 1L] - PAD2[si]
  if (sum_d2 < num_zero * n_d2) return(list(pos = integer(0), val = -Inf))
  
  g  <- (si + 1L):(ei - 1L)           # global indices of interior points
  bl <- g - si + 1L                    # local positions 2, ..., m-1
  
  # Prefix-sum lookups (PY/PY1 use 1-based indexing with a leading zero,
  # so PY[k+1] = sum(y[1:k]) and PY[1] = 0).
  py_g   <- PY[g + 1L]                # sum(y[1:g])   for each g
  py1_g  <- PY1[g + 1L]               # sum(y[1:g]*1:g) for each g
  py_si  <- PY[si]                     # sum(y[1:(si-1)])
  py1_si <- PY1[si]
  py_ei  <- PY[ei + 1L]               # sum(y[1:ei])
  py1_ei <- PY1[ei + 1L]
  
  # Local cumulative sums via prefix-sum differences.
  y_bl   <- py_g  - py_si                         # sum(y[si:g])
  y1_bl  <- (py1_g - py1_si) - (si - 1) * y_bl    # sum(y[si:g] * (1:bl))
  yr_bl  <- py_ei  - py_g                          # sum(y[(g+1):ei])
  y1r_bl <- (py1_ei - py1_g) - (si - 1) * yr_bl   # sum(y[(g+1):ei] * ((bl+1):m))
  
  # Normalisation factors (identical to kink_contrast).
  a_coef  <- sqrt(6 / ((m - 1) * m * (m + 1) *
                         (2 - 2*bl^2 + 2*bl*m - 1 + 2*bl - m)))
  be_coef <- sqrt(((m - bl + 1) * (m - bl)) / ((bl - 1) * bl))
  
  # Contrast (vectorised over all interior points).
  res <- abs(
    a_coef * be_coef  * ((2*bl + m - 1) * y1_bl  - (m + 1) * bl       * y_bl) -
      a_coef / be_coef  * ((3*m - 2*bl + 1) * y1r_bl - (m + 1) * (2*m - bl) * yr_bl)
  )
  
  best <- which.max(res)
  
  # Guard against numerically zero contrasts.
  if (res[best] < num_zero) return(list(pos = integer(0), val = -Inf))
  
  list(pos = g[best], val = res[best])
}


# ------------------------------------------------------------------------------
# max_kink_contrast_grid
#
# Find the position and value of the maximum absolute kink contrast across a
# grid of sub-intervals of [s, e].  No thresholding is applied; the caller
# decides whether the contrast is large enough.
#
# A grid of M indices is formed as round(seq(s, e, length.out = M)).  Contrasts
# are computed (via prefix sums) on every pair of grid points.
#
# When M = 2 (the default) the grid contains only the endpoints s and e, so
# only the single interval [s, e] is evaluated.
#
# Arguments:
#   PY, PY1  Prefix-sum vectors (see max_kink_contrast).
#   PAD2     Prefix-sum of absolute second differences (see max_kink_contrast).
#   s, e     Integer start and end indices (1-based) of the search range.
#   M        Number of grid points.  Must be >= 2.  Defaults to 2.
#
# Returns:
#   A list with components:
#     pos  Integer of length 1 giving the best change-point location (global
#          index), or integer(0) if no valid contrast exists.
#     val  The corresponding absolute contrast value (-Inf if none).
# ------------------------------------------------------------------------------
max_kink_contrast_grid <- function(PY, PY1, PAD2, s, e, M = 2L) {
  
  grid <- unique(round(seq(from = s, to = e, length.out = M)))
  ng   <- length(grid)
  
  if (ng < 2L) return(list(pos = integer(0), val = -Inf))
  
  best_val <- -Inf
  best_pos <- integer(0)
  
  for (i in seq_len(ng - 1L)) {
    for (j in seq.int(i + 1L, ng)) {
      si <- grid[i]
      ei <- grid[j]
      if (ei - si < 2L) next       # need >= 3 points for a non-zero contrast
      
      result <- max_kink_contrast(PY, PY1, PAD2, si, ei)
      
      if (result$val > best_val) {
        best_val <- result$val
        best_pos <- result$pos
      }
    }
  }
  
  list(pos = best_pos, val = best_val)
}


# ------------------------------------------------------------------------------
# labs_recursion
#
# Recursive engine of the LABS algorithm.
#
# At each call the function:
#   (a) Proposes a change-point in [s, e].  When initial_test = TRUE the
#       proposal must exceed the threshold; when initial_test = FALSE any
#       positive contrast suffices (thresholding is deferred to the re-test).
#   (b) Recurses into the left and right sub-intervals (scrutiny).
#   (c) Re-tests the candidate over the interval between the outermost
#       neighbours found by scrutiny.  When at least one child found a
#       change-point, the contrast is recomputed on the narrowed interval.
#       When both children are empty and initial_test = FALSE, the
#       already-computed proposal contrast is thresholded directly (avoiding
#       a redundant recomputation).
#
# Arguments:
#   PY, PY1      Prefix-sum vectors (see max_kink_contrast).
#   PAD2         Prefix-sum of absolute second differences (see
#                max_kink_contrast).
#   s, e         Integer start and end indices of the current interval.
#   lambda       Detection threshold (on the normalised scale).
#   initial_test Logical; if FALSE the proposal-phase threshold is bypassed
#                at every level of the recursion, so that the re-test is the
#                sole gatekeeper.  Defaults to TRUE.
#   M            Number of proposal-stage grid points passed to
#                max_kink_contrast_grid. Defaults to 2 (single-interval,
#                original behaviour).
#   retest_M     Number of retest-stage grid points passed to
#                max_kink_contrast_grid. Defaults to M.
#
# Returns:
#   Sorted integer vector of detected change-point locations (may be
#   integer(0)).
# ------------------------------------------------------------------------------
labs_recursion <- function(PY, PY1, PAD2, s, e, lambda,
                           initial_test = TRUE,
                           M            = 2L,
                           retest_M     = M) {
  
  # (a) Proposal.
  proposal <- max_kink_contrast_grid(PY, PY1, PAD2, s, e, M)
  
  # No valid contrast (interval too short or numerically zero).
  if (proposal$val <= 0) return(integer(0))
  
  # When initial_test = TRUE, apply the threshold now.
  if (initial_test && proposal$val <= lambda) return(integer(0))
  
  cur_change <- proposal$pos
  
  # (b) Scrutiny: recurse into sub-intervals, propagating initial_test.
  left    <- labs_recursion(PY, PY1, PAD2, s,              cur_change,  lambda,
                            initial_test, M, retest_M)
  right   <- labs_recursion(PY, PY1, PAD2, cur_change + 1L, e,          lambda,
                            initial_test, M, retest_M)
  left_l  <- length(left)
  right_l <- length(right)
  
  # (c) Re-test.
  if (left_l || right_l) {
    # At least one child found change-points: recompute contrast on the
    # narrowed interval.
    retest_from <- if (left_l)  left[left_l] + 1L else s
    retest_to   <- if (right_l) right[1]           else e
    retest      <- max_kink_contrast_grid(PY, PY1, PAD2, retest_from, retest_to, retest_M)
    cur_change  <- if (retest$val > lambda) retest$pos else integer(0)
  } else if (!initial_test) {
    # Both children empty and no initial thresholding was applied: the re-test
    # interval is [s, e], identical to the proposal interval.  Reuse the
    # proposal only when the retest grid is identical to the proposal grid.
    retest <- if (retest_M == M) {
      proposal
    } else {
      max_kink_contrast_grid(PY, PY1, PAD2, s, e, retest_M)
    }
    cur_change <- if (retest$val > lambda) retest$pos else integer(0)
  }
  
  c(left, cur_change, right)
}


# ------------------------------------------------------------------------------
# labs
#
# Detect piecewise-linear trend change-points with the LABS algorithm.
#
# The signal x is normalised by its maximum absolute value before calling
# labs_recursion so that the contrast values are scale-independent.  Prefix
# sums and absolute second differences are precomputed once from the normalised
# input and reused throughout the recursion, eliminating redundant cumulative-
# sum computation and vector subsetting.  After detection a piecewise-linear
# fit is obtained via a B-spline design matrix with knots at the estimated
# change-points.
#
# Arguments:
#   x            Numeric vector of observations (length >= 3 required for
#                change-point detection; shorter inputs are returned as-is).
#                Must not contain NA, NaN, or Inf values.
#   thresh       Detection threshold on the original scale.  Defaults (NULL) to
#                the scaled median absolute deviation of second differences
#                times sqrt(2 log n), a near-universal threshold for Gaussian
#                noise.  When initial_test = FALSE and thresh = NULL, this is
#                multiplied by initial_false_multiplier.  Must be a single
#                non-negative number if supplied.
#   initial_test Logical; if FALSE the proposal-phase threshold is bypassed
#                at every level of the recursion, so that the re-test is the
#                sole gatekeeper.  Defaults to TRUE.
#   M            Number of proposal-stage grid points passed to
#                max_kink_contrast_grid via labs_recursion.  M = 2 (the
#                default) evaluates only the
#                single interval [s, e] at each recursion step, reproducing
#                the original behaviour.  Larger M adds interior grid points
#                and evaluates all O(M^2) sub-intervals, broadening the
#                contrast search at the cost of extra computation.
#   retest_M     Number of retest-stage grid points passed to
#                max_kink_contrast_grid via labs_recursion. Defaults to M.
#   initial_false_multiplier
#                Threshold multiplier used when initial_test = FALSE and
#                thresh = NULL. Defaults to a Bonferroni-style multiplier based
#                on at most n - 2 retest gates; set to 1 to reproduce the old
#                threshold.
#
# Returns:
#   A list with components:
#     cpts  Integer vector of estimated change-point locations (in 1:n).
#     fit   Numeric vector of length n with the piecewise-linear fitted values.
# ------------------------------------------------------------------------------
labs <- function(x,
                 thresh                   = NULL,
                 initial_test             = TRUE,
                 M                        = 2L,
                 retest_M                 = M,
                 initial_false_multiplier = NULL) {
  
  # --- Input validation -------------------------------------------------------
  if (!is.numeric(x))        stop("`x' must be a numeric vector.")
  if (anyNA(x))              stop("`x' must not contain NA values.")
  if (any(!is.finite(x)))    stop("`x' must not contain Inf or NaN values.")
  
  n <- length(x)
  
  # Trivial cases: no change-point can be detected.
  if (n <= 2) return(list(cpts = integer(0), fit = x))
  
  thresh_defaulted <- is.null(thresh)

  # Default threshold: MAD of rescaled second differences times sqrt(2 log n).
  if (is.null(thresh)) {
    thresh <- stats::mad(diff(x, differences = 2) / sqrt(6)) * sqrt(2 * log(n))
  }
  
  if (!is.numeric(thresh) || length(thresh) != 1L || is.na(thresh) || thresh < 0)
    stop("`thresh' must be a single non-negative number.")
  
  if (!is.logical(initial_test) || length(initial_test) != 1L || is.na(initial_test))
    stop("`initial_test' must be TRUE or FALSE.")
  
  if (!is.numeric(M) || length(M) != 1L || is.na(M) || M < 2L)
    stop("`M' must be an integer >= 2.")

  if (!is.numeric(retest_M) || length(retest_M) != 1L || is.na(retest_M) || retest_M < 2L)
    stop("`retest_M' must be an integer >= 2.")

  if (!is.null(initial_false_multiplier) &&
      (!is.numeric(initial_false_multiplier) ||
       length(initial_false_multiplier) != 1L ||
       is.na(initial_false_multiplier) ||
       initial_false_multiplier < 1)) {
    stop("`initial_false_multiplier' must be NULL or a single number >= 1.")
  }
  
  M <- as.integer(M)
  retest_M <- as.integer(retest_M)

  if (!initial_test && thresh_defaulted) {
    if (is.null(initial_false_multiplier)) {
      initial_false_multiplier <- default_initial_false_multiplier(n)
    }
    thresh <- thresh * initial_false_multiplier
  }
  
  # --- Main algorithm ---------------------------------------------------------
  x_abs_max <- max(abs(x))
  if (x_abs_max == 0) return(list(cpts = integer(0), fit = x))
  
  # Normalise to [-1, 1] for numerical stability.
  y  <- x / x_abs_max
  th <- thresh / x_abs_max
  
  # Precompute prefix sums and absolute second differences once.
  # PY[k+1]   = sum(y[1:k]),            PY[1]   = 0
  # PY1[k+1]  = sum(y[1:k] * (1:k)),   PY1[1]  = 0
  # PAD2[k+1] = sum(ad2[1:k]),          PAD2[1] = 0
  #   where ad2[t] = |y[t+2] - 2*y[t+1] + y[t]| for t = 1, ..., n-2.
  PY   <- c(0, cumsum(y))
  PY1  <- c(0, cumsum(y * seq_len(n)))
  PAD2 <- c(0, cumsum(abs(diff(y, differences = 2))))
  
  cpts <- labs_recursion(PY, PY1, PAD2, 1L, n, th, initial_test, M, retest_M)
  
  # Piecewise-linear fit via B-splines of degree 1.
  X   <- splines::bs(seq_len(n), knots = cpts, degree = 1, intercept = TRUE)
  fit <- stats::lm.fit(X, x)$fitted.values
  
  list(cpts = cpts, fit = fit)
}


# ------------------------------------------------------------------------------
# labs_path
#
# Solution-path version of LABS.  Runs LABS over a geometric grid of thresholds,
# computes an information criterion for each unique model, and returns the
# model minimising the criterion together with the full path.
#
# Arguments:
#   x            Numeric vector of observations (length >= 3 required).
#                Must not contain NA, NaN, or Inf values.
#   initial_test Logical; passed to labs_recursion.  Defaults to TRUE.
#   M            Number of proposal-stage grid points passed to
#                max_kink_contrast_grid. Defaults to 2.
#   retest_M     Number of retest-stage grid points passed to
#                max_kink_contrast_grid. Defaults to M.
#   K            Number of thresholds in the geometric grid.  Defaults to 25.
#   penalty      Penalty type: "sic" for the Schwarz Information Criterion
#                (penalty log n per parameter) or "ssic" for the strengthened
#                SIC (penalty (log n)^2.1 per parameter).  Defaults to "sic".
#
# Returns:
#   A list with components:
#     best    List with components cpts, fit, rss, df, threshold, ic for
#             the model minimising the information criterion.
#     path    Data frame with one row per unique model encountered along the
#             path, containing columns: n_cpts, threshold, rss, df, ic.
#     all     List of all unique models (each a list with cpts, fit, rss, df,
#             threshold, ic).
#     penalty Character string indicating the penalty used.
# ------------------------------------------------------------------------------
labs_path <- function(x,
                      initial_test = TRUE,
                      M            = 2L,
                      retest_M     = M,
                      K            = 25L,
                      penalty      = c("sic", "ssic")) {
  
  # --- Input validation -------------------------------------------------------
  if (!is.numeric(x))        stop("`x' must be a numeric vector.")
  if (anyNA(x))              stop("`x' must not contain NA values.")
  if (any(!is.finite(x)))    stop("`x' must not contain Inf or NaN values.")
  
  n <- length(x)
  if (n <= 2) {
    null_fit  <- x
    null_rss  <- 0
    null_model <- list(cpts = integer(0), fit = null_fit, rss = null_rss,
                       df = 2L, threshold = Inf, ic = n * log(null_rss / n) + 2 * log(n))
    return(list(best = null_model,
                path = data.frame(n_cpts = 0L, threshold = Inf,
                                  rss = null_rss, df = 2L, ic = null_model$ic),
                all = list(null_model), penalty = "sic"))
  }
  
  if (!is.logical(initial_test) || length(initial_test) != 1L || is.na(initial_test))
    stop("`initial_test' must be TRUE or FALSE.")
  if (!is.numeric(M) || length(M) != 1L || is.na(M) || M < 2L)
    stop("`M' must be an integer >= 2.")
  if (!is.numeric(retest_M) || length(retest_M) != 1L || is.na(retest_M) || retest_M < 2L)
    stop("`retest_M' must be an integer >= 2.")
  if (!is.numeric(K) || length(K) != 1L || is.na(K) || K < 2L)
    stop("`K' must be an integer >= 2.")
  
  M <- as.integer(M)
  retest_M <- as.integer(retest_M)
  K <- as.integer(K)
  penalty <- match.arg(penalty)
  
  # --- Precompute -------------------------------------------------------------
  x_abs_max <- max(abs(x))
  if (x_abs_max == 0) {
    null_model <- list(cpts = integer(0), fit = x, rss = 0, df = 2L,
                       threshold = Inf, ic = -Inf)
    return(list(best = null_model,
                path = data.frame(n_cpts = 0L, threshold = Inf,
                                  rss = 0, df = 2L, ic = -Inf),
                all = list(null_model), penalty = penalty))
  }
  
  y  <- x / x_abs_max
  PY   <- c(0, cumsum(y))
  PY1  <- c(0, cumsum(y * seq_len(n)))
  PAD2 <- c(0, cumsum(abs(diff(y, differences = 2))))
  
  # --- Build threshold grid ---------------------------------------------------
  # Upper bound: global maximum contrast (on the normalised scale).
  global     <- max_kink_contrast_grid(PY, PY1, PAD2, 1L, n, M)
  lambda_max <- global$val
  
  # Lower bound: half the universal threshold (on the normalised scale).
  sigma_hat  <- stats::mad(diff(y, differences = 2) / sqrt(6))
  lambda_min <- 0.5 * sigma_hat * sqrt(2 * log(n))
  
  # Ensure lambda_min < lambda_max; if not, use a small fraction of lambda_max.
  if (lambda_min >= lambda_max) lambda_min <- 0.1 * lambda_max
  
  # Geometric grid from lambda_max down to lambda_min.
  grid <- lambda_max * (lambda_min / lambda_max)^(seq.int(0L, K - 1L) / (K - 1L))
  
  # --- Run LABS at each threshold, collect unique models ----------------------
  pen_factor <- if (penalty == "sic") log(n) else log(n)^2.1
  
  # Helper: compute fit and IC for a set of change-points.
  score_model <- function(cpts, threshold) {
    X   <- splines::bs(seq_len(n), knots = cpts, degree = 1, intercept = TRUE)
    fit <- stats::lm.fit(X, x)$fitted.values
    rss <- sum((x - fit)^2)
    df  <- length(cpts) + 2L       # intercept + slope + one per knot
    ic  <- n * log(rss / n) + df * pen_factor
    list(cpts = cpts, fit = fit, rss = rss, df = df,
         threshold = threshold * x_abs_max, ic = ic)
  }
  
  models <- list()
  seen   <- character(0)
  
  # Always include the null model.
  null <- score_model(integer(0), Inf)
  models[[1L]] <- null
  seen <- ""
  
  for (lam in grid) {
    cpts <- labs_recursion(PY, PY1, PAD2, 1L, n, lam, initial_test, M, retest_M)
    key  <- paste(cpts, collapse = ",")
    if (!(key %in% seen)) {
      seen   <- c(seen, key)
      models[[length(models) + 1L]] <- score_model(cpts, lam)
    }
  }
  
  # --- Select best model by IC ------------------------------------------------
  ic_vals <- vapply(models, `[[`, numeric(1), "ic")
  best    <- which.min(ic_vals)
  
  # --- Build summary path -----------------------------------------------------
  path <- data.frame(
    n_cpts    = vapply(models, function(m) length(m$cpts), integer(1)),
    threshold = vapply(models, `[[`, numeric(1), "threshold"),
    rss       = vapply(models, `[[`, numeric(1), "rss"),
    df        = vapply(models, `[[`, numeric(1), "df"),
    ic        = ic_vals
  )
  
  list(best = models[[best]], path = path, all = models, penalty = penalty)
}


# ------------------------------------------------------------------------------
# labs_sic
#
# SIC-backed model selection for LABS over a fixed multiplier grid.  LABS is run
# at thresholds
#   multiplier * mad(diff(x, differences = 2) / sqrt(6)) * sqrt(2 log n),
# and the selected model minimises the same continuous piecewise-linear SIC
# convention used by breakfast::model.ic():
#   n * log(RSS / n) + (2 * number_of_cpts + 3) * log(n)^alpha.
#
# Arguments:
#   x            Numeric vector of observations.
#   initial_test Logical; passed to labs(). Defaults to TRUE.
#   M            Proposal-stage grid size passed to labs().
#   retest_M     Retest-stage grid size passed to labs(). Defaults to M.
#   multipliers  Numeric threshold multipliers. Defaults to 0.50, 0.55, ...,
#                1.50.
#   alpha        SIC exponent. breakfast::model.ic() defaults to 1.01.
#
# Returns:
#   A list with components:
#     cpts        Integer vector selected by SIC.
#     fit         Fitted values for the selected model.
#     threshold   Threshold associated with the selected model.
#     multiplier  Threshold multiplier associated with the selected model.
#     ic          Selected SIC value.
#     path        Data frame of unique candidate models and their SIC values.
# ------------------------------------------------------------------------------
labs_sic <- function(x,
                     initial_test = TRUE,
                     M            = 2L,
                     retest_M     = M,
                     multipliers  = seq(0.50, 1.50, by = 0.05),
                     alpha        = 1.01) {
  
  if (!is.numeric(x))        stop("`x' must be a numeric vector.")
  if (anyNA(x))              stop("`x' must not contain NA values.")
  if (any(!is.finite(x)))    stop("`x' must not contain Inf or NaN values.")
  if (!is.numeric(multipliers) || length(multipliers) == 0L ||
      anyNA(multipliers) || any(multipliers <= 0)) {
    stop("`multipliers' must be a non-empty numeric vector of positive values.")
  }
  if (!is.numeric(alpha) || length(alpha) != 1L || is.na(alpha) || alpha <= 0) {
    stop("`alpha' must be a single positive number.")
  }
  
  n <- length(x)
  if (n <= 2L) {
    return(list(cpts = integer(0), fit = x, threshold = Inf,
                multiplier = NA_real_, ic = -Inf,
                path = data.frame(n_cpts = 0L, threshold = Inf,
                                  multiplier = NA_real_, rss = 0, df = 0L,
                                  ic = -Inf)))
  }
  
  base_threshold <- stats::mad(diff(x, differences = 2) / sqrt(6)) *
    sqrt(2 * log(n))
  penalty_factor <- log(n)^alpha
  
  score_model <- function(cpts, threshold, multiplier) {
    X   <- splines::bs(seq_len(n), knots = cpts, degree = 1, intercept = TRUE)
    fit <- stats::lm.fit(X, x)$fitted.values
    rss <- sum((x - fit)^2)
    df  <- 2L * length(cpts) + 3L
    ic  <- n * log(rss / n) + df * penalty_factor
    list(cpts = cpts, fit = fit, rss = rss, df = df,
         threshold = threshold, multiplier = multiplier, ic = ic)
  }
  
  models <- list(score_model(integer(0), Inf, NA_real_))
  seen <- ""
  
  for (multiplier in sort(unique(multipliers), decreasing = TRUE)) {
    threshold <- base_threshold * multiplier
    cpts <- labs(
      x,
      thresh       = threshold,
      initial_test = initial_test,
      M            = M,
      retest_M     = retest_M
    )$cpts
    key <- paste(cpts, collapse = ",")
    if (!(key %in% seen)) {
      seen <- c(seen, key)
      models[[length(models) + 1L]] <- score_model(cpts, threshold, multiplier)
    }
  }
  
  ic_vals <- vapply(models, `[[`, numeric(1), "ic")
  best <- which.min(ic_vals)
  
  path <- data.frame(
    n_cpts     = vapply(models, function(m) length(m$cpts), integer(1)),
    threshold  = vapply(models, `[[`, numeric(1), "threshold"),
    multiplier = vapply(models, `[[`, numeric(1), "multiplier"),
    rss        = vapply(models, `[[`, numeric(1), "rss"),
    df         = vapply(models, `[[`, integer(1), "df"),
    ic         = ic_vals
  )
  
  list(cpts = models[[best]]$cpts,
       fit = models[[best]]$fit,
       threshold = models[[best]]$threshold,
       multiplier = models[[best]]$multiplier,
       ic = models[[best]]$ic,
       path = path)
}


# ------------------------------------------------------------------------------
# labs_threshold_path_fast
#
# Fast fixed-threshold path builder for LABS.  This is equivalent to running
# labs() once per threshold multiplier, but normalisation and prefix sums are
# computed once and reused across the whole path.
#
# Returns one row per unique change-point set encountered, including the null
# model.  The path is intentionally unscored; use labs_sic_fast() for SIC-backed
# model selection.
# ------------------------------------------------------------------------------
labs_threshold_path_fast <- function(x,
                                     initial_test = TRUE,
                                     M            = 2L,
                                     retest_M     = M,
                                     multipliers  = seq(0.50, 1.50, by = 0.05)) {
  
  if (!is.numeric(x))        stop("`x' must be a numeric vector.")
  if (anyNA(x))              stop("`x' must not contain NA values.")
  if (any(!is.finite(x)))    stop("`x' must not contain Inf or NaN values.")
  if (!is.logical(initial_test) || length(initial_test) != 1L || is.na(initial_test))
    stop("`initial_test' must be TRUE or FALSE.")
  if (!is.numeric(M) || length(M) != 1L || is.na(M) || M < 2L)
    stop("`M' must be an integer >= 2.")
  if (!is.numeric(retest_M) || length(retest_M) != 1L || is.na(retest_M) || retest_M < 2L)
    stop("`retest_M' must be an integer >= 2.")
  if (!is.numeric(multipliers) || length(multipliers) == 0L ||
      anyNA(multipliers) || any(multipliers <= 0)) {
    stop("`multipliers' must be a non-empty numeric vector of positive values.")
  }
  
  n <- length(x)
  if (n <= 2L) {
    return(data.frame(
      n_cpts = 0L,
      threshold = Inf,
      multiplier = NA_real_,
      key = "",
      cpts = I(list(integer(0)))
    ))
  }
  
  x_abs_max <- max(abs(x))
  if (x_abs_max == 0) {
    return(data.frame(
      n_cpts = 0L,
      threshold = Inf,
      multiplier = NA_real_,
      key = "",
      cpts = I(list(integer(0)))
    ))
  }
  
  M <- as.integer(M)
  retest_M <- as.integer(retest_M)
  
  y <- x / x_abs_max
  PY   <- c(0, cumsum(y))
  PY1  <- c(0, cumsum(y * seq_len(n)))
  PAD2 <- c(0, cumsum(abs(diff(y, differences = 2))))
  
  base_threshold <- stats::mad(diff(x, differences = 2) / sqrt(6)) *
    sqrt(2 * log(n))
  base_threshold_normalised <- base_threshold / x_abs_max
  
  rows <- list(data.frame(
    n_cpts = 0L,
    threshold = Inf,
    multiplier = NA_real_,
    key = "",
    cpts = I(list(integer(0)))
  ))
  seen <- ""
  
  for (multiplier in sort(unique(multipliers), decreasing = TRUE)) {
    threshold <- base_threshold * multiplier
    cpts <- labs_recursion(
      PY, PY1, PAD2, 1L, n,
      base_threshold_normalised * multiplier,
      initial_test,
      M,
      retest_M
    )
    key <- paste(cpts, collapse = ",")
    if (!(key %in% seen)) {
      seen <- c(seen, key)
      rows[[length(rows) + 1L]] <- data.frame(
        n_cpts = length(cpts),
        threshold = threshold,
        multiplier = multiplier,
        key = key,
        cpts = I(list(cpts))
      )
    }
  }
  
  do.call(rbind, rows)
}


# ------------------------------------------------------------------------------
# labs_sic_fast
#
# Fast SIC-backed model selection for LABS over the same fixed multiplier grid as
# labs_sic().  The selected model and SIC objective match labs_sic(), but the
# threshold path is computed with shared prefix sums instead of repeated calls to
# labs().
# ------------------------------------------------------------------------------
labs_sic_fast <- function(x,
                          initial_test = TRUE,
                          M            = 2L,
                          retest_M     = M,
                          multipliers  = seq(0.50, 1.50, by = 0.05),
                          alpha        = 1.01) {
  
  if (!is.numeric(x))        stop("`x' must be a numeric vector.")
  if (anyNA(x))              stop("`x' must not contain NA values.")
  if (any(!is.finite(x)))    stop("`x' must not contain Inf or NaN values.")
  if (!is.numeric(alpha) || length(alpha) != 1L || is.na(alpha) || alpha <= 0) {
    stop("`alpha' must be a single positive number.")
  }
  
  n <- length(x)
  if (n <= 2L) {
    return(list(cpts = integer(0), fit = x, threshold = Inf,
                multiplier = NA_real_, ic = -Inf,
                path = data.frame(n_cpts = 0L, threshold = Inf,
                                  multiplier = NA_real_, rss = 0, df = 0L,
                                  ic = -Inf)))
  }
  
  path <- labs_threshold_path_fast(
    x,
    initial_test = initial_test,
    M = M,
    retest_M = retest_M,
    multipliers = multipliers
  )
  
  penalty_factor <- log(n)^alpha
  
  score_one <- function(cpts) {
    X   <- splines::bs(seq_len(n), knots = cpts, degree = 1, intercept = TRUE)
    fit <- stats::lm.fit(X, x)$fitted.values
    rss <- sum((x - fit)^2)
    df  <- 2L * length(cpts) + 3L
    ic  <- n * log(rss / n) + df * penalty_factor
    list(fit = fit, rss = rss, df = df, ic = ic)
  }
  
  scores <- lapply(path$cpts, score_one)
  path$rss <- vapply(scores, `[[`, numeric(1), "rss")
  path$df  <- vapply(scores, `[[`, integer(1), "df")
  path$ic  <- vapply(scores, `[[`, numeric(1), "ic")
  path$key <- NULL
  
  best <- which.min(path$ic)
  
  list(cpts = path$cpts[[best]],
       fit = scores[[best]]$fit,
       threshold = path$threshold[best],
       multiplier = path$multiplier[best],
       ic = path$ic[best],
       path = path[, c("n_cpts", "threshold", "multiplier", "rss", "df", "ic")])
}


# ------------------------------------------------------------------------------
# labs_prepare_solution_path_fast
#
# Precompute the data shared by all fixed-threshold LABS solution paths for one
# signal.  This is mainly useful when several SIC-LABS configurations are being
# compared on the same x, because the normalised signal and prefix sums are then
# reused across configurations.
# ------------------------------------------------------------------------------
labs_prepare_solution_path_fast <- function(x) {
  
  if (!is.numeric(x))        stop("`x' must be a numeric vector.")
  if (anyNA(x))              stop("`x' must not contain NA values.")
  if (any(!is.finite(x)))    stop("`x' must not contain Inf or NaN values.")
  
  n <- length(x)
  x_abs_max <- if (n > 0L) max(abs(x)) else 0
  base_threshold <- if (n > 2L) {
    stats::mad(diff(x, differences = 2) / sqrt(6)) * sqrt(2 * log(n))
  } else {
    Inf
  }
  
  if (n <= 2L || x_abs_max == 0) {
    return(list(
      x = x,
      n = n,
      x_abs_max = x_abs_max,
      base_threshold = base_threshold,
      PY = numeric(0),
      PY1 = numeric(0),
      PAD2 = numeric(0)
    ))
  }
  
  y <- x / x_abs_max
  list(
    x = x,
    n = n,
    x_abs_max = x_abs_max,
    base_threshold = base_threshold,
    PY = c(0, cumsum(y)),
    PY1 = c(0, cumsum(y * seq_len(n))),
    PAD2 = c(0, cumsum(abs(diff(y, differences = 2))))
  )
}


# ------------------------------------------------------------------------------
# labs_threshold_path_prepared_fast
#
# Prepared-data version of labs_threshold_path_fast().  The `prepared' argument
# must be the output of labs_prepare_solution_path_fast().
# ------------------------------------------------------------------------------
labs_threshold_path_prepared_fast <- function(prepared,
                                             initial_test = TRUE,
                                             M            = 2L,
                                             retest_M     = M,
                                             multipliers  = seq(0.50, 1.50, by = 0.05)) {
  
  if (!is.list(prepared) || is.null(prepared$x) || is.null(prepared$n) ||
      is.null(prepared$x_abs_max) || is.null(prepared$base_threshold)) {
    stop("`prepared' must be created by labs_prepare_solution_path_fast().")
  }
  if (!is.logical(initial_test) || length(initial_test) != 1L || is.na(initial_test))
    stop("`initial_test' must be TRUE or FALSE.")
  if (!is.numeric(M) || length(M) != 1L || is.na(M) || M < 2L)
    stop("`M' must be an integer >= 2.")
  if (!is.numeric(retest_M) || length(retest_M) != 1L || is.na(retest_M) || retest_M < 2L)
    stop("`retest_M' must be an integer >= 2.")
  if (!is.numeric(multipliers) || length(multipliers) == 0L ||
      anyNA(multipliers) || any(multipliers <= 0)) {
    stop("`multipliers' must be a non-empty numeric vector of positive values.")
  }
  
  n <- prepared$n
  if (n <= 2L || prepared$x_abs_max == 0) {
    return(data.frame(
      n_cpts = 0L,
      threshold = Inf,
      multiplier = NA_real_,
      key = "",
      cpts = I(list(integer(0)))
    ))
  }
  
  M <- as.integer(M)
  retest_M <- as.integer(retest_M)
  base_threshold_normalised <- prepared$base_threshold / prepared$x_abs_max
  
  rows <- list(data.frame(
    n_cpts = 0L,
    threshold = Inf,
    multiplier = NA_real_,
    key = "",
    cpts = I(list(integer(0)))
  ))
  seen <- ""
  
  for (multiplier in sort(unique(multipliers), decreasing = TRUE)) {
    threshold <- prepared$base_threshold * multiplier
    cpts <- labs_recursion(
      prepared$PY,
      prepared$PY1,
      prepared$PAD2,
      1L,
      n,
      base_threshold_normalised * multiplier,
      initial_test,
      M,
      retest_M
    )
    key <- paste(cpts, collapse = ",")
    if (!(key %in% seen)) {
      seen <- c(seen, key)
      rows[[length(rows) + 1L]] <- data.frame(
        n_cpts = length(cpts),
        threshold = threshold,
        multiplier = multiplier,
        key = key,
        cpts = I(list(cpts))
      )
    }
  }
  
  do.call(rbind, rows)
}


# ------------------------------------------------------------------------------
# labs_sic_prepared_fast
#
# Prepared-data version of labs_sic_fast().  Use this when applying multiple
# LABS SIC configurations to the same signal.
# ------------------------------------------------------------------------------
labs_sic_prepared_fast <- function(prepared,
                                   initial_test = TRUE,
                                   M            = 2L,
                                   retest_M     = M,
                                   multipliers  = seq(0.50, 1.50, by = 0.05),
                                   alpha        = 1.01) {
  
  if (!is.numeric(alpha) || length(alpha) != 1L || is.na(alpha) || alpha <= 0) {
    stop("`alpha' must be a single positive number.")
  }
  
  n <- prepared$n
  x <- prepared$x
  if (n <= 2L) {
    return(list(cpts = integer(0), fit = x, threshold = Inf,
                multiplier = NA_real_, ic = -Inf,
                path = data.frame(n_cpts = 0L, threshold = Inf,
                                  multiplier = NA_real_, rss = 0, df = 0L,
                                  ic = -Inf)))
  }
  
  path <- labs_threshold_path_prepared_fast(
    prepared,
    initial_test = initial_test,
    M = M,
    retest_M = retest_M,
    multipliers = multipliers
  )
  
  penalty_factor <- log(n)^alpha
  
  score_one <- function(cpts) {
    X   <- splines::bs(seq_len(n), knots = cpts, degree = 1, intercept = TRUE)
    fit <- stats::lm.fit(X, x)$fitted.values
    rss <- sum((x - fit)^2)
    df  <- 2L * length(cpts) + 3L
    ic  <- n * log(rss / n) + df * penalty_factor
    list(fit = fit, rss = rss, df = df, ic = ic)
  }
  
  scores <- lapply(path$cpts, score_one)
  path$rss <- vapply(scores, `[[`, numeric(1), "rss")
  path$df  <- vapply(scores, `[[`, integer(1), "df")
  path$ic  <- vapply(scores, `[[`, numeric(1), "ic")
  path$key <- NULL
  
  best <- which.min(path$ic)
  
  list(cpts = path$cpts[[best]],
       fit = scores[[best]]$fit,
       threshold = path$threshold[best],
       multiplier = path$multiplier[best],
       ic = path$ic[best],
       path = path[, c("n_cpts", "threshold", "multiplier", "rss", "df", "ic")])
}


# ------------------------------------------------------------------------------
# labs_sic_batch_fast
#
# Evaluate several SIC-LABS configurations on one signal while sharing the
# precomputed solution-path inputs.  `configs' is a list of lists with elements
# method, initial_test, M, and retest_M; missing values default to
# initial_test = TRUE, M = 2, and retest_M = M.
# ------------------------------------------------------------------------------
labs_sic_batch_fast <- function(x,
                                configs = list(
                                  list(method = "LABS(SIC,T,M=2)",     initial_test = TRUE, M = 2L, retest_M = 2L),
                                  list(method = "LABS(SIC,T,M=3)",     initial_test = TRUE, M = 3L, retest_M = 3L),
                                  list(method = "LABS(SIC,T,M=3,R=2)", initial_test = TRUE, M = 3L, retest_M = 2L),
                                  list(method = "LABS(SIC,T,M=5)",     initial_test = TRUE, M = 5L, retest_M = 5L),
                                  list(method = "LABS(SIC,T,M=5,R=2)", initial_test = TRUE, M = 5L, retest_M = 2L)
                                ),
                                multipliers = seq(0.50, 1.50, by = 0.05),
                                alpha = 1.01) {
  
  if (!is.list(configs) || length(configs) == 0L) {
    stop("`configs' must be a non-empty list of configuration lists.")
  }
  
  prepared <- labs_prepare_solution_path_fast(x)
  
  results <- lapply(seq_along(configs), function(i) {
    cfg <- configs[[i]]
    M <- if (!is.null(cfg$M)) cfg$M else 2L
    retest_M <- if (!is.null(cfg$retest_M)) cfg$retest_M else M
    initial_test <- if (!is.null(cfg$initial_test)) cfg$initial_test else TRUE
    
    labs_sic_prepared_fast(
      prepared,
      initial_test = initial_test,
      M = M,
      retest_M = retest_M,
      multipliers = multipliers,
      alpha = alpha
    )
  })
  
  result_names <- vapply(seq_along(configs), function(i) {
    cfg <- configs[[i]]
    if (!is.null(cfg$method)) return(as.character(cfg$method))
    M <- if (!is.null(cfg$M)) cfg$M else 2L
    retest_M <- if (!is.null(cfg$retest_M)) cfg$retest_M else M
    sprintf("LABS(SIC,T,M=%s,R=%s)", M, retest_M)
  }, character(1))
  names(results) <- result_names
  
  results
}
