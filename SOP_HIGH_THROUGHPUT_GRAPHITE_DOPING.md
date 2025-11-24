# SOP: High-Throughput Calculation for Graphite Doping Studies

## Overview

This Standard Operating Procedure (SOP) provides a complete workflow for high-throughput computational studies of doped graphite structures. The workflow calculates lattice parameters, interlayer spacing, and formation energies for various doping configurations (interstitial and substitutional) with different dopant elements.

**Software Requirements:**
- `mpvasp` (company-internal VASP automation tool)
- Python 3.x with pymatgen
- Standard Unix tools (bash, etc.)

**Calculation Method:**
- DFT calculations via VASP
- Workflow similar to Materials Project
- Automated job submission via `mpjob` command

---

## Directory Structure

```
Graphitization/
├── 00_initial_structure/          # Pristine graphite structure
│   ├── graphite_pristine.vasp     # Initial unit cell
│   ├── pristine_relaxation/       # Relaxation calculation
│   └── CONTCAR                    # Relaxed structure (after Step 1)
│
├── 01_structure_generation/       # Generated doped structures
│   └── doped_structures/          # All doped structure files
│       ├── graphite_sub_*.vasp    # Substitutional doping
│       ├── graphite_int_*.vasp    # Interstitial doping
│       └── structure_metadata.json # Metadata for all structures
│
├── 02_calculations/               # Calculation jobs
│   ├── graphite_sub_B_site0/      # Individual job directories
│   ├── graphite_int_La_pos0/
│   ├── ...
│   ├── submitted_jobs.log         # Submission log
│   └── failed_submissions.log     # Failed submissions
│
├── 03_analysis/                   # Results and analysis
│   ├── results_summary.csv        # Summary in CSV format
│   ├── results_complete.json      # Complete results in JSON
│   └── summary_report.txt         # Human-readable report
│
└── scripts/                       # Workflow scripts
    ├── 00_relax_pristine.sh
    ├── 01_generate_doped_structures.py
    ├── 02_batch_submit_jobs.sh
    ├── 02b_monitor_jobs.sh
    └── 03_extract_results.py
```

---

## Workflow Steps

### Step 0: Relax Pristine Graphite Structure

**Objective:** Obtain an accurately relaxed pristine graphite unit cell to use as the reference structure.

**Commands:**
```bash
cd scripts
bash 00_relax_pristine.sh
```

**What it does:**
- Takes the initial graphite structure from `00_initial_structure/graphite_pristine.vasp`
- Submits a double relaxation + static calculation using `mpjob`
- Uses task type: `u_double_relax_static` for high accuracy
- Calculation mode: `normal` (good balance of speed and accuracy)

**Wait for completion** (check with standard cluster monitoring tools like `squeue`)

**After completion:**
```bash
cd ../00_initial_structure/pristine_relaxation
# Check the calculation completed successfully
grep "reached required accuracy" OUTCAR

# Copy the relaxed structure to parent directory
cp CONTCAR ../CONTCAR
```

**Important Notes:**
- This step is CRITICAL - all doped structures will be based on this relaxed unit cell
- Make sure the calculation converged properly before proceeding
- Record the final energy for formation energy calculations later

**Expected time:** ~30 minutes to 2 hours (depending on cluster load)

---

### Step 1: Generate Doped Structures

**Objective:** Create all doped structure variants (substitutional and interstitial) for high-throughput screening.

**Commands:**
```bash
cd scripts
python3 01_generate_doped_structures.py
```

**What it does:**
- Reads the relaxed CONTCAR from `00_initial_structure/`
- Generates substitutional doped structures (dopant replaces C atom)
- Generates interstitial doped structures (dopant added between layers)
- Creates metadata file tracking all structure information
- Default dopants: B, N, La, Mg, Al, Si, P, S (easily customizable)

**Customization:**
Edit `scripts/01_generate_doped_structures.py`:

