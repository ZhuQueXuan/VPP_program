#!/usr/bin/env python

import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="npDoseResponse",
    version="0.0.10",
    author="Yikun Zhang",
    author_email="yikunzhang@foxmail.com",
    description="Nonparametric Inference on Dose-Response Curve and its Derivative: With and Without Positivity",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/zhangyk8/npDoseResponse",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    packages=setuptools.find_packages(),
    # packages=["npDoseResponse"],
    install_requires=["numpy >= 1.16", "scipy", "scikit-learn", "torch"],
    python_requires=">=3.8",
)
