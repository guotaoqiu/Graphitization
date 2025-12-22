# Li Adsorption on Doped/Pristine Graphene Workflow

## Overview

This workflow calculates **formation energies** for doped graphene structures and **adsorption energies** for Li atoms on both pristine and doped graphene surfaces.

### Scientific Background

**Formation Energy** (for doped structures):
```
Ef = Edoped - Epure + EC - Esub
```
- Measures the energy cost of substituting a C atom with a dopant
- Positive Ef → endothermic (unfavorable), Negative Ef → exothermic (favorable)

**Adsorption Energy** (for Li on graphene):
```
Eads = Etotal - Eslab - ELi
```
- Measures the binding strength of Li to the surface
- More negative Eads → stronger binding

### Hypothesis

**Boron-doped graphene** is expected to show stronger Li binding because:
- B has one fewer electron than C (electron deficient)
- Creates electron-deficient sites that can better accommodate Li's electron
- Enhanced bonding interaction with Li

---

## Workflow Structure

```
Li_adsorption_graphene/
├── 00_initial_structure/
│   └── POSCAR_REV.vasp           # Pristine 3x3 graphene supercell (18 C atoms)
├── 01_doped_structures/           # Generated doped structures
├── 02_adsorption_structures/      # Li adsorption configurations
├── 03_calculations/
│   ├── doped_relaxation/          # Relaxed doped structures
│   └── adsorption/                # Li adsorption calculations
├── 04_analysis/                   # Analysis results and plots
└── scripts/                       # Workflow scripts
    ├── 01_generate_doped_graphene.py
    ├── 02_relax_doped_structures.sh
    ├── 03_generate_li_adsorption.py
    ├── 04_submit_adsorption_jobs.sh
    └── 05_analyze_results.py
```

---

## Quick Start Guide

### Prerequisites
- Python 3.7+ with pymatgen, pandas, numpy
- Access to HPC cluster with VASP
- `mpjob` tool for job submission

### Step 1: Generate Doped Structures

```bash
cd Li_adsorption_graphene/scripts
python3 01_generate_doped_graphene.py
```

This generates:
- Pristine graphene structure (reference)
- Doped structures with C014 substituted by: B, N, O, F, Si, P, S, Cl, Br, I, Al, Se

**Output**: `../01_doped_structures/`

### Step 2: Relax Doped Structures

```bash
chmod +x 02_relax_doped_structures.sh
./02_relax_doped_structures.sh
```

Submits VASP relaxation jobs with parameters:
- `ISIF=2` (relax ions only, not cell shape - for 2D materials)
- `LDIPOL=T`, `IDIPOL=3` (dipole corrections for slab)
- `IVDW=11` (DFT-D3 van der Waals correction)

**Monitor**: `squeue -u $USER`

**Output**: `../03_calculations/doped_relaxation/`

### Step 3: Generate Li Adsorption Sites

After doped structures are relaxed:

```bash
python3 03_generate_li_adsorption.py
```

Generates Li adsorption configurations with 3+ adsorption sites:
- **Top site**: Above a C/dopant atom
- **Hollow site**: Center of hexagonal ring
- **Bridge site**: Above C-C bond

For doped structures, sites are defined relative to the dopant atom.

**Output**: `../02_adsorption_structures/`

### Step 4: Submit Adsorption Calculations

```bash
chmod +x 04_submit_adsorption_jobs.sh
./04_submit_adsorption_jobs.sh
```

Submits VASP calculations for all Li adsorption configurations.

**Monitor**: `squeue -u $USER`

**Output**: `../03_calculations/adsorption/`

### Step 5: Analyze Results

After all calculations complete:

```bash
python3 05_analyze_results.py
```

Calculates:
1. **Formation energies** for all doped structures
2. **Adsorption energies** for all Li adsorption sites
3. Identifies strongest Li binding sites
4. Generates comparison plots and reports

**Output**: `../04_analysis/`
- `doped_structures_results.csv` - Formation energies
- `adsorption_results.csv` - Adsorption energies
- `summary_report.txt` - Human-readable summary
- `complete_results.json` - Complete data

---

## Dopant Elements

The workflow includes the following dopants:

| Element | Reason |
|---------|--------|
| **B** | Electron deficient - expected strong Li binding |
| N | Isoelectronic to C, more electronegative |
| O, F | Highly electronegative |
| Si | Same group as C, larger |
| P, S | Higher periods of N, O |
| Cl, Br, I | Halogens with varying sizes |
| Al | Similar to B, larger |
| Se | Similar to S |

