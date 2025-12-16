#!/bin/bash
################################################################################
# Resubmit Corrupted Running Jobs Script
# Identifies RUNNING jobs with corrupted (0K) POSCAR files and resubmits them
# from scratch using the original structure files
################################################################################

CALC_DIR="../02_calculations"
STRUCTURE_DIR="../01_structure_generation/doped_structures"
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
MAGENTA='\033[0;35m'
NC='\033[0m'

echo "============================================================================"
echo "Resubmit Corrupted Running Jobs from Scratch"
echo "============================================================================"
echo "This script will:"
echo "  • Find RUNNING jobs (have INCAR but not completed)"
echo "  • Check for corrupted POSCAR files (0 bytes)"
echo "  • Clean up corrupted calculation directories"
echo "  • Resubmit from original structure files"
echo "============================================================================"
echo ""

# Check if directories exist
if [ ! -d "$CALC_DIR" ]; then
    echo -e "${RED}Error: Calculation directory not found: $CALC_DIR${NC}"
    exit 1
fi

if [ ! -d "$STRUCTURE_DIR" ]; then
    echo -e "${RED}Error: Structure directory not found: $STRUCTURE_DIR${NC}"
    echo "Please ensure the original structure files are in: $STRUCTURE_DIR"
    exit 1
fi

# Counters
total_jobs=0
corrupted_found=0
resubmitted=0
failed_resubmits=0
skipped_jobs=0

################################################################################
# Function to check if POSCAR is corrupted (0 bytes)
################################################################################
is_poscar_corrupted() {
    local poscar_file=$1

    if [ ! -f "$poscar_file" ]; then
        # POSCAR doesn't exist - also considered corrupted
        return 0
    fi

    local file_size=$(stat -f%z "$poscar_file" 2>/dev/null || stat -c%s "$poscar_file" 2>/dev/null)
    if [ "$file_size" -eq 0 ]; then
        return 0  # Corrupted (0 bytes)
    fi

    return 1  # Not corrupted
}

################################################################################
# Function to find original structure file
################################################################################
find_original_structure() {
    local structure_name=$1

    # Try different naming patterns
    # Pattern 1: exact match (e.g., graphite_int_Fe_bridge.vasp)
    if [ -f "$STRUCTURE_DIR/${structure_name}.vasp" ]; then
        echo "$STRUCTURE_DIR/${structure_name}.vasp"
        return 0
    fi

    # Pattern 2: try replacing "int" with "init" (e.g., graphite_int_Fe_bridge -> graphite_init_Fe_bridge.vasp)
    local alt_name=$(echo "$structure_name" | sed 's/_int_/_init_/')
    if [ -f "$STRUCTURE_DIR/${alt_name}.vasp" ]; then
        echo "$STRUCTURE_DIR/${alt_name}.vasp"
        return 0
    fi

    # Pattern 3: try removing suffixes and searching
    local base_name=$(echo "$structure_name" | sed 's/_relax$//' | sed 's/_static$//')
    if [ -f "$STRUCTURE_DIR/${base_name}.vasp" ]; then
        echo "$STRUCTURE_DIR/${base_name}.vasp"
        return 0
    fi

    # Pattern 4: fuzzy search for similar names
    local found_file=$(find "$STRUCTURE_DIR" -name "*${structure_name}*.vasp" | head -1)
    if [ -n "$found_file" ]; then
        echo "$found_file"
        return 0
    fi

    return 1
}

