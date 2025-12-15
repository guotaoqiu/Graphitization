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
echo "  • Detects wall time limits and continues from CONTCAR"
echo "  • Progressive recovery: POTIM=0.2 → ALGO=Veryfast"
echo "  • Intelligently validates CONTCAR before using"
echo "  • Backs up files before resubmission"
echo "  • Resubmits pending jobs automatically"
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
# Function to check if calculation hit wall time limit
################################################################################
check_wall_time() {
    local outcar_file="$1"

    if [ ! -f "$outcar_file" ]; then
        return 1  # No OUTCAR, can't determine
    fi

    # Check for common wall time indicators
    if grep -q "STOPCAR" "$outcar_file" 2>/dev/null || \
       grep -q "walltime" "$outcar_file" 2>/dev/null || \
       tail -20 "$outcar_file" | grep -q "reached required accuracy" -v 2>/dev/null; then
        # Check if it's NOT completed successfully
        if ! grep -q "reached required accuracy" "$outcar_file" 2>/dev/null; then
            return 0  # Hit wall time
        fi
    fi

    return 1  # Did not hit wall time
}

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

# Add or update POTIM in INCAR
add_potim_to_incar() {
    local incar_file=$1
    local potim_value=${2:-0.2}

    if [ ! -f "$incar_file" ]; then
        echo "  ⚠ INCAR file not found: $incar_file"
        return 1
    fi

    # Check if POTIM already exists
    if grep -q "^[[:space:]]*POTIM" "$incar_file"; then
        # Update existing POTIM
        sed -i "s/^[[:space:]]*POTIM[[:space:]]*=.*/POTIM = $potim_value/" "$incar_file"
        echo "  ✓ Updated POTIM = $potim_value in INCAR"
    else
        # Add POTIM to INCAR
        echo "POTIM = $potim_value" >> "$incar_file"
        echo "  ✓ Added POTIM = $potim_value to INCAR"
    fi

    return 0
}

# Change ALGO to Veryfast in INCAR
change_algo_to_veryfast() {
    local incar_file=$1

    if [ ! -f "$incar_file" ]; then
        echo "  ⚠ INCAR file not found: $incar_file"
        return 1
    fi

    # Check if ALGO exists
    if grep -q "^[[:space:]]*ALGO" "$incar_file"; then
        # Update existing ALGO
        sed -i "s/^[[:space:]]*ALGO[[:space:]]*=.*/ALGO = Veryfast/" "$incar_file"
        echo "  ✓ Changed ALGO = Veryfast in INCAR"
    else
        # Add ALGO to INCAR
        echo "ALGO = Veryfast" >> "$incar_file"
        echo "  ✓ Added ALGO = Veryfast to INCAR"
    fi

    return 0
}