```python
# Line ~213: Modify dopant list
DOPANT_ELEMENTS = ['B', 'N', 'La', 'Mg', 'Al', 'Si', 'P', 'S', 'Your_Element']

# Lines ~227-240: Uncomment to generate supercells for lower doping concentrations
# supercell_matrix = [[2, 0, 0], [0, 2, 0], [0, 0, 1]]
# generator.generate_supercell_structures(supercell_matrix, ...)
```

**Output:**
- Structure files in `01_structure_generation/doped_structures/`
- Metadata file: `structure_metadata.json`

**Expected time:** < 1 minute

**Verify:**
```bash
cd ../01_structure_generation/doped_structures
ls -l *.vasp | wc -l  # Count generated structures
cat structure_metadata.json  # Check metadata
```

---

### Step 2: Batch Submit Calculations

**Objective:** Submit all generated structures for DFT calculations in batch mode.

**Commands:**
```bash
cd scripts
bash 02_batch_submit_jobs.sh
```

**What it does:**
- Loops through all `.vasp` files in `01_structure_generation/doped_structures/`
- Creates individual calculation directories in `02_calculations/`
- Submits each calculation using `mpjob`
- Logs successful and failed submissions

**Default Parameters:**
- Task type: `u_relax` (relaxation with U parameters if needed)
- Partition: `cu`
- Cores: 64
- Mode: `fast`

**Customization:**
Edit the configuration section in `scripts/02_batch_submit_jobs.sh`:

```bash
TASK_TYPE="u_relax"              # Change to: relax, double_relax_static, etc.
PARTITION="cu"                   # Your cluster partition
NCORES=64                        # Cores per calculation
MODE="fast"                      # fast, normal, or native
CUSTOM_PARAMS=""                 # e.g., "ISIF=2,ALGO=ALL"
```

**Monitoring:**
```bash
# Check submission logs
cat ../02_calculations/submitted_jobs.log
cat ../02_calculations/failed_submissions.log

# Monitor job status
bash 02b_monitor_jobs.sh           # Summary
bash 02b_monitor_jobs.sh -v        # Verbose (show all jobs)

# Check cluster queue
squeue -u $USER
```

**Expected time:**
- Submission: ~1-5 minutes for 50-100 structures
- Calculations: 30 minutes - 4 hours per structure (depending on system size and convergence)

**Troubleshooting:**
- If some submissions fail, check `failed_submissions.log`
- You can manually resubmit failed jobs by navigating to the job directory and running `mpjob` command

---

### Step 3: Extract and Analyze Results

**Objective:** Extract lattice parameters, interlayer spacing, energies, and analyze trends.

**Wait for all calculations to complete:**
```bash
cd scripts
bash 02b_monitor_jobs.sh
# Wait until most/all jobs show "COMPLETED"
```

**Extract results:**
```bash
python3 03_extract_results.py
```

**What it does:**
- Scans all calculation directories in `02_calculations/`
- Extracts from completed calculations:
  - Lattice parameters (a, b, c, α, β, γ, volume)
  - Interlayer spacing (average, min, max)
  - Total energy and energy per atom
  - Structure composition
- Merges with metadata (doping type, dopant element, etc.)
- Generates output files in `03_analysis/`

**Output Files:**
1. **`results_summary.csv`** - Spreadsheet-compatible table of all results
2. **`results_complete.json`** - Complete results with all details
3. **`summary_report.txt`** - Human-readable summary with statistics

**Calculate Formation Energies (Optional):**

After obtaining pristine graphite energy, edit `scripts/03_extract_results.py`:

```python
# Line ~290: Uncomment and add pristine energy
PRISTINE_ENERGY_PER_ATOM = -9.XXX  # Replace with actual value from Step 0
analyzer.calculate_formation_energies(PRISTINE_ENERGY_PER_ATOM)
```

**View Results:**
```bash
cd ../03_analysis

# Quick summary
cat summary_report.txt

# Open in spreadsheet
libreoffice results_summary.csv  # or Excel, etc.

# Analyze in Python
python3
>>> import pandas as pd
>>> df = pd.read_csv('results_summary.csv')
>>> df.head()
>>> df[df['doping_type']=='substitutional'].describe()
```

