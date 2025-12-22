#!/bin/bash
################################################################################
# Script to relax the pristine graphene structure
# This should be run first to get the reference pristine energy
################################################################################

# VASP calculation parameters
MODE="native"
TASK_TYPE="u_relax"
PARTITION="cu"
NCORES=64
CUSTOM_PARAMS="ISIF=2,LDIPOL=.TRUE.,IDIPOL=3,IVDW=11"

# Directories
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
STRUCTURE_FILE="$SCRIPT_DIR/../00_initial_structure/POSCAR_REV.vasp"
CALC_DIR="$SCRIPT_DIR/../03_calculations/pristine_relaxation"

echo "================================================================================"
echo "Pristine Graphene Relaxation"
echo "================================================================================"
echo "Structure file: $STRUCTURE_FILE"
echo "Calculation directory: $CALC_DIR"
echo "Mode: $MODE"
echo "Task type: $TASK_TYPE"
echo "Partition: $PARTITION"
echo "Cores: $NCORES"
echo "Custom VASP parameters: $CUSTOM_PARAMS"
echo "================================================================================"
echo ""

# Check if structure file exists
if [ ! -f "$STRUCTURE_FILE" ]; then
    echo "✗ Error: Structure file not found: $STRUCTURE_FILE"
    exit 1
fi

# Create calculation directory
mkdir -p "$CALC_DIR"
cd "$CALC_DIR" || exit 1

# Check if already completed
if [ -f "OUTCAR" ]; then
    if grep -q "reached required accuracy" OUTCAR 2>/dev/null; then
        echo "✓ Pristine relaxation already completed"
        echo ""
        echo "Energy information:"
        grep "energy  without entropy" OUTCAR | tail -1
        echo ""
        echo "Next steps:"
        echo "  1. Generate doped structures: python3 ../scripts/01_generate_doped_graphene.py"
        exit 0
    fi
fi

# Submit job
echo "Submitting pristine graphene relaxation job..."
mpjob "$STRUCTURE_FILE" \
    -m "$MODE" \
    -t "$TASK_TYPE" \
    -p "$PARTITION" \
    -n "$NCORES" \
    -c "$CUSTOM_PARAMS"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Job submitted successfully"
    echo ""
    echo "Monitor job status:"
    echo "  squeue -u \$USER"
    echo ""
    echo "Check progress:"
    echo "  cd $CALC_DIR"
    echo "  tail -f OUTCAR"
    echo ""
    echo "After completion:"
    echo "  Copy relaxed structure: cp CONTCAR ../00_initial_structure/"
    echo "  Or continue with unrelaxed: python3 01_generate_doped_graphene.py"
else
    echo ""
    echo "✗ Job submission failed"
    exit 1
fi
