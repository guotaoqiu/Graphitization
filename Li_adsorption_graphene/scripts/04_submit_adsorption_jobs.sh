#!/bin/bash
################################################################################
# Script to batch submit Li adsorption calculation jobs
# Uses mpjob with specific VASP parameters for 2D materials
################################################################################

# VASP calculation parameters
MODE="native"              # Calculation mode
TASK_TYPE="u_relax"        # Task type: relaxation
PARTITION="cu"             # Cluster partition
NCORES=64                  # Number of cores per job
# VASP parameters for 2D materials with vdW correction
CUSTOM_PARAMS="ISIF=2,LDIPOL=.TRUE.,IDIPOL=3,IVDW=11"

# Directories
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
STRUCTURE_DIR="$SCRIPT_DIR/../02_adsorption_structures"
CALC_DIR="$SCRIPT_DIR/../03_calculations/adsorption"

# Create calculation directory
mkdir -p "$CALC_DIR"

echo "================================================================================"
echo "Batch Submission of Li Adsorption Calculation Jobs"
echo "================================================================================"
echo "Structure directory: $STRUCTURE_DIR"
echo "Calculation directory: $CALC_DIR"
echo "Mode: $MODE"
echo "Task type: $TASK_TYPE"
echo "Partition: $PARTITION"
echo "Cores per job: $NCORES"
echo "Custom VASP parameters: $CUSTOM_PARAMS"
echo "================================================================================"
echo ""

# Change to calculation directory
cd "$CALC_DIR" || exit 1

# Counter for submitted jobs
submitted=0
skipped=0

# Find all adsorption structure files
echo "Searching for adsorption structures..."
echo ""

for structure_file in "$STRUCTURE_DIR"/graphene_*_Li_*.vasp; do
    if [ ! -f "$structure_file" ]; then
        echo "No adsorption structure files found in $STRUCTURE_DIR"
        break
    fi

    # Extract structure name from filename
    filename=$(basename "$structure_file")
    structure_name="${filename%.vasp}"

    echo "Processing: $structure_name"

    # Check if job already exists and completed
    job_dir="$CALC_DIR/$structure_name"
    if [ -d "$job_dir" ]; then
        if [ -f "$job_dir/OUTCAR" ]; then
            if grep -q "reached required accuracy" "$job_dir/OUTCAR" 2>/dev/null; then
                echo "  ✓ Already completed - skipping"
                ((skipped++))
                echo ""
                continue
            fi
        fi
    fi

    # Submit job using mpjob
    echo "  Submitting job..."
    mpjob "$structure_file" \
        -m "$MODE" \
        -t "$TASK_TYPE" \
        -p "$PARTITION" \
        -n "$NCORES" \
        -c "$CUSTOM_PARAMS"

    if [ $? -eq 0 ]; then
        echo "  ✓ Job submitted successfully"
        ((submitted++))
    else
        echo "  ✗ Job submission failed"
    fi

    echo ""

    # Small delay to avoid overwhelming the queue system
    sleep 1
done

echo "================================================================================"
echo "Submission Summary"
echo "================================================================================"
echo "Jobs submitted: $submitted"
echo "Jobs skipped (already completed): $skipped"
echo "================================================================================"
echo ""
echo "Next steps:"
echo "  1. Monitor job status: squeue -u \$USER"
echo "  2. After jobs complete, analyze results: python3 05_analyze_results.py"
echo "================================================================================"
