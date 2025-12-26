#!/bin/bash
################################################################################
# Resubmit Running/Failed/Pending Jobs Script
# Compresses failed calculations and restarts fresh with conservative params
################################################################################

CALC_DIR="../02_calculations"
TASK_TYPE="u_relax"          # Task type: u_relax, double_relax_static, etc.
PARTITION="cu"                # Cluster partition
NCORES=64                     # Number of cores per job
MODE="native"                 # Calculation mode: fast, normal, native

# Custom INCAR parameters - more conservative settings
CUSTOM_PARAMS="POTIM=0.02,ADDGRID=.T."

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "============================================================================"
echo "Resubmit Running/Failed/Pending Jobs (Fresh Restart)"
echo "============================================================================"
echo "This script will:"
echo "  • Compress failed calculations to *.tar.gz"
echo "  • Restart calculations fresh with: $CUSTOM_PARAMS"
echo "  • Target: RUNNING, FAILED, and PENDING jobs only"
echo "  • Skip: COMPLETED jobs"
echo "============================================================================"
echo ""

if [ ! -d "$CALC_DIR" ]; then
    echo -e "${RED}Error: Calculation directory not found: $CALC_DIR${NC}"
    exit 1
fi

# Counters
total_jobs=0
running_resubmitted=0
failed_resubmitted=0
pending_submitted=0
skipped_jobs=0
failed_resubmits=0

################################################################################
# Function to compress and restart a job
################################################################################
restart_job() {
    local calc_dir=$1
    local structure_name=$2
    local job_name=$3
    local status=$4

    echo -e "${YELLOW}Restarting ${status} job: ${job_name}${NC}"

    # Remove trailing slash from calc_dir
    local calc_dir_clean="${calc_dir%/}"

    # Get the parent structure directory (e.g., graphite_int_La_in_ring_6x6x1)
    local structure_dir=$(dirname "$calc_dir_clean")
    if [ "$(basename "$structure_dir")" == "$structure_name" ]; then
        structure_dir=$(dirname "$structure_dir")
    fi

    # Find the original structure file
    local structure_file=$(find "$structure_dir" -maxdepth 1 -name "*.vasp" | head -1)
    if [ -z "$structure_file" ]; then
        # Try to find in calc_dir
        structure_file=$(find "$calc_dir_clean" -maxdepth 1 -name "*.vasp" | head -1)
        if [ -z "$structure_file" ]; then
            echo -e "  ${RED}✗ No structure file found${NC}"
            echo "----------------------------------------"
            return 1
        fi
    fi

    # Compress existing calculation directory if it exists and is not pending
    if [ "$status" != "PENDING" ] && [ -d "$calc_dir_clean" ]; then
        local tar_file="${calc_dir_clean}.tar.gz"

        # If tar file already exists, append timestamp
        if [ -f "$tar_file" ]; then
            local timestamp=$(date +%Y%m%d_%H%M%S)
            tar_file="${calc_dir_clean}_${timestamp}.tar.gz"
        fi

        echo "  Compressing to: $(basename "$tar_file")"
        tar -czf "$tar_file" -C "$(dirname "$calc_dir_clean")" "$(basename "$calc_dir_clean")" 2>/dev/null

        if [ $? -eq 0 ]; then
            echo -e "  ${GREEN}✓ Compressed successfully${NC}"
            # Remove the original directory after successful compression
            rm -rf "$calc_dir_clean"
            echo -e "  ${GREEN}✓ Removed original directory${NC}"
        else
            echo -e "  ${RED}✗ Compression failed${NC}"
            echo "----------------------------------------"
            return 1
        fi
    fi

    # Navigate to structure directory for fresh submission
    local submit_dir="$structure_dir"
    cd "$submit_dir" || {
        echo -e "  ${RED}✗ Cannot navigate to structure directory${NC}"
        echo "----------------------------------------"
        return 1
    }

    # Construct mpjob command (same as batch script - fresh submission)
    local structure_basename=$(basename "$structure_file")
    local mpjob_cmd="mpjob \"$structure_basename\" -t $TASK_TYPE -p $PARTITION -n $NCORES -m $MODE"

    # Add custom parameters
    if [ -n "$CUSTOM_PARAMS" ]; then
        mpjob_cmd="$mpjob_cmd -c $CUSTOM_PARAMS"
    fi

    # Add job name
    mpjob_cmd="$mpjob_cmd --name $structure_name"

    # Submit job
    echo "  Running: $mpjob_cmd"
    eval $mpjob_cmd
    local submit_status=$?

    # Return to original directory
    cd - > /dev/null

    if [ $submit_status -eq 0 ]; then
        echo -e "  ${GREEN}✓ Successfully resubmitted${NC}"
        case "$status" in
            RUNNING)
                running_resubmitted=$((running_resubmitted + 1))
                ;;
            FAILED)
                failed_resubmitted=$((failed_resubmitted + 1))
                ;;
            PENDING)
                pending_submitted=$((pending_submitted + 1))
                ;;
        esac
    else
        echo -e "  ${RED}✗ Failed to resubmit (exit code: $submit_status)${NC}"
        failed_resubmits=$((failed_resubmits + 1))
    fi

    echo "----------------------------------------"
}