---

## Adsorption Sites

For each substrate (pristine or doped), Li is placed at multiple sites:

### Pristine Graphene
- `top`: Above a C atom near cell center
- `hollow`: Center of hexagonal ring
- `bridge`: Above C-C bond midpoint

### Doped Graphene
- `top_dopant`: Directly above dopant atom
- `hollow_dopant`: Center of ring containing dopant
- `bridge_dopant`: Above dopant-neighbor bond

---

## VASP Parameters

All calculations use:

```
MODE: native
TASK_TYPE: u_relax
PARTITION: cu
NCORES: 64
CUSTOM_PARAMS: ISIF=2, LDIPOL=.TRUE., IDIPOL=3, IVDW=11
```

**Why these parameters?**
- `ISIF=2`: Relaxes atomic positions only (keeps cell fixed for 2D materials)
- `LDIPOL=T, IDIPOL=3`: Dipole correction along z-axis (perpendicular to slab)
- `IVDW=11`: DFT-D3 method for van der Waals interactions (important for Li-graphene)

---

## Expected Results

### Formation Energies
- **Negative Ef**: Doping is thermodynamically favorable
- **Positive Ef**: Doping is unfavorable (requires energy input)

Typically:
- B, N: Small Ef (similar size to C)
- Larger atoms (Si, Cl, etc.): Higher Ef (size mismatch)

### Adsorption Energies
- **More negative Eads**: Stronger Li binding
- **Less negative/positive Eads**: Weaker/no binding

Hypothesis:
- **B-doped graphene** should show most negative Eads (strongest binding)
- Pristine graphene: moderate binding
- Electronegative dopants (F, Cl): potentially weaker binding

---

## Troubleshooting

### Issue: No pristine structure found
**Solution**: Ensure `00_initial_structure/POSCAR_REV.vasp` exists

### Issue: mpjob command not found
**Solution**: Load mpvasp module: `module load mpvasp`

### Issue: Calculations not completing
**Solution**:
- Check OUTCAR for errors
- Try increasing walltime
- Verify VASP parameters are compatible

### Issue: Missing chemical potentials
**Solution**: Check that dopant element is in `CHEMICAL_POTENTIALS` dictionary in `05_analyze_results.py`

---

## Customization

### Add More Dopants
Edit `scripts/01_generate_doped_graphene.py`:
```python
DOPANT_ELEMENTS = ['B', 'N', 'YOUR_ELEMENT', ...]
```

### Change Adsorption Height
Edit `scripts/03_generate_li_adsorption.py`:
```python
ADSORPTION_HEIGHT = 2.0  # Angstroms
```

### Adjust VASP Parameters
Edit job submission scripts:
```bash
CUSTOM_PARAMS="ISIF=2,LDIPOL=.TRUE.,IDIPOL=3,IVDW=11,YOUR_PARAM=VALUE"
```

---

## Output Files

### Doped Structures Results
`04_analysis/doped_structures_results.csv`:
- Structure name, dopant element
- Energy, formation energy
- Calculation status

### Adsorption Results
`04_analysis/adsorption_results.csv`:
- Structure name, substrate (pristine/doped)
- Dopant element, adsorption site
- Energy, adsorption energy

### Summary Report
`04_analysis/summary_report.txt`:
- Overview of all calculations
- Formation energies ranked by dopant
- Adsorption energies by substrate and site
- Top 10 strongest Li binding configurations

---

## Chemical Potentials Reference

Chemical potentials (per atom) used in energy calculations are from DFT calculations of bulk/molecular references. Key values:

```
C:  -9.2287 eV
Li: -1.9089 eV
B:  -6.6794 eV
N:  -8.3365 eV
Si: -5.4253 eV
...
```

Full table in: `scripts/05_analyze_results.py`

---

## Workflow Timing Estimates

- **Step 1** (Structure generation): ~1 minute
- **Step 2** (Doped structure relaxation): ~2-6 hours per structure
- **Step 3** (Adsorption site generation): ~1 minute
- **Step 4** (Adsorption calculations): ~2-6 hours per structure
- **Step 5** (Analysis): ~1 minute

**Total**: ~1-2 days for complete workflow (depends on queue wait times)

---

## Citation

If you use this workflow, please cite:
```
Li Adsorption on Doped Graphene Workflow
Part of: High-Throughput Graphitization Study
```

---

## Contact

For questions or issues, refer to the main repository documentation or contact your HPC support team.

---

**Version**: 1.0
**Last Updated**: 2024-12-22
**Status**: Ready for Production ✅