**Expected time:** 1-5 minutes

---

## Quick Start (Full Workflow)

```bash
# Step 0: Relax pristine structure
cd scripts
bash 00_relax_pristine.sh
# WAIT for completion, then:
cd ../00_initial_structure/pristine_relaxation
cp CONTCAR ../CONTCAR

# Step 1: Generate doped structures
cd ../../scripts
python3 01_generate_doped_structures.py

# Step 2: Submit all calculations
bash 02_batch_submit_jobs.sh

# Monitor progress
bash 02b_monitor_jobs.sh

# Step 3: Extract results (after calculations complete)
python3 03_extract_results.py

# View results
cd ../03_analysis
cat summary_report.txt
```

---

## Data Analysis Tips

### Key Properties to Analyze:

1. **Interlayer Spacing:**
   - Compare `avg_interlayer_spacing` across different dopants
   - Identify which dopants expand/contract the interlayer spacing
   - Critical for understanding graphitization effects

2. **Lattice Parameter c:**
   - Direct measure of graphite stacking
   - Should correlate with interlayer spacing

3. **Formation Energy:**
   - Indicates thermodynamic stability
   - Lower formation energy = more favorable doping
   - Compare substitutional vs. interstitial for same dopant

4. **In-plane Lattice Parameters (a, b):**
   - Shows distortion within graphene layers
   - Important for understanding stress/strain

### Example Analysis Workflow:

```python
import pandas as pd
import matplotlib.pyplot as plt

# Load results
df = pd.read_csv('03_analysis/results_summary.csv')

# Filter completed calculations only
df_complete = df[df['status'] == 'completed']

# Compare interlayer spacing by dopant
pivot = df_complete.pivot_table(
    values='avg_interlayer_spacing',
    index='dopant',
    columns='doping_type',
    aggfunc='mean'
)
print(pivot)

# Plot
pivot.plot(kind='bar')
plt.ylabel('Interlayer Spacing (Å)')
plt.title('Effect of Doping on Graphite Interlayer Spacing')
plt.show()

# Identify best dopants for graphitization (larger spacing)
df_complete.sort_values('avg_interlayer_spacing', ascending=False).head(10)
```

---

## Customization Guide

### Adding New Dopant Elements:

Edit `scripts/01_generate_doped_structures.py`:
```python
DOPANT_ELEMENTS = ['B', 'La', 'Mg', 'YOUR_ELEMENT']
```

### Changing Interstitial Positions:

Edit `scripts/01_generate_doped_structures.py`, line ~105:
```python
interstitial_positions = [
    [0.0, 0.0, 0.25],        # Your custom positions
    [0.333, 0.667, 0.75],
]
```

### Generating Supercells (Lower Doping Concentration):

Uncomment lines in `scripts/01_generate_doped_structures.py`:
```python
supercell_matrix = [[2, 0, 0], [0, 2, 0], [0, 0, 1]]  # 2x2x1 supercell
generator.generate_supercell_structures(
    supercell_matrix,
    DOPANT_ELEMENTS,
    doping_type='substitutional'
)
```

### Adjusting Calculation Parameters:

Edit `scripts/02_batch_submit_jobs.sh`:
```bash
TASK_TYPE="u_relax"              # Task type
PARTITION="cu"                   # Cluster partition
NCORES=64                        # Number of cores
MODE="fast"                      # Calculation mode
CUSTOM_PARAMS="ISIF=3,ENCUT=600" # Custom INCAR parameters
```

---

## Troubleshooting

### Problem: mpjob command not found
**Solution:**
```bash
# Check if mpvasp is in PATH
which mpjob
# If not, load the module or add to PATH
module load mpvasp  # or equivalent
```

### Problem: Calculation fails with convergence errors
**Solution:**
- Check OUTCAR for error messages
- Try changing mode from "fast" to "normal"
- Adjust convergence parameters in CUSTOM_PARAMS
```bash
CUSTOM_PARAMS="EDIFF=1E-5,NELM=200"
```

