# Quick Start Guide

## Prerequisites
- `mpvasp` installed and available in PATH
- Python 3.x with pymatgen installed
- Access to computing cluster with partition `cu` (or modify scripts for your partition)

## One-Time Setup
```bash
# Make scripts executable
chmod +x scripts/*.sh
chmod +x scripts/*.py
```

## Workflow (Step by Step)

### 1. Relax Pristine Graphite (~1-2 hours)
```bash
cd scripts
./00_relax_pristine.sh
```
**Wait for job to complete**, then:
```bash
cd ../00_initial_structure/pristine_relaxation
grep "reached required accuracy" OUTCAR  # Verify completion
cp CONTCAR ../CONTCAR                    # Save relaxed structure
cd ../../scripts
```

### 2. Generate Doped Structures (~1 minute)
```bash
python3 01_generate_doped_structures.py
```
Check output:
```bash
ls -l ../01_structure_generation/doped_structures/*.vasp
```

### 3. Submit All Calculations (~30 min - 4 hours)
```bash
./02_batch_submit_jobs.sh
```
Monitor progress:
```bash
./02b_monitor_jobs.sh        # Check status
./02b_monitor_jobs.sh -v     # Detailed status
```

### 4. Extract Results (~1 minute)
Wait until most jobs are completed, then:
```bash
python3 03_extract_results.py
```

### 5. View Results
```bash
cd ../03_analysis
cat summary_report.txt
less results_summary.csv
```

### 6. (Optional) Advanced Analysis
```bash
cd ../scripts
python3 04_example_analysis.py
```
View generated plots in `../03_analysis/plots/`

### 7. (Optional) Export & Database Upload
```bash
# Export to MongoDB-compatible JSON
python3 05_export_to_json.py

# Upload to MongoDB (configure connection first)
python3 06_upload_to_mongodb.py
```

## Typical Timeline
- **Day 1 Morning:** Run pristine relaxation (Step 1)
- **Day 1 Afternoon:** Generate structures & submit calculations (Steps 2-3)
- **Day 2:** Monitor progress, extract results when complete (Steps 4-5)

## Key Files
- **Input:** `00_initial_structure/graphite_pristine.vasp`
- **Reference:** `00_initial_structure/CONTCAR` (relaxed structure)
- **Structures:** `01_structure_generation/doped_structures/*.vasp`
- **Results:** `03_analysis/results_summary.csv`
- **Complete Data:** `03_analysis/results_complete.json`
- **Database Export:** `03_analysis/results_database.json`
- **Plots:** `03_analysis/plots/*.png` (if matplotlib available)

## Common Commands

### Monitor jobs
```bash
cd scripts
./02b_monitor_jobs.sh
```

### Check specific calculation
```bash
cd ../02_calculations/graphite_sub_B_site0
tail OUTCAR
grep "reached required accuracy" OUTCAR
```

### Resubmit failed job
```bash
cd ../02_calculations/failed_job_name
mpjob *.vasp -t u_relax -p cu -n 64
```

## Customization

### Change dopant elements
Edit `scripts/01_generate_doped_structures.py`, line ~213:
```python
DOPANT_ELEMENTS = ['B', 'La', 'Mg', 'YOUR_ELEMENT']
```

### Change calculation parameters
Edit `scripts/02_batch_submit_jobs.sh`:
```bash
TASK_TYPE="u_relax"     # or double_relax_static, relax_static, etc.
NCORES=64               # adjust based on your cluster
PARTITION="cu"          # your cluster partition
```

## Advanced Features

### Generate Analysis Plots
```bash
cd scripts
python3 04_example_analysis.py
```
Generates:
- Interlayer spacing comparison plots
- Formation energy rankings
- Lattice parameter distributions
- Correlation analyses

### Export to Database
```bash
# Step 1: Export to JSON
python3 05_export_to_json.py

# Step 2: Configure MongoDB connection in 06_upload_to_mongodb.py
# Edit MONGO_URI, DATABASE_NAME, COLLECTION_NAME

# Step 3: Upload
python3 06_upload_to_mongodb.py
```

## Troubleshooting

**mpjob not found:**
```bash
which mpjob
module load mpvasp  # if using modules
```

**Import error for pymatgen:**
```bash
pip install pymatgen
# or
conda install -c conda-forge pymatgen
```

**Job keeps failing:**
- Check OUTCAR for errors
- Try MODE="normal" instead of "fast"
- Increase NELM or adjust other INCAR parameters

## Need Help?
See full documentation: `SOP_HIGH_THROUGHPUT_GRAPHITE_DOPING.md`
