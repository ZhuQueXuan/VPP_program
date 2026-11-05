# LABS: Look-Ahead Binary Segmentation

These files support the computational results in "LABS: Extending the scope
of binary segmentation via a look-ahead device". They contain the LABS
implementation, simulation and data-analysis scripts, frozen public data,
reported output, and figure files.

LABS detects changes in slope in continuous piecewise-linear signals. The
main implementation is in `code/LABS_functions.R`. The configuration with the
best aggregate performance in the paper's simulation study uses SIC selection,
five proposal grid points and two re-test grid points.

## Quick start

```r
source("code/LABS_functions.R")

set.seed(1)
n <- 400
t <- seq_len(n)
signal <- ifelse(t <= 200, 0.01 * t, 2 + 0.04 * (t - 200))
x <- signal + rnorm(n, sd = 0.5)

fit <- labs_sic_fast(x, M = 5, retest_M = 2)
fit$cpts
plot(x, type = "l")
lines(fit$fit, col = 2, lwd = 2)
abline(v = fit$cpts, col = 2, lty = 2)
```

The lower-level `labs()` routine performs one thresholded run. The
`labs_sic_fast()` routine constructs a fixed-threshold solution path with
shared prefix sums and selects a model by SIC.

## Software

The reported analysis used R 4.5.2 on macOS. Install the required packages
with:

```r
install.packages(c(
  "Rcpp", "tidyverse", "cpop", "breakfast", "trendsegmentR",
  "jsonlite", "ggplot2", "patchwork"
))
```

Exact package versions are listed in `package_versions.txt`. A C++ compiler is
required because the MovingSumLin implementation compiles a C++ file through
Rcpp.

The MOSUM implementation is not included in these materials. On the first
full or smoke run, `code/fetch_mosum.R` downloads `MOSUM_linear.R` and
`mosumCwald.cpp` from commit
`290cef395a0bd691bb50fa401dd82f861f16ce01` of the authors' MovingSumLin
repository and verifies their checksums. This first run therefore requires an
internet connection. Later runs use the verified local copies in `external/`.
The table-only workflow does not download or execute this external code.

## Workflow

Run commands from this directory.

```sh
Rscript run_all.R
```

The default `full` mode reruns 500 replications per scenario for every method
except CPOP, which uses 50. It then regenerates all three figures and the CSV
inputs to Tables 1 to 4. Set `LABS_N_CORES` to an integer greater than one to
use multicore parallelism on Unix-like systems. The reported results used one
core. A full run took about 80 minutes on the machine used for the paper;
timings will vary by system.

For a short installation check, run:

```sh
LABS_REPRO_MODE=smoke Rscript run_all.R
```

To reconstruct the paper-table inputs from the supplied reported outputs
without rerunning the simulations or data analysis, run:

```sh
LABS_REPRO_MODE=tables Rscript run_all.R
```

## Contents

- `code/LABS_functions.R`: LABS routines, including the fast SIC solution path.
- `code/LABS_comparisons.R`: twelve-scenario comparative simulation.
- `code/fetch_mosum.R` and `code/load_mosum.R`: download, verify, and load the
  pinned upstream MovingSumLin implementation used for the MOSUM comparison.
- `code/temperature_analysis_v16.R`: frozen-data temperature analysis.
- `code/trap_figure.R`: trap-signal illustration.
- `code/make_paper_tables.R`: CSV inputs for Tables 1 to 4.
- `data/temperature-anomaly/`: frozen HadCRUT5 data and metadata downloaded
  through Our World in Data on 7 August 2026.
- `results/simulation/`: raw and summarized results reported in the paper.
- `results/temperature/`: detected changes, timings, sensitivity analysis, and
  LABS segment slopes reported in the paper.
- `figures/`: the three reported figures.

The temperature script uses the frozen data by default. To download the live
Our World in Data version instead, run it with `LABS_USE_FROZEN_DATA=false`;
doing so may not reproduce the reported results if the source has changed.

## CPOP boundaries

Both analysis scripts remove CPOP's automatic boundaries at 0 and `n - 1`
before evaluating or displaying its estimated internal change-points. This is
the convention used for the paper's simulation and temperature analyses.

## Output locations

A full run writes new simulation output to `results/reproduced_simulation/`.
A smoke run writes to `results/smoke_simulation/`. Temperature outputs are
written to `results/temperature/`; figures to `figures/`; and table inputs to
`results/paper_tables/`.

## Licence

The MIT licence applies only to the original code supplied in these materials.
It does not apply to MovingSumLin or to any R package installed separately.
MovingSumLin is downloaded directly from its authors' repository and remains
subject to the terms set by its copyright holders.

## Citation

If you use LABS in published work, please cite the accompanying paper. GitHub
also exposes the citation metadata in `CITATION.cff` through its **Cite this
repository** control.