################################################################################
# Function to clean and resubmit a corrupted job
################################################################################
resubmit_corrupted_job() {
    local calc_dir=$1
    local structure_name=$2
    local job_name=$3

    echo -e "${MAGENTA}Processing corrupted job: ${job_name}${NC}"

    # Find the original structure file
    local structure_file=$(find_original_structure "$structure_name")

    if [ -z "$structure_file" ] || [ ! -f "$structure_file" ]; then
        echo -e "  ${RED}✗ Original structure file not found for: ${structure_name}${NC}"
        echo -e "  Searched in: $STRUCTURE_DIR"
        echo -e "  Tried patterns:"
        echo -e "    - ${structure_name}.vasp"
        echo -e "    - ${structure_name/_int_/_init_}.vasp"
        echo -e "    - *${structure_name}*.vasp"
        failed_resubmits=$((failed_resubmits + 1))
        echo "----------------------------------------"
        return 1
    fi

    echo -e "  ${CYAN}✓ Found original structure: $(basename $structure_file)${NC}"

    # Backup the corrupted directory
    local backup_dir="${calc_dir}_corrupted_backup_$(date +%Y%m%d_%H%M%S)"
    echo -e "  ${YELLOW}Creating backup: $(basename $backup_dir)${NC}"
    cp -r "$calc_dir" "$backup_dir"

    # Clean up the calculation directory (remove all files except the backup markers)
    echo -e "  ${YELLOW}Cleaning calculation directory...${NC}"
    find "$calc_dir" -type f ! -name '.recovery_*' -delete

    # Remove recovery markers since we're starting from scratch
    rm -f "$calc_dir/.recovery_potim" "$calc_dir/.recovery_algo"

    # Navigate to parent directory for mpjob submission
    local parent_dir=$(dirname "$calc_dir")
    cd "$parent_dir" || exit

    # Construct mpjob command to submit to the specific calculation directory
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
        echo -e "  ${GREEN}✓ Successfully resubmitted from scratch${NC}"
        resubmitted=$((resubmitted + 1))
    else
        echo -e "  ${RED}✗ Failed to resubmit (exit code: $submit_status)${NC}"
        failed_resubmits=$((failed_resubmits + 1))
    fi

    # Return to original directory
    cd - > /dev/null || exit

    echo "----------------------------------------"
}

################################################################################
# Main loop through all job directories
################################################################################

echo "Scanning for corrupted RUNNING jobs..."
echo ""

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

            # Check if this is a RUNNING job (has INCAR but not completed)
            is_running=false

            if [ -f "$calc_dir/INCAR" ]; then
                # Has INCAR - check if completed
                if [ -f "$calc_dir/OUTCAR" ]; then
                    # Check if calculation completed successfully
                    if grep -q "reached required accuracy" "$calc_dir/OUTCAR" 2>/dev/null; then
                        # Completed - skip
                        skipped_jobs=$((skipped_jobs + 1))
                        continue
                    else
                        # Has OUTCAR but not completed - consider as running
                        is_running=true
                    fi
                else
                    # Has INCAR but no OUTCAR - running
                    is_running=true
                fi
            else
                # No INCAR - not started yet
                skipped_jobs=$((skipped_jobs + 1))
                continue
            fi

            # If it's a running job, check for corrupted POSCAR
            if [ "$is_running" = true ]; then
                local poscar_file="$calc_dir/POSCAR"

                if is_poscar_corrupted "$poscar_file"; then
                    corrupted_found=$((corrupted_found + 1))

                    if [ -f "$poscar_file" ]; then
                        local file_size=$(stat -f%z "$poscar_file" 2>/dev/null || stat -c%s "$poscar_file" 2>/dev/null)
                        echo -e "${RED}Found corrupted POSCAR (${file_size} bytes): ${job_name}${NC}"
                    else
                        echo -e "${RED}Found missing POSCAR: ${job_name}${NC}"
                    fi

                    # Resubmit this corrupted job
                    resubmit_corrupted_job "$calc_dir" "$structure_name" "$job_name"
                else
                    # POSCAR exists and is not corrupted - skip
                    skipped_jobs=$((skipped_jobs + 1))
                fi
            fi
        done
    fi
done

echo ""
echo "============================================================================"
echo "Resubmission Summary"
echo "============================================================================"
echo -e "Total jobs scanned:              ${total_jobs}"
echo -e "Corrupted RUNNING jobs found:    ${RED}${corrupted_found}${NC}"
echo -e "Successfully resubmitted:        ${GREEN}${resubmitted}${NC}"
echo -e "Failed to resubmit:              ${RED}${failed_resubmits}${NC}"
echo -e "Skipped (healthy/completed):     ${BLUE}${skipped_jobs}${NC}"
echo "============================================================================"
echo ""

if [ $corrupted_found -gt 0 ]; then
    echo -e "${YELLOW}Note: Corrupted directories have been backed up with '_corrupted_backup_' suffix${NC}"
    echo ""
fi

if [ $failed_resubmits -gt 0 ]; then
    echo -e "${RED}Warning: Some jobs failed to resubmit. Check the errors above.${NC}"
    echo -e "${YELLOW}Common issues:${NC}"
    echo -e "  • Original structure file not found in $STRUCTURE_DIR"
    echo -e "  • Incorrect file naming pattern (check int vs init)"
    echo -e "  • mpjob command failed (check partition, resources, etc.)"
    echo ""
fi

if [ $resubmitted -gt 0 ]; then
    echo -e "${GREEN}Successfully resubmitted ${resubmitted} corrupted job(s) from scratch!${NC}"
    echo -e "Use ${CYAN}bash 02b_monitor_jobs.sh -v${NC} to check job status"
    echo ""
fi
