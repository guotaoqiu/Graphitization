#!/bin/bash
################################################################################
# Continue Job Submission Script
# Resubmits RUNNING jobs (with CONTCAR->POSCAR) and submits PENDING jobs
# Handles wall time limits and incomplete calculations intelligently
################################################################################

CALC_DIR="../02_calculations"
TASK_TYPE="u_relax"          # Task type: u_relax, double_relax_static, etc.
PARTITION="cu"                # Cluster partition
NCORES=64                     # Number of cores per job
MODE="fast"                   # Calculation mode: fast, normal, native

# MPJOB custom parameters (optional)
CUSTOM_PARAMS=""              # e.g., "ISIF=2,ALGO=ALL"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "============================================================================"
echo "Continue Job Submission (INCOMPLETE + RUNNING + PENDING)"
echo "============================================================================"
echo "Smart resubmission features:"
echo "  • Progressive recovery: POTIM=0.2 → ALGO=Veryfast (for all incomplete)"
echo "  • Auto-detects Th/U elements and sets magmoms for pending jobs"
echo "  • Skips completed jobs"
echo "  • All incomplete/running/failed jobs treated as failures needing recovery"
echo "============================================================================"
echo ""

if [ ! -d "$CALC_DIR" ]; then
    echo -e "${RED}Error: Calculation directory not found: $CALC_DIR${NC}"
    exit 1
fi

# Counters
total_jobs=0
running_resubmitted=0
pending_submitted=0
skipped_jobs=0
failed_resubmits=0

################################################################################
# Recovery tracking functions
################################################################################

# Check recovery stage based on marker files
get_recovery_stage() {
    local calc_dir=$1

    if [ -f "$calc_dir/.recovery_algo" ]; then
        echo "algo_tried"
    elif [ -f "$calc_dir/.recovery_potim" ]; then
        echo "potim_tried"
    else
        echo "none"
    fi
}

# Check if structure contains Th or U elements and return magmom settings
check_special_elements() {
    local structure_file=$1
    local magmom_params=""

    if [ ! -f "$structure_file" ]; then
        echo ""
        return
    fi

    # Check for Th (Thorium) or U (Uranium) in the structure file
    if grep -q "Th" "$structure_file" || grep -q "U" "$structure_file"; then
        # Set appropriate magmoms for actinides
        # Th: typically non-magnetic (0)
        # U: typically magnetic (2-3 μB)
        if grep -q "Th" "$structure_file" && grep -q "U" "$structure_file"; then
            magmom_params="MAGMOM={Th:0,U:2.5}"
        elif grep -q "Th" "$structure_file"; then
            magmom_params="MAGMOM={Th:0}"
        elif grep -q "U" "$structure_file"; then
            magmom_params="MAGMOM={U:2.5}"
        fi
    fi

    echo "$magmom_params"
}

