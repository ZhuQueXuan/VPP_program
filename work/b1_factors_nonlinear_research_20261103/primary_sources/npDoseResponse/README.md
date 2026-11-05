[![PyPI pyversions](https://img.shields.io/pypi/pyversions/npDoseResponse.svg)](https://pypi.python.org/pypi/npDoseResponse/)
[![PyPI version](https://badge.fury.io/py/npDoseResponse.svg)](https://badge.fury.io/py/NPDoseResponse)
[![Downloads](https://static.pepy.tech/badge/npDoseResponse)](https://pepy.tech/project/npDoseResponse)
[![Documentation Status](https://readthedocs.org/projects/npdoseresponse/badge/?version=latest)](http://npdoseresponse.readthedocs.io/?badge=latest)

# Nonparametric Inference on Dose-Response Curve and its Derivative

This package provides the implementation of estimating and conducting valid inference on the covariate-adjusted regression function (or the dose-response curve in causal inference) and its derivative through the proposed integral estimator and a localized derivative estimator in [[1]](#npdoseresponse). It also implements the regression adjustment (RA), inverse probability weighting (IPW) and doubly robust (DR) estimators of the dose-response curve and its derivative function with and without the positivity condition in [[2]](#npdrderiv). All the code for simulations and real-world applications in our papers are documented in [Paper 1](https://github.com/zhangyk8/NPDoseResponse/tree/main/Paper_Code) and [Paper 2](https://github.com/zhangyk8/npDRDeriv).

* Free software: MIT license
* Python Package Documentation: [https://npdoseresponse.readthedocs.io](https://npdoseresponse.readthedocs.io).
* We also provide an R package [npDoseResponse](https://cran.r-project.org/package=npDoseResponse) for those estimators in [[1]](#npdoseresponse), though the Python package will be numerically stabler.

Installation guide
--------

```npDoseResponse``` requires Python 3.8+ (earlier version might be applicable) and [NumPy](http://www.numpy.org/). To install the latest version of ```npDoseResponse``` from this repository, run:

```
python setup.py install
```

To pip install a stable release, run:
```
pip install npDoseResponse
```

References
--------

<a name="npdoseresponse">[1]</a> Y. Zhang, Y.-C. Chen, and A. Giessing (2024+) Nonparametric Inference on Dose-Response Curves Without the Positivity Condition [arXiv:2405.09003](https://arxiv.org/abs/2405.09003).

<a name="npdrderiv">[2]</a> Y. Zhang and Y.-C. Chen (2025+) Doubly Robust Inference on Causal Derivative Effects for Continuous Treatments [arXiv:2501.06969](http://arxiv.org/abs/2501.06969).
