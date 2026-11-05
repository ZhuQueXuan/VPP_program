\# Power Quality Disturbance Dataset for Electric Vehicle Charging  

\*\*Source Code Documentation and Reproducibility Notes\*\*



\## 1. Overview



This repository provides the source code used to preprocess, visualize, analyze, and technically validate the electric vehicle (EV) charging dataset under standardized power quality (PQ) disturbances. The dataset and code are released to support \*\*reproducible research\*\*, \*\*method development\*\*, and \*\*benchmarking\*\* in PQ disturbance analysis, EV charging behavior modeling, and data-driven diagnostics.



All scripts are written in Python and correspond directly to the analysis steps reported in the accompanying manuscript, including data visualization, feature extraction, dimensionality reduction, clustering analysis, and technical validation.



---



\## 2. File Structure and Purpose



Table 1 summarizes the purpose of each Python script included in this repository.



\### Table 1. Description of source code files



| File name | Purpose |

|----------|---------|

| `csv\_name.py` | Parses and decodes metadata embedded in CSV filenames (e.g., disturbance type, voltage amplitude, frequency, duration, SOC, EV model). Enables automated grouping and labeling of experiments without manual annotation. |

| `data\_vis.py` | Generates time-domain visualizations of voltage and current signals under different PQ disturbances. Used to illustrate disturbance onset, duration, and charging-response behavior. |

| `technical\_validation.py` | Implements technical validation procedures described in the manuscript, including signal integrity checks, consistency analysis, and robustness evaluation across charging configurations. |

| `clustering.py` | Extracts statistical time-domain and frequency-domain features from voltage and current signals and performs clustering using PCA and $k$-means. Used to evaluate data separability and structural consistency across disturbance types. |

| `tsne.py` | Applies t-distributed stochastic neighbor embedding (t-SNE) to the extracted feature space for nonlinear dimensionality reduction and visualization of disturbance similarity. |

| `UMAP.py` | Applies Uniform Manifold Approximation and Projection (UMAP) as an alternative nonlinear embedding method to assess robustness of clustering structure. |



Each script is modular and can be executed independently once the dataset path is specified.



---



\## 3. Reproducibility and Reuse



The provided code enables \*\*full reproduction of the analyses and figures reported in the manuscript\*\*, including:



\- Time-domain visualization of PQ disturbances and EV charging responses  

\- Feature extraction from voltage and current signals  

\- Dimensionality reduction using PCA, t-SNE, and UMAP  

\- Unsupervised clustering and confusion-matrix analysis  

\- Technical validation across different charging conditions  



The code can be directly reused for:



\- Developing and testing PQ disturbance detection or classification algorithms  

\- Benchmarking feature engineering strategies  

\- Evaluating clustering or representation-learning methods  

\- Comparing voltage-domain, current-domain, or joint-feature approaches  



---



\## 4. Scope and Limitations of Simulation



The scripts operate on \*\*experimentally measured data\*\* obtained from controlled laboratory tests under IEEE-defined PQ disturbance categories. They \*\*do not simulate grid events or generate synthetic disturbances\*\*.



This design choice reflects the primary goal of the dataset:



> to provide a \*\*reliable, standardized, and experimentally grounded reference dataset\*\*, rather than a fully synthetic simulation framework.



Researchers may extend the code to:

\- Analyze synthetic or simulated PQ signals  

\- Incorporate composite or overlapping disturbances  

\- Adapt the pipeline to other EV models or charging architectures  



The modular structure of the code supports such extensions.



---



\## 5. Dependencies and Environment



The scripts rely on standard scientific Python libraries:



\- `numpy`

\- `pandas`

\- `scipy`

\- `scikit-learn`

\- `matplotlib`

\- `seaborn`



All analyses were performed using \*\*Python 3.x\*\*. No proprietary software is required.



---



\## 6. Intended Audience



This codebase is intended for:



\- Researchers in power quality analysis and smart grids  

\- EV charging and energy systems researchers  

\- Data scientists working on signal processing or clustering  

\- Developers benchmarking machine learning methods on real-world PQ data  



---



\## 7. Citation and Acknowledgment



If you use this dataset or code in your research, please cite the associated manuscript and dataset DOI as provided on the OSF project page.



---