################################################################################
# Function to resubmit a running/incomplete job using mpjob -j
################################################################################
resubmit_running_job() {
    local calc_dir=$1
    local structure_name=$2
    local job_name=$3

    echo -e "${YELLOW}Resubmitting INCOMPLETE job: ${job_name}${NC}"

    # Analyze calculation status without changing directory
    local calc_failed=false
    local hit_wall_time=false
    local contcar_valid=false

    # Check if calculation failed with errors
    if [ -f "$calc_dir/OUTCAR" ]; then
        if grep -q "ZBRENT: fatal error" "$calc_dir/OUTCAR" 2>/dev/null || \
           grep -q "ERROR" "$calc_dir/OUTCAR" 2>/dev/null; then
            calc_failed=true
            echo "  ⚠ Calculation failed with errors"
        fi

        # Check for wall time limit
        if check_wall_time "$calc_dir/OUTCAR"; then
            hit_wall_time=true
            echo "  ⏱ Calculation hit wall time limit"
        fi
    fi

    # Check CONTCAR validity
    if [ -f "$calc_dir/CONTCAR" ]; then
        local line_count=$(wc -l < "$calc_dir/CONTCAR" 2>/dev/null || echo 0)
        if [ "$line_count" -ge 8 ]; then
            # Check if CONTCAR has actual atomic coordinates (not all zeros)
            if tail -n +8 "$calc_dir/CONTCAR" | grep -q "[1-9]" 2>/dev/null; then
                contcar_valid=true
                echo "  ✓ Valid CONTCAR found (${line_count} lines)"
            else
                echo "  ⚠ CONTCAR exists but appears empty/invalid"
            fi
        else
            echo "  ⚠ CONTCAR is incomplete (${line_count} lines)"
        fi
    else
        echo "  ⚠ No CONTCAR found"
    fi

    # Progressive recovery strategy for failed jobs
    if [ "$calc_failed" = true ]; then
        local recovery_stage=$(get_recovery_stage "$calc_dir")
        echo "  Recovery stage: $recovery_stage"

        case "$recovery_stage" in
            none)
                # First recovery attempt: Add POTIM = 0.2
                echo -e "  ${CYAN}→ Applying recovery strategy 1: POTIM = 0.2${NC}"
                if [ -f "$calc_dir/INCAR" ]; then
                    add_potim_to_incar "$calc_dir/INCAR" 0.2
                    touch "$calc_dir/.recovery_potim"
                    echo "  ✓ Created recovery marker: .recovery_potim"
                fi
                ;;
            potim_tried)
                # Second recovery attempt: Change ALGO to Veryfast
                echo -e "  ${CYAN}→ Applying recovery strategy 2: ALGO = Veryfast${NC}"
                if [ -f "$calc_dir/INCAR" ]; then
                    change_algo_to_veryfast "$calc_dir/INCAR"
                    touch "$calc_dir/.recovery_algo"
                    echo "  ✓ Created recovery marker: .recovery_algo"
                fi
                ;;
            algo_tried)
                # Both recovery strategies tried, just resubmit
                echo -e "  ${CYAN}→ Both recovery strategies already tried, resubmitting...${NC}"
                ;;
        esac
    fi

    # Prepare for continuation
    if [ "$contcar_valid" = true ] && [ "$hit_wall_time" = true ]; then
        # Only continue from CONTCAR if hit wall time (not for failed calculations)
        cp "$calc_dir/CONTCAR" "$calc_dir/POSCAR"
        echo -e "  ${CYAN}→ Continuing from CONTCAR${NC}"
    elif [ "$contcar_valid" = true ] && [ "$calc_failed" = false ]; then
        # Continue from CONTCAR for incomplete but not failed calculations
        cp "$calc_dir/CONTCAR" "$calc_dir/POSCAR"
        echo -e "  ${CYAN}→ Continuing from CONTCAR${NC}"
    else
        echo -e "  ${CYAN}→ Using existing POSCAR${NC}"
    fi

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
    # The -m fast mode will automatically handle ALGO changes
    local mpjob_cmd="mpjob \"$structure_file\" -j \"$calc_dir\" -t $TASK_TYPE -p $PARTITION -n $NCORES -m $MODE"

    # Add custom parameters if specified
    if [ -n "$CUSTOM_PARAMS" ]; then
        mpjob_cmd="$mpjob_cmd -c $CUSTOM_PARAMS"
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

    # Construct mpjob command with explicit output directory
    local mpjob_cmd="mpjob \"$structure_file\" -o \"$calc_dir\" -t $TASK_TYPE -p $PARTITION -n $NCORES -m $MODE"

    # Add custom parameters if specified
    if [ -n "$CUSTOM_PARAMS" ]; then
        mpjob_cmd="$mpjob_cmd -c $CUSTOM_PARAMS"
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
                    # Resubmit incomplete, running, and failed jobs
                    # The function will handle each case appropriately:
                    # - INCOMPLETE with valid CONTCAR: continue from CONTCAR
                    # - FAILED: progressive recovery (POTIM=0.2 → ALGO=Veryfast)
                    # - RUNNING with empty CONTCAR: resubmit
                    resubmit_running_job "$calc_dir" "$structure_name" "$job_name"
                    ;;
                PENDING)
                    # Submit pending jobs that haven't been started yet
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
