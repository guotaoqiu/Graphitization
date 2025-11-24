#!/bin/bash
################################################################################
# Job Monitoring Script
# Checks the status of all submitted calculation jobs
################################################################################

CALC_DIR="../02_calculations"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "============================================================================"
echo "Job Status Monitor"
echo "============================================================================"
echo ""

if [ ! -d "$CALC_DIR" ]; then
    echo -e "${RED}Error: Calculation directory not found: $CALC_DIR${NC}"
    exit 1
fi

# Counters
total_jobs=0
completed_jobs=0
running_jobs=0
failed_jobs=0
pending_jobs=0

# Loop through all job directories
for job_dir in "$CALC_DIR"/*/; do
    if [ -d "$job_dir" ]; then
        total_jobs=$((total_jobs + 1))
        job_name=$(basename "$job_dir")

        # Check for completion markers
        if [ -f "$job_dir/CONTCAR" ] && [ -f "$job_dir/OUTCAR" ]; then
            # Check if calculation completed successfully
            if grep -q "reached required accuracy" "$job_dir/OUTCAR" 2>/dev/null; then
                completed_jobs=$((completed_jobs + 1))
                status="${GREEN}COMPLETED${NC}"
            elif grep -q "ZBRENT: fatal error" "$job_dir/OUTCAR" 2>/dev/null || \
                 grep -q "ERROR" "$job_dir/OUTCAR" 2>/dev/null; then
                failed_jobs=$((failed_jobs + 1))
                status="${RED}FAILED${NC}"
            else
                running_jobs=$((running_jobs + 1))
                status="${YELLOW}RUNNING${NC}"
            fi
        elif [ -f "$job_dir/INCAR" ]; then
            # INCAR exists but no OUTCAR yet
            running_jobs=$((running_jobs + 1))
            status="${YELLOW}RUNNING${NC}"
        else
            # Job not started
            pending_jobs=$((pending_jobs + 1))
            status="${BLUE}PENDING${NC}"
        fi

        # Only print if verbose flag is set
        if [ "$1" == "-v" ] || [ "$1" == "--verbose" ]; then
            echo -e "$job_name: $status"
        fi
    fi
done

echo ""
echo "============================================================================"
echo "Summary"
echo "============================================================================"
echo -e "Total jobs:      ${total_jobs}"
echo -e "Completed:       ${GREEN}${completed_jobs}${NC}"
echo -e "Running:         ${YELLOW}${running_jobs}${NC}"
echo -e "Failed:          ${RED}${failed_jobs}${NC}"
echo -e "Pending:         ${BLUE}${pending_jobs}${NC}"
echo "============================================================================"
echo ""

if [ "$1" != "-v" ] && [ "$1" != "--verbose" ]; then
    echo "Use -v or --verbose flag to see detailed job status"
fi

# Calculate and display progress
if [ $total_jobs -gt 0 ]; then
    progress=$((completed_jobs * 100 / total_jobs))
    echo "Progress: ${progress}%"
fi