################################################################################
# Function to resubmit a running/incomplete job using mpjob -j
################################################################################
resubmit_running_job() {
    local calc_dir=$1
    local structure_name=$2
    local job_name=$3
    local status=$4

    echo -e "${YELLOW}Resubmitting ${status} job: ${job_name}${NC}"

    # All incomplete/running/failed jobs are treated as failures requiring recovery
    # No wall-time limits for small systems - all need progressive recovery
    local recovery_params=""
    local recovery_stage=$(get_recovery_stage "$calc_dir")
    echo "  Recovery stage: $recovery_stage"

    case "$recovery_stage" in
        none)
            # First recovery attempt: Add POTIM = 0.2
            echo -e "  ${CYAN}→ Applying recovery strategy 1: POTIM=0.2${NC}"
            recovery_params="POTIM=0.2"
            touch "$calc_dir/.recovery_potim"
            echo "  ✓ Created recovery marker: .recovery_potim"
            ;;
        potim_tried)
            # Second recovery attempt: Change ALGO to Veryfast (keep POTIM)
            echo -e "  ${CYAN}→ Applying recovery strategy 2: POTIM=0.2,ALGO=Veryfast${NC}"
            recovery_params="POTIM=0.2,ALGO=Veryfast"
            touch "$calc_dir/.recovery_algo"
            echo "  ✓ Created recovery marker: .recovery_algo"
            ;;
        algo_tried)
            # Both recovery strategies tried, continue using both parameters
            echo -e "  ${CYAN}→ Both recovery strategies already tried, using POTIM=0.2,ALGO=Veryfast${NC}"
            recovery_params="POTIM=0.2,ALGO=Veryfast"
            ;;
    esac

    # Find the original structure file in the parent structure directory
    local structure_dir=$(dirname "$calc_dir")
    # Go up one more level if in nested structure (structure_name/structure_name/calc_type/)
    if [ "$(basename "$structure_dir")" == "$structure_name" ]; then
        structure_dir=$(dirname "$structure_dir")
    fi

    local structure_file=$(find "$structure_dir" -maxdepth 1 -name "*.vasp" | head -1)

    if [ -z "$structure_file" ]; then
        # Try to use POSCAR from calc_dir
        if [ -f "$calc_dir/POSCAR" ]; then
            structure_file="$calc_dir/POSCAR"
        else
            echo -e "  ${RED}✗ No structure file found${NC}"
            echo "----------------------------------------"
            return 1
        fi
    fi

    # Build mpjob command using -j to continue from previous calculation
    local mpjob_cmd="mpjob \"$structure_file\" -j \"$calc_dir\" -t $TASK_TYPE -p $PARTITION -n $NCORES -m $MODE"

    # Combine custom parameters and recovery parameters
    local combined_params=""
    if [ -n "$recovery_params" ] && [ -n "$CUSTOM_PARAMS" ]; then
        combined_params="${recovery_params},${CUSTOM_PARAMS}"
    elif [ -n "$recovery_params" ]; then
        combined_params="$recovery_params"
    elif [ -n "$CUSTOM_PARAMS" ]; then
        combined_params="$CUSTOM_PARAMS"
    fi

    # Add combined custom parameters if any
    if [ -n "$combined_params" ]; then
        mpjob_cmd="$mpjob_cmd -c $combined_params"
    fi

    # Add job name
    mpjob_cmd="$mpjob_cmd --name $structure_name"

    # Submit job
    echo "  Running: $mpjob_cmd"
    eval $mpjob_cmd
    local submit_status=$?

    if [ $submit_status -eq 0 ]; then
        echo -e "  ${GREEN}✓ Successfully resubmitted${NC}"
        running_resubmitted=$((running_resubmitted + 1))
    else
        echo -e "  ${RED}✗ Failed to resubmit (exit code: $submit_status)${NC}"
        failed_resubmits=$((failed_resubmits + 1))
    fi

    echo "----------------------------------------"
}

################################################################################
# Function to submit a pending job
################################################################################
submit_pending_job() {
    local calc_dir=$1
    local structure_name=$2
    local job_name=$3

    echo -e "${BLUE}Submitting PENDING job: ${job_name}${NC}"

    # Find the original structure file in the parent structure directory
    local structure_dir=$(dirname "$calc_dir")
    # Go up one more level if in nested structure (structure_name/structure_name/calc_type/)
    if [ "$(basename "$structure_dir")" == "$structure_name" ]; then
        structure_dir=$(dirname "$structure_dir")
    fi

    local structure_file=$(find "$structure_dir" -maxdepth 1 -name "*.vasp" | head -1)

    if [ -z "$structure_file" ]; then
        # Try to find .vasp file in calc_dir
        structure_file=$(find "$calc_dir" -maxdepth 1 -name "*.vasp" | head -1)
        if [ -z "$structure_file" ]; then
            echo -e "  ${RED}✗ No structure file found${NC}"
            echo "----------------------------------------"
            return 1
        fi
    fi

    # Check for special elements (Th, U) that need magmom settings
    local special_params=$(check_special_elements "$structure_file")
    if [ -n "$special_params" ]; then
        echo "  ✓ Detected special elements, adding: $special_params"
    fi

    # Construct mpjob command with explicit output directory
    local mpjob_cmd="mpjob \"$structure_file\" -o \"$calc_dir\" -t $TASK_TYPE -p $PARTITION -n $NCORES -m $MODE"

    # Combine custom parameters and special element parameters
    local combined_params=""
    if [ -n "$special_params" ] && [ -n "$CUSTOM_PARAMS" ]; then
        combined_params="${special_params},${CUSTOM_PARAMS}"
    elif [ -n "$special_params" ]; then
        combined_params="$special_params"
    elif [ -n "$CUSTOM_PARAMS" ]; then
        combined_params="$CUSTOM_PARAMS"
    fi

    # Add combined custom parameters if any
    if [ -n "$combined_params" ]; then
        mpjob_cmd="$mpjob_cmd -c $combined_params"
    fi

    # Add job name
    mpjob_cmd="$mpjob_cmd --name $structure_name"

    # Submit job
    echo "  Running: $mpjob_cmd"
    eval $mpjob_cmd
    local submit_status=$?

    if [ $submit_status -eq 0 ]; then
        echo -e "  ${GREEN}✓ Successfully submitted${NC}"
        pending_submitted=$((pending_submitted + 1))
    else
        echo -e "  ${RED}✗ Failed to submit (exit code: $submit_status)${NC}"
        failed_resubmits=$((failed_resubmits + 1))
    fi

    echo "----------------------------------------"
}

