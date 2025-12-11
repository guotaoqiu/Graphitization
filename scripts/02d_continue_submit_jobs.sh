#!/bin/bash
################################################################################
# Continue Job Submission Script
# Resubmits RUNNING jobs (with CONTCAR->POSCAR) and submits PENDING jobs
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
NC='\033[0m'

echo "============================================================================"
echo "Continue Job Submission (RUNNING + PENDING)"
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
# Function to resubmit a running job (CONTCAR -> POSCAR)
################################################################################
resubmit_running_job() {
    local calc_dir=$1
    local structure_name=$2
    local job_name=$3

    echo -e "${YELLOW}Resubmitting RUNNING job: ${job_name}${NC}"

    cd "$calc_dir" || return 1

    # Check if calculation failed
    local calc_failed=false
    if [ -f "OUTCAR" ]; then
        if grep -q "ZBRENT: fatal error" "OUTCAR" 2>/dev/null || \
           grep -q "ERROR" "OUTCAR" 2>/dev/null; then
            calc_failed=true
            echo "  ⚠ Calculation failed, will change ALGO to Fast"
        fi
    fi

    # Check CONTCAR and copy to POSCAR
    local contcar_empty=false
    if [ -f "CONTCAR" ]; then
        # Check if CONTCAR is empty or has only a few lines (header only)
        local line_count=$(wc -l < "CONTCAR" 2>/dev/null || echo 0)
        if [ "$line_count" -lt 8 ]; then
            contcar_empty=true
            echo "  ⚠ CONTCAR is empty or incomplete, will use original structure and change ALGO to Fast"
        else
            cp CONTCAR POSCAR
            echo "  ✓ Copied CONTCAR to POSCAR"
        fi
    else
        contcar_empty=true
        echo "  ⚠ CONTCAR not found, will use original structure and change ALGO to Fast"
    fi

    # If CONTCAR is empty or failed, modify INCAR to use ALGO=Fast
    if [ "$contcar_empty" = true ] || [ "$calc_failed" = true ]; then
        if [ -f "INCAR" ]; then
            # Change ALGO from Normal to Fast (or add if not present)
            if grep -q "^[[:space:]]*ALGO" "INCAR"; then
                sed -i 's/^[[:space:]]*ALGO[[:space:]]*=.*/ALGO = Fast/' "INCAR"
                echo "  ✓ Changed ALGO to Fast in INCAR"
            else
                echo "ALGO = Fast" >> "INCAR"
                echo "  ✓ Added ALGO = Fast to INCAR"
            fi
        fi
    fi

    # Find the structure file (*.vasp)
    structure_file=$(find . -maxdepth 1 -name "*.vasp" | head -1)

    if [ -z "$structure_file" ]; then
        # If no .vasp file found, use POSCAR
        if [ -f "POSCAR" ]; then
            structure_file="POSCAR"
        else
            echo -e "  ${RED}✗ No structure file found${NC}"
            cd - > /dev/null
            return 1
        fi
    fi

    # Create a temporary directory for mpjob output to avoid directory conflict
    local temp_outdir="temp_mpjob_$$"
    mkdir -p "$temp_outdir"

    # Copy structure file to temp directory
    cp "$(basename $structure_file)" "$temp_outdir/"

    # Copy INCAR if it exists (to preserve ALGO changes)
    if [ -f "INCAR" ]; then
        cp "INCAR" "$temp_outdir/"
    fi

    # Construct mpjob command in temp directory
    local mpjob_cmd="mpjob $(basename $structure_file) -t $TASK_TYPE -p $PARTITION -n $NCORES -m $MODE"

    # Add custom parameters if specified
    if [ -n "$CUSTOM_PARAMS" ]; then
        mpjob_cmd="$mpjob_cmd -c $CUSTOM_PARAMS"
    fi

    # Add job name
    mpjob_cmd="$mpjob_cmd --name $structure_name"

    # Submit job from temp directory
    echo "  Running: $mpjob_cmd"
    cd "$temp_outdir"
    eval $mpjob_cmd
    local submit_status=$?
    cd - > /dev/null

    if [ $submit_status -eq 0 ]; then
        # Copy generated files back from temp directory
        cp -r "$temp_outdir"/* .
        echo -e "  ${GREEN}✓ Successfully resubmitted${NC}"
        running_resubmitted=$((running_resubmitted + 1))
    else
        echo -e "  ${RED}✗ Failed to resubmit${NC}"
        failed_resubmits=$((failed_resubmits + 1))
    fi

    # Clean up temp directory
    rm -rf "$temp_outdir"

    cd - > /dev/null
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

    cd "$calc_dir" || return 1

    # Find the structure file (*.vasp)
    structure_file=$(find . -maxdepth 1 -name "*.vasp" | head -1)

    if [ -z "$structure_file" ]; then
        echo -e "  ${RED}✗ No structure file found${NC}"
        cd - > /dev/null
        return 1
    fi

    # Construct mpjob command
    local mpjob_cmd="mpjob $(basename $structure_file) -t $TASK_TYPE -p $PARTITION -n $NCORES -m $MODE"

    # Add custom parameters if specified
    if [ -n "$CUSTOM_PARAMS" ]; then
        mpjob_cmd="$mpjob_cmd -c $CUSTOM_PARAMS"
    fi

    # Add job name
    mpjob_cmd="$mpjob_cmd --name $structure_name"

    # Submit job
    echo "  Running: $mpjob_cmd"
    eval $mpjob_cmd

    if [ $? -eq 0 ]; then
        echo -e "  ${GREEN}✓ Successfully submitted${NC}"
        pending_submitted=$((pending_submitted + 1))
    else
        echo -e "  ${RED}✗ Failed to submit${NC}"
        failed_resubmits=$((failed_resubmits + 1))
    fi

    cd - > /dev/null
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

            # Determine job status
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

            # Process based on status
            case "$status" in
                RUNNING|FAILED)
                    # Both running and failed jobs should be resubmitted
                    # Failed jobs will have ALGO changed to Fast automatically
                    resubmit_running_job "$calc_dir" "$structure_name" "$job_name"
                    ;;
                PENDING)
                    submit_pending_job "$calc_dir" "$structure_name" "$job_name"
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
echo -e "Total jobs scanned:       ${total_jobs}"
echo -e "Running jobs resubmitted: ${YELLOW}${running_resubmitted}${NC}"
echo -e "Pending jobs submitted:   ${BLUE}${pending_submitted}${NC}"
echo -e "Skipped (completed/failed): ${skipped_jobs}"
echo -e "Failed to resubmit:       ${RED}${failed_resubmits}${NC}"
echo "============================================================================"
echo ""