################################################################################
# Main loop through all job directories
################################################################################

# Loop through all job directories
for structure_dir in "$CALC_DIR"/*/; do
    if [ -d "$structure_dir" ]; then
        structure_name=$(basename "$structure_dir")

        # Find calculation directories (may be nested)
        calc_dirs=()

        # Pattern 1: structure_name/structure_name/calc_type/
        if [ -d "$structure_dir/$structure_name" ]; then
            for calc_type_dir in "$structure_dir/$structure_name"/*/; do
                if [ -d "$calc_type_dir" ]; then
                    calc_dirs+=("$calc_type_dir")
                fi
            done
        fi

        # Pattern 2: structure_name/calc_type/ (fallback)
        if [ ${#calc_dirs[@]} -eq 0 ]; then
            for calc_type_dir in "$structure_dir"/*/; do
                if [ -d "$calc_type_dir" ] && [ "$(basename "$calc_type_dir")" != "$structure_name" ]; then
                    calc_dirs+=("$calc_type_dir")
                fi
            done
        fi

        # If no nested calculation directories found, check the structure directory itself
        if [ ${#calc_dirs[@]} -eq 0 ]; then
            calc_dirs+=("$structure_dir")
        fi

        # Check each calculation directory
        for calc_dir in "${calc_dirs[@]}"; do
            total_jobs=$((total_jobs + 1))
            job_name="$structure_name/$(basename "$calc_dir")"

            # Determine job status (same logic as monitor script)
            status=""
            if [ -f "$calc_dir/CONTCAR" ] && [ -f "$calc_dir/OUTCAR" ]; then
                # Check if calculation completed successfully
                if grep -q "reached required accuracy" "$calc_dir/OUTCAR" 2>/dev/null; then
                    status="COMPLETED"
                elif grep -q "ZBRENT: fatal error" "$calc_dir/OUTCAR" 2>/dev/null || \
                     grep -q "ERROR" "$calc_dir/OUTCAR" 2>/dev/null; then
                    status="FAILED"
                else
                    status="RUNNING"
                fi
            elif [ -f "$calc_dir/INCAR" ]; then
                # INCAR exists but no OUTCAR yet
                status="RUNNING"
            else
                # Job not started
                status="PENDING"
            fi

            # Process based on status - only restart RUNNING, FAILED, and PENDING
            case "$status" in
                RUNNING|FAILED|PENDING)
                    restart_job "$calc_dir" "$structure_name" "$job_name" "$status"
                    ;;
                COMPLETED)
                    skipped_jobs=$((skipped_jobs + 1))
                    echo -e "${GREEN}✓ Skipping completed job: ${job_name}${NC}"
                    ;;
                *)
                    skipped_jobs=$((skipped_jobs + 1))
                    ;;
            esac
        done
    fi
done

echo ""
echo "============================================================================"
echo "Resubmission Summary"
echo "============================================================================"
echo -e "Total jobs scanned:           ${total_jobs}"
echo -e "Running jobs restarted:       ${YELLOW}${running_resubmitted}${NC}"
echo -e "Failed jobs restarted:        ${RED}${failed_resubmitted}${NC}"
echo -e "Pending jobs submitted:       ${BLUE}${pending_submitted}${NC}"
echo -e "Skipped (already completed):  ${GREEN}${skipped_jobs}${NC}"
if [ $failed_resubmits -gt 0 ]; then
    echo -e "Failed to resubmit:           ${RED}${failed_resubmits}${NC}"
    echo -e "  ⚠ Check mpjob errors above for details"
fi
echo "============================================================================"
echo ""
echo "Custom parameters used: $CUSTOM_PARAMS"
echo "Failed calculations compressed to: *.tar.gz"
echo ""
