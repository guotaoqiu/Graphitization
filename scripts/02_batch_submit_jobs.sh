#!/bin/bash
################################################################################
# Batch Job Submission Script for High-Throughput Doped Graphite Calculations
################################################################################

# Configuration
STRUCTURE_DIR="../01_structure_generation/doped_structures"
CALC_DIR="../02_calculations"
TASK_TYPE="u_relax"          # Task type: u_relax, double_relax_static, etc.
PARTITION="cu"                # Cluster partition
NCORES=64                     # Number of cores per job
MODE="fast"                   # Calculation mode: fast, normal, native

# MPJOB custom parameters (optional)
CUSTOM_PARAMS=""              # e.g., "ISIF=2,ALGO=ALL"

# Create calculation directory
mkdir -p "$CALC_DIR"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

################################################################################
# Function to submit a single structure
################################################################################
submit_structure() {
    local structure_file=$1
    local structure_basename=$(basename "$structure_file" .vasp)

    echo -e "${YELLOW}Processing: ${structure_basename}${NC}"

    # Create job directory
    local job_dir="${CALC_DIR}/${structure_basename}"
    mkdir -p "$job_dir"

    # Copy structure to job directory
    cp "$structure_file" "$job_dir/"

    # Navigate to job directory
    cd "$job_dir" || exit

    # Construct mpjob command
    local mpjob_cmd="mpjob $(basename $structure_file) -t $TASK_TYPE -p $PARTITION -n $NCORES -m $MODE"

    # Add custom parameters if specified
    if [ -n "$CUSTOM_PARAMS" ]; then
        mpjob_cmd="$mpjob_cmd -c $CUSTOM_PARAMS"
    fi

    # Add job name
    mpjob_cmd="$mpjob_cmd --name $structure_basename"

    # Submit job
    echo "Running: $mpjob_cmd"
    eval $mpjob_cmd

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Successfully submitted: ${structure_basename}${NC}"
        echo "$structure_basename" >> "${CALC_DIR}/submitted_jobs.log"
    else
        echo -e "${RED}✗ Failed to submit: ${structure_basename}${NC}"
        echo "$structure_basename" >> "${CALC_DIR}/failed_submissions.log"
    fi

    echo "----------------------------------------"

    # Return to original directory
    cd - > /dev/null || exit
}

################################################################################
# Main Execution
################################################################################

echo "============================================================================"
echo "Batch Job Submission for Doped Graphite Calculations"
echo "============================================================================"
echo "Structure directory: $STRUCTURE_DIR"
echo "Calculation directory: $CALC_DIR"
echo "Task type: $TASK_TYPE"
echo "Partition: $PARTITION"
echo "Cores per job: $NCORES"
echo "Mode: $MODE"
echo "============================================================================"
echo ""

# Check if structure directory exists
if [ ! -d "$STRUCTURE_DIR" ]; then
    echo -e "${RED}Error: Structure directory not found: $STRUCTURE_DIR${NC}"
    exit 1
fi

# Count total structures
total_structures=$(find "$STRUCTURE_DIR" -name "*.vasp" | wc -l)
echo "Found $total_structures structure files to process"
echo ""

# Initialize log files
> "${CALC_DIR}/submitted_jobs.log"
> "${CALC_DIR}/failed_submissions.log"

# Loop through all VASP structure files
counter=0
for structure_file in "$STRUCTURE_DIR"/*.vasp; do
    if [ -f "$structure_file" ]; then
        counter=$((counter + 1))
        echo "[$counter/$total_structures]"
        submit_structure "$structure_file"
    fi
done

echo ""
echo "============================================================================"
echo "Submission Summary"
echo "============================================================================"
submitted_count=$(wc -l < "${CALC_DIR}/submitted_jobs.log" 2>/dev/null || echo "0")
failed_count=$(wc -l < "${CALC_DIR}/failed_submissions.log" 2>/dev/null || echo "0")
echo -e "Successfully submitted: ${GREEN}${submitted_count}${NC}"
echo -e "Failed submissions: ${RED}${failed_count}${NC}"
echo "============================================================================"
echo ""
echo "Check logs:"
echo "  - Submitted: ${CALC_DIR}/submitted_jobs.log"
echo "  - Failed: ${CALC_DIR}/failed_submissions.log"
echo ""
