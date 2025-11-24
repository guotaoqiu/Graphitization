# High-Throughput Graphite Doping Calculation Workflow

[![Status](https://img.shields.io/badge/status-ready-green)]()
[![Python](https://img.shields.io/badge/python-3.7+-blue)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

## Overview

This repository contains a complete **Standard Operating Procedure (SOP)** for high-throughput computational studies of doped graphite structures. The workflow automates the calculation of lattice parameters, interlayer spacing, and formation energies for various doping configurations using DFT (VASP) via the company-internal `mpvasp` tool.

### Key Features

✅ **Automated workflow** from pristine structure relaxation to results analysis
✅ **Support for multiple doping types**: substitutional and interstitial
✅ **High-throughput**: batch processing of multiple dopant elements
✅ **Comprehensive analysis**: lattice parameters, interlayer spacing, energies
✅ **Modular design**: separate scripts for each workflow step
✅ **Rich output**: CSV, JSON, and human-readable reports

---

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Workflow
```bash
cd scripts

# Step 1: Relax pristine graphite (~1-2 hours)
./00_relax_pristine.sh

# Wait for completion, then copy relaxed structure
cd ../00_initial_structure/pristine_relaxation
cp CONTCAR ../CONTCAR
cd ../../scripts

# Step 2: Generate doped structures (~1 minute)
python3 01_generate_doped_structures.py

# Step 3: Submit calculations (~30 min - 4 hours per structure)
./02_batch_submit_jobs.sh

# Monitor progress
./02b_monitor_jobs.sh

# Step 4: Extract results (~1 minute)
python3 03_extract_results.py

# Step 5: Analyze results
python3 04_example_analysis.py
```

### 3. View Results
```bash
cd ../03_analysis
cat summary_report.txt
less results_summary.csv
```

See [QUICK_START.md](QUICK_START.md) for detailed quick start guide.

---

## Documentation

📚 **[Full SOP Documentation](SOP_HIGH_THROUGHPUT_GRAPHITE_DOPING.md)** - Complete workflow guide
🚀 **[Quick Start Guide](QUICK_START.md)** - Get started in minutes
📊 **[Workflow Diagram](WORKFLOW_DIAGRAM.txt)** - Visual workflow representation

---

## Repository Structure

```
Graphitization/
├── README.md                                  # This file
├── QUICK_START.md                            # Quick start guide
├── SOP_HIGH_THROUGHPUT_GRAPHITE_DOPING.md   # Full SOP documentation
├── WORKFLOW_DIAGRAM.txt                      # Visual workflow
├── requirements.txt                          # Python dependencies
│
├── 00_initial_structure/                     # Initial structures
│   └── graphite_pristine.vasp               # Pristine graphite unit cell
│
├── 01_structure_generation/                  # Generated structures
├── 02_calculations/                          # Calculation results
├── 03_analysis/                              # Analysis outputs
│
└── scripts/                                  # Workflow scripts
    ├── 00_relax_pristine.sh                 # Step 0: Pristine relaxation
    ├── 01_generate_doped_structures.py      # Step 1: Structure generation
    ├── 02_batch_submit_jobs.sh              # Step 2: Batch submission
    ├── 02b_monitor_jobs.sh                  # Monitor job status
    ├── 03_extract_results.py                # Step 3: Result extraction
    └── 04_example_analysis.py               # Step 4: Advanced analysis
```

---

## Workflow Summary

```
Pristine Structure → Relax → Generate Doped Structures → Submit Calculations
                                                                 ↓
                                                          Monitor Jobs
                                                                 ↓
           Analysis & Plots ← Extract Results ← Completed Calculations
```

---

## Supported Doping Types

### Substitutional Doping
Dopant atom replaces a carbon atom in the graphite lattice.

### Interstitial Doping
Dopant atom is inserted between graphene layers.

### Default Dopant Elements
- Boron (B)
- Nitrogen (N)
- Lanthanum (La)
- Magnesium (Mg)
- Aluminum (Al)
- Silicon (Si)
- Phosphorus (P)
- Sulfur (S)

*Easily customizable in `scripts/01_generate_doped_structures.py`*

---

## Output Data

For each doped structure, the workflow extracts:

- **Lattice parameters**: a, b, c, α, β, γ
- **Volume**: Unit cell volume
- **Interlayer spacing**: Average, min, max
- **Energy**: Total energy, energy per atom
- **Formation energy**: Relative to pristine graphite
- **Structural info**: Composition, doping type, dopant element

Results are exported in multiple formats:
- **CSV**: `results_summary.csv` (Excel-compatible)
- **JSON**: `results_complete.json` (machine-readable)
- **TXT**: `summary_report.txt` (human-readable)

---

## Analysis Capabilities

The included analysis scripts can:

✓ Compare interlayer spacing across dopants
✓ Identify dopants that promote graphitization
✓ Rank structures by formation energy (stability)
✓ Compare substitutional vs. interstitial effects
✓ Generate publication-quality plots
✓ Export key findings in structured format

---

## Requirements

### Software
- **mpvasp** (company-internal VASP automation tool)
- **Python 3.7+**
- **pymatgen** (for structure manipulation)
- **pandas** (for data analysis)
- **numpy** (for numerical operations)
- Optional: **matplotlib** (for plotting)

### Hardware
- Access to HPC cluster with VASP
- Recommended: 64+ cores per calculation for reasonable runtime

---

## Customization

### Change Dopant Elements
Edit `scripts/01_generate_doped_structures.py`:
```python
DOPANT_ELEMENTS = ['B', 'La', 'Mg', 'YOUR_ELEMENT']
```

### Adjust Calculation Parameters
Edit `scripts/02_batch_submit_jobs.sh`:
```bash
TASK_TYPE="u_relax"              # or double_relax_static, etc.
NCORES=64                        # cores per job
PARTITION="cu"                   # your cluster partition
MODE="fast"                      # fast, normal, or native
```

### Generate Supercells
Uncomment supercell section in `scripts/01_generate_doped_structures.py` for lower doping concentrations.

See [SOP documentation](SOP_HIGH_THROUGHPUT_GRAPHITE_DOPING.md) for detailed customization options.

---

## Troubleshooting

### Common Issues

**Q: mpjob command not found**
A: Load the mpvasp module or add to PATH: `module load mpvasp`

**Q: ImportError for pymatgen**
A: Install dependencies: `pip install -r requirements.txt`

**Q: Calculations failing**
A: Check OUTCAR for errors. Try `MODE="normal"` for better convergence.

**Q: No interlayer spacing data**
A: Ensure calculations completed successfully. Check `02b_monitor_jobs.sh`.

See [SOP documentation](SOP_HIGH_THROUGHPUT_GRAPHITE_DOPING.md#troubleshooting) for more troubleshooting tips.

---

## Citation

If you use this workflow in your research, please cite:

```
High-Throughput Graphite Doping Workflow
https://github.com/guotaoqiu/Graphitization
```

---

## License

MIT License - See LICENSE file for details

---

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

---

## Contact

For questions or issues:
- Open an issue on GitHub
- Contact your HPC support team for `mpvasp` related questions

---

## Acknowledgments

- Materials Project for workflow inspiration
- pymatgen development team
- VASP development team

---

**Version**: 1.0
**Last Updated**: 2024-11-24
**Status**: Production Ready ✅