################################################################################
# Main loop through all job directories
################################################################################

# Loop through all job directories
# mpjob creates nested structure: structure_name/structure_name/calc_type/
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

            # Determine job status with better detection
            status=""
            if [ -f "$calc_dir/OUTCAR" ]; then
                # Check if calculation completed successfully
                if grep -q "reached required accuracy" "$calc_dir/OUTCAR" 2>/dev/null; then
                    status="COMPLETED"
                # Check for fatal errors
                elif grep -q "ZBRENT: fatal error" "$calc_dir/OUTCAR" 2>/dev/null || \
                     grep -q "ERROR" "$calc_dir/OUTCAR" 2>/dev/null; then
                    status="FAILED"
                # Check if hit wall time (incomplete but has OUTCAR)
                elif check_wall_time "$calc_dir/OUTCAR"; then
                    status="INCOMPLETE"
                # Has OUTCAR but not completed - might be still running or incomplete
                else
                    # Check if CONTCAR exists and is valid
                    if [ -f "$calc_dir/CONTCAR" ]; then
                        local line_count=$(wc -l < "$calc_dir/CONTCAR" 2>/dev/null || echo 0)
                        if [ "$line_count" -ge 8 ]; then
                            # Has valid CONTCAR but not completed - likely incomplete
                            status="INCOMPLETE"
                        else
                            status="RUNNING"
                        fi
                    else
                        status="RUNNING"
                    fi
                fi
            elif [ -f "$calc_dir/INCAR" ]; then
                # INCAR exists but no OUTCAR yet - could be pending or just started
                if [ -f "$calc_dir/POSCAR" ] || [ -f "$calc_dir"/*.vasp ]; then
                    status="RUNNING"
                else
                    status="PENDING"
                fi
            else
                # Job not started
                status="PENDING"
            fi

            # Process based on status
            case "$status" in
                INCOMPLETE|RUNNING|FAILED)
                    # All incomplete/running/failed jobs are treated as failures
                    # Apply progressive recovery strategy:
                    # - Stage 1: POTIM=0.2
                    # - Stage 2: POTIM=0.2,ALGO=Veryfast
                    # - Stage 3: Continue with both parameters
                    resubmit_running_job "$calc_dir" "$structure_name" "$job_name" "$status"
                    ;;
                PENDING)
                    # Submit pending jobs with auto-detection of Th/U for magmom settings
                    submit_pending_job "$calc_dir" "$structure_name" "$job_name"
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
echo -e "Incomplete jobs resubmitted:  ${YELLOW}${running_resubmitted}${NC}"
echo -e "  ↳ (includes wall-time limited, failed, and incomplete jobs)"
echo -e "Pending jobs submitted:       ${BLUE}${pending_submitted}${NC}"
echo -e "Skipped (already completed):  ${GREEN}${skipped_jobs}${NC}"
if [ $failed_resubmits -gt 0 ]; then
    echo -e "Failed to resubmit:           ${RED}${failed_resubmits}${NC}"
    echo -e "  ⚠ Check mpjob errors above for details"
fi
echo "============================================================================"
echo ""
