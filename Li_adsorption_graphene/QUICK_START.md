# Quick Start: Li Adsorption on Doped Graphene

## TL;DR - Complete Workflow in 5 Commands

```bash
cd Li_adsorption_graphene/scripts

# 1. Generate doped structures
python3 01_generate_doped_graphene.py

# 2. Relax doped structures (wait for completion)
./02_relax_doped_structures.sh

# 3. Generate Li adsorption sites
python3 03_generate_li_adsorption.py

# 4. Submit adsorption calculations (wait for completion)
./04_submit_adsorption_jobs.sh

# 5. Analyze results
python3 05_analyze_results.py
```

## What This Workflow Does

### Formation Energy
Calculate how much energy it costs to dope graphene:
```
Ef = Edoped - Epure + EC - Esub
```
- Negative = favorable
- Positive = unfavorable

### Adsorption Energy
Calculate how strongly Li binds to graphene:
```
Eads = Etotal - Eslab - ELi
```
- More negative = stronger binding

### Hypothesis
**B-doped graphene** should bind Li strongest (most negative Eads) because B is electron-deficient.

---

## Prerequisites

```bash
# Install Python packages
pip install pymatgen pandas numpy

# Load VASP tools (on HPC)
module load mpvasp
```

---

## Workflow Steps

### Step 1: Generate Structures (1 min)

```bash
cd Li_adsorption_graphene/scripts
python3 01_generate_doped_graphene.py
```

**Output**: 13 structures (1 pristine + 12 doped with B, N, O, F, Si, P, S, Cl, Br, I, Al, Se)

---

### Step 2: Relax Structures (2-6 hrs × 13)

```bash
./02_relax_doped_structures.sh
```

**Monitor**:
```bash
squeue -u $USER
./check_status.sh
```

**VASP Settings**:
- `ISIF=2` - relax atoms only (2D material)
- `LDIPOL=T, IDIPOL=3` - dipole correction
- `IVDW=11` - vdW correction

---

### Step 3: Generate Li Sites (1 min)

```bash
python3 03_generate_li_adsorption.py
```

**Output**: ~39 structures (3 sites × 13 substrates)

Sites:
- Top (above atom)
- Hollow (hexagon center)
- Bridge (bond midpoint)

---

### Step 4: Submit Adsorption Calculations (2-6 hrs × 39)

```bash
./04_submit_adsorption_jobs.sh
```

**Monitor**:
```bash
./check_status.sh
```

---

### Step 5: Analyze (1 min)

```bash
python3 05_analyze_results.py
cd ../04_analysis
cat summary_report.txt
```

**Key Questions**:
1. Which dopant has lowest Ef? (easiest to synthesize)
2. Which substrate binds Li strongest? (most negative Eads)
3. Is B-doped > pristine? (test hypothesis)
4. Which site is preferred?

---

## File Structure

```
Li_adsorption_graphene/
├── 00_initial_structure/
│   └── POSCAR_REV.vasp          # 3×3 graphene (18 C atoms)
├── 01_doped_structures/          # Generated doped structures
├── 02_adsorption_structures/     # Li adsorption configs
├── 03_calculations/
│   ├── doped_relaxation/         # VASP results (doped)
│   └── adsorption/               # VASP results (Li+graphene)
├── 04_analysis/                  # CSV, JSON, reports
└── scripts/                      # All workflow scripts
```

---

## Output Files

### `04_analysis/doped_structures_results.csv`
| structure_name | dopant | energy | formation_energy | status |
|----------------|--------|---------|------------------|---------|
| graphene_B_doped | B | -XXX.XX | X.XX | completed |

### `04_analysis/adsorption_results.csv`
| structure_name | dopant | site | energy | adsorption_energy | status |
|----------------|--------|------|---------|-------------------|---------|
| graphene_B_Li_top_dopant | B | top_dopant | -XXX.XX | -X.XX | completed |

### `04_analysis/summary_report.txt`
- Formation energies ranked
- Adsorption energies by substrate
- Top 10 strongest Li binding sites

---

## Typical Results

### Formation Energy (Ef)
```
B:  ~0.5 eV  (favorable, similar size to C)
N:  ~0.6 eV
Si: ~1.0 eV  (larger atom, more strain)
F:  ~2.0 eV  (small, very different)
```

### Adsorption Energy (Eads)
```
B-doped:  -1.2 to -1.5 eV  (strong)
Pristine: -0.8 to -1.0 eV  (moderate)
F-doped:  -0.5 to -0.7 eV  (weak)
```

**Site preference**: Usually Hollow > Top > Bridge for pristine

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: pymatgen` | `pip install pymatgen` |
| `mpjob: command not found` | `module load mpvasp` |
| Jobs failing | Check `OUTCAR` for errors, try `MODE="fast"` |
| No pristine energy | Pristine must complete before analysis |

---

## Check Progress Anytime

```bash
cd Li_adsorption_graphene/scripts
./check_status.sh
```

Shows completion rates for:
- Pristine relaxation
- Doped structure relaxations
- Li adsorption calculations

---

## Optional: Relax Pristine First

For best accuracy, relax pristine graphene before doping:

```bash
./00_relax_pristine.sh
# Wait for completion
cp ../03_calculations/pristine_relaxation/CONTCAR ../00_initial_structure/
# Then proceed with Step 1
```

---

## Timeline

| Step | Time |
|------|------|
| 1. Generate doped | 1 min |
| 2. Relax doped | 26-78 hrs (parallel) |
| 3. Generate Li sites | 1 min |
| 4. Adsorption calcs | 78-234 hrs (parallel) |
| 5. Analysis | 1 min |

**Total**: 1-2 days wallclock (depends on queue)

---

## Key Insight

The workflow answers:
> **"Which dopant makes graphene bind Li strongest?"**

Expected: **B-doped graphene** (electron-deficient → attracts Li+)

Use results to:
- Design better Li-ion battery anodes
- Predict synthesis conditions (from Ef)
- Guide experimental synthesis

---

## Need Help?

- Detailed guide: `WORKFLOW_GUIDE.txt`
- Full documentation: `README.md`
- Script details: Check script headers
- VASP issues: HPC support team

---

**Ready to start?**

```bash
cd Li_adsorption_graphene/scripts
python3 01_generate_doped_graphene.py
```

🚀 Good luck!