### Problem: Some structures generate errors
**Solution:**
- Check which structures failed: `cat 02_calculations/failed_submissions.log`
- Manually inspect the problematic structure files
- Adjust structure generation parameters or exclude problematic dopants

### Problem: Interlayer spacing extraction gives None
**Solution:**
- Check if structure has distinct layers in z-direction
- For supercells or complex structures, you may need to adjust the layer detection algorithm in `03_extract_results.py`

### Problem: No CONTCAR after pristine relaxation
**Solution:**
- Calculation may still be running (check with `squeue`)
- Calculation may have failed (check OUTCAR for errors)
- May need to adjust convergence parameters

---

## File Formats

### Structure Files (VASP POSCAR format):
```
System Name
1.0                           # Scaling factor
  a_x  a_y  a_z              # Lattice vector a
  b_x  b_y  b_z              # Lattice vector b
  c_x  c_y  c_z              # Lattice vector c
Element1 Element2            # Element names
  n1  n2                     # Number of each element
Direct                       # Coordinate type
  x1  y1  z1                # Fractional coordinates
  ...
```

### Metadata JSON Structure:
```json
{
  "filename": "graphite_sub_B_site0.vasp",
  "doping_type": "substitutional",
  "dopant": "B",
  "site_index": 0,
  "original_species": "C",
  "composition": "C3B1"
}
```

### Results CSV Columns:
- `job_name`: Calculation name
- `status`: completed/failed/running
- `doping_type`: substitutional/interstitial
- `dopant`: Element symbol
- `a, b, c`: Lattice parameters (Å)
- `volume`: Unit cell volume (Ų)
- `avg_interlayer_spacing`: Average interlayer distance (Å)
- `final_energy`: Total energy (eV)
- `energy_per_atom`: Energy per atom (eV/atom)
- `formation_energy_per_atom`: Formation energy (eV/atom)

---

## Best Practices

1. **Always relax pristine structure first** - This ensures all doped structures start from a consistent reference

2. **Keep metadata** - The `structure_metadata.json` file is crucial for linking structures to their properties

3. **Monitor calculations** - Use `02b_monitor_jobs.sh` regularly to check progress

4. **Back up results** - Copy important results before re-running analyses

5. **Document changes** - If you modify scripts, note the changes for reproducibility

6. **Verify convergence** - Always check OUTCAR files for "reached required accuracy"

7. **Use version control** - This directory is a git repository; commit your changes

---

## Performance Optimization

### For faster results:
- Use `MODE="fast"` in batch submission
- Use `TASK_TYPE="relax"` instead of `double_relax_static` for screening
- Reduce `NCORES` if many short calculations (better throughput)

### For higher accuracy:
- Use `MODE="normal"` or `MODE="native"`
- Use `TASK_TYPE="double_relax_static"`
- Add custom parameters: `CUSTOM_PARAMS="ENCUT=600,EDIFF=1E-6"`

### For large-scale studies:
- Generate supercells for realistic doping concentrations
- Parallelize job submission across multiple nodes
- Use `find` and `xargs` for batch operations

---

## References

- **mpvasp Documentation:** [Contact your system administrator]
- **Materials Project:** https://materialsproject.org/
- **pymatgen Documentation:** https://pymatgen.org/
- **VASP Manual:** https://www.vasp.at/wiki/

---

## Support

For issues with:
- **mpvasp/mpjob:** Contact your HPC support team
- **This workflow:** Check error logs in `02_calculations/`
- **VASP convergence:** Consult VASP documentation

---

## Changelog

- **v1.0** (2024-11-24): Initial SOP release
  - Complete workflow from pristine relaxation to results analysis
  - Support for substitutional and interstitial doping
  - Automated structure generation and batch submission
  - Comprehensive result extraction and analysis

---

**Last Updated:** 2024-11-24
**Author:** Automated Workflow System
**Version:** 1.0
