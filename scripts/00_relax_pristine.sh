#!/bin/bash
################################################################################
# Initial Pristine Graphite Relaxation
# This should be run first to get the relaxed unit cell structure
################################################################################

STRUCTURE_FILE="../00_initial_structure/graphite_pristine.vasp"
OUTPUT_DIR="../00_initial_structure/pristine_relaxation"

# mpjob parameters
TASK_TYPE="u_double_relax_static"  # Double relax for accurate structure
PARTITION="cu"
NCORES=64
MODE="normal"  # Use normal mode for better accuracy

echo "============================================================================"
echo "Pristine Graphite Unit Cell Relaxation"
echo "============================================================================"
echo "This calculation will relax the pristine graphite structure."
echo "The resulting CONTCAR will be used as the base structure for doping."
echo "============================================================================"
echo ""

# Check if structure file exists
if [ ! -f "$STRUCTURE_FILE" ]; then
    echo "Error: Structure file not found: $STRUCTURE_FILE"
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Copy structure to output directory
cp "$STRUCTURE_FILE" "$OUTPUT_DIR/"

# Navigate to output directory
cd "$OUTPUT_DIR" || exit

# Submit calculation
echo "Submitting pristine graphite relaxation..."
echo "Command: mpjob $(basename $STRUCTURE_FILE) -t $TASK_TYPE -p $PARTITION -n $NCORES -m $MODE --name pristine_graphite"
mpjob "$(basename $STRUCTURE_FILE)" -t "$TASK_TYPE" -p "$PARTITION" -n "$NCORES" -m "$MODE" --name pristine_graphite

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Job submitted successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Wait for the calculation to complete"
    echo "2. Check the results: cd $OUTPUT_DIR"
    echo "3. Copy CONTCAR to: cp CONTCAR ../CONTCAR"
    echo "4. Proceed with structure generation: cd ../../scripts && python3 01_generate_doped_structures.py"
else
    echo ""
    echo "✗ Job submission failed!"
    exit 1
fi

cd - > /dev/null || exit
