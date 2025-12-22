#!/bin/bash
################################################################################
# Script to check the status of all calculations
################################################################################

CALC_DIR_DOPED="../03_calculations/doped_relaxation"
CALC_DIR_PRISTINE="../03_calculations/pristine_relaxation"
CALC_DIR_ADSORPTION="../03_calculations/adsorption"

echo "================================================================================"
echo "Calculation Status Summary"
echo "================================================================================"
echo ""

# Function to check calculation status
check_status() {
    local calc_dir=$1
    local name=$2

    if [ ! -d "$calc_dir" ]; then
        echo "  Directory not found"
        return
    fi

    total=0
    completed=0
    running=0
    failed=0
    not_started=0

    for job_dir in "$calc_dir"/*; do
        if [ ! -d "$job_dir" ]; then
            continue
        fi

        ((total++))

        if [ -f "$job_dir/OUTCAR" ]; then
            if grep -q "reached required accuracy" "$job_dir/OUTCAR" 2>/dev/null; then
                ((completed++))
            elif grep -q "ZBRENT: fatal error\|ERROR" "$job_dir/OUTCAR" 2>/dev/null; then
                ((failed++))
            else
                ((running++))
            fi
        else
            ((not_started++))
        fi
    done

    if [ $total -eq 0 ]; then
        echo "  No calculations found"
    else
        echo "  Total: $total"
        echo "  Completed: $completed"
        echo "  Running: $running"
        echo "  Failed: $failed"
        echo "  Not started: $not_started"

        if [ $total -gt 0 ]; then
            completion_rate=$((completed * 100 / total))
            echo "  Completion rate: ${completion_rate}%"
        fi
    fi
}

# Check pristine relaxation
echo "PRISTINE GRAPHENE RELAXATION"
echo "--------------------------------------------------------------------------------"
check_status "$CALC_DIR_PRISTINE" "Pristine"
echo ""

# Check doped structure relaxations
echo "DOPED STRUCTURE RELAXATIONS"
echo "--------------------------------------------------------------------------------"
check_status "$CALC_DIR_DOPED" "Doped"
echo ""

# Check adsorption calculations
echo "LI ADSORPTION CALCULATIONS"
echo "--------------------------------------------------------------------------------"
check_status "$CALC_DIR_ADSORPTION" "Adsorption"
echo ""

echo "================================================================================"
echo "Queue Status"
echo "================================================================================"
squeue -u $USER
echo ""

echo "================================================================================"
echo "Commands"
echo "================================================================================"
echo "Monitor specific job:"
echo "  cd <job_directory>"
echo "  tail -f OUTCAR"
echo ""
echo "Check energy convergence:"
echo "  grep 'energy  without entropy' <job_directory>/OUTCAR"
echo ""
echo "Resubmit failed jobs:"
echo "  (Manual intervention required - check OUTCAR for errors)"
echo "================================================================================"
