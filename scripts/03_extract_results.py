#!/usr/bin/env python3
"""
Script to extract and analyze results from high-throughput calculations
Extracts: lattice parameters, interlayer spacing, energies, formation energies
"""

import os
import json
import pandas as pd
import numpy as np
from pathlib import Path
from pymatgen.core import Structure
from pymatgen.io.vasp.outputs import Vasprun, Outcar
import warnings
warnings.filterwarnings('ignore')

# Chemical potential table for common elements (DFT calculated)
CHEMICAL_POTENTIALS = {
    'Cl': -1.84853666, 'Ir': -8.83843418, 'Tm': -4.475835423333334, 'Li': -1.9089228666666667,
    'Hf': -9.95718903, 'Sb': -4.12900124, 'Mg': -1.60028005, 'Dy': -4.60678684, 'Ho': -4.58240887,
    'Pa': -9.51466466, 'Cd': -0.92288976, 'As': -4.659118405, 'Ne': -0.02593678, 'Tc': -10.360638945,
    'Np': -12.94777968125, 'Tb': -4.6343661, 'Sn': -4.009571855, 'Rb': -0.9805340725, 'Er': -4.56771881,
    'Cs': -0.8954023720689656, 'In': -2.75168373, 'Hg': -0.303680365, 'K': -1.110398947,
    'Na': -1.3225252934482759, 'Sr': -1.6894934533333332, 'Y': -6.466471113333333,
    'P': -5.413302506666667, 'Ba': -1.91897494, 'Nd': -4.7681474325, 'Pt': -6.07113332,
    'Mo': -10.84565011, 'Fe': -8.47002121, 'Zr': -8.54770063, 'Al': -3.74557583, 'Ga': -3.0280960225,
    'Lu': -4.52095052, 'V': -9.08390607, 'Si': -5.42531803, 'Gd': -14.07612224, 'B': -6.679391770833334,
    'Te': -3.1433058933333338, 'Pd': -5.17988181, 'Pb': -3.71264707, 'Ni': -5.78013668,
    'Ar': -0.06880822, 'He': -0.00905951, 'H': -3.392726045, 'N': -8.336494925, 'C': -9.2286654925,
    'La': -4.936007105, 'Cu': -4.09920667, 'Ge': -4.623027855, 'Ru': -9.27440254,
    'Mn': -9.162015292068965, 'Th': -7.41385825, 'Pr': -4.780905755, 'U': -11.29141001,
    'Ca': -2.00559988, 'Os': -11.22736743, 'Ta': -11.85777763, 'Co': -7.108317795, 'F': -1.9114789675,
    'Ce': -5.933089155, 'Bi': -3.84048913, 'Se': -3.49591147765625, 'Pu': -14.26783833,
    'Kr': -0.05671467, 'Eu': -10.2570018, 'I': -1.47336635, 'Sc': -6.332469105, 'Sm': -4.718586135,
    'Ti': -7.895492016666666, 'O': -4.94668871125, 'Rh': -7.36430787, 'Nb': -10.10130504,
    'Zn': -1.25974361, 'Re': -12.444527185, 'Au': -3.273882, 'Ac': -4.1211750075, 'Pm': -4.7505423225,
    'Be': -3.739412865, 'Cr': -9.65304747, 'W': -12.95813023, 'S': -4.136449866875, 'Xe': -0.03617417,
    'Yb': -1.5396082800000002, 'Tl': -2.3626431466666666, 'Ag': -2.8325560033333335, 'Br': -1.55302833
}


class GraphiteResultsAnalyzer:
    """Extract and analyze results from doped graphite calculations"""

    def __init__(self, calc_dir, metadata_file=None):
        """
        Initialize the results analyzer

        Args:
            calc_dir: Directory containing calculation results
            metadata_file: Path to structure metadata JSON file
        """
        self.calc_dir = Path(calc_dir)
        self.results = []
        self.metadata = {}

        # Load metadata if available
        if metadata_file and os.path.exists(metadata_file):
            with open(metadata_file, 'r') as f:
                meta_list = json.load(f)
                self.metadata = {m['filename'].replace('.vasp', ''): m
                               for m in meta_list}
            print(f"Loaded metadata for {len(self.metadata)} structures")

    def parse_structure_name(self, structure_name):
        """
        Extract dopant and doping information from structure name

        Expected naming patterns:
        - graphite_int_{ELEMENT}_{site}_{supercell}  (interstitial)
        - graphite_int_{ELEMENT}_{site}               (interstitial, 1x1x1)
        - graphite_sub_{ELEMENT}_{supercell}         (substitutional)
        - graphite_sub_{ELEMENT}                     (substitutional, 1x1x1)
        - graphite_pristine_{supercell}              (pure)
        - graphite_pristine                          (pure, 1x1x1)

        Args:
            structure_name: Name of the structure (directory or file name without .vasp)

        Returns:
            dict: Dictionary with dopant, doping_type, site, supercell info
        """
        info = {
            'dopant': None,
            'doping_type': None,
            'site': None,
            'supercell': '1x1x1'
        }

        # Remove .vasp extension if present
        name = structure_name.replace('.vasp', '')

        # Split by underscore
        parts = name.split('_')

        if len(parts) < 2:
            return info

        # Check if it's pristine/pure graphite
        if 'pristine' in parts or 'pure' in parts:
            info['doping_type'] = 'pure'
            # Look for supercell (e.g., 2x2x1, 3x3x1)
            for part in parts:
                if 'x' in part and part.replace('x', '').replace('X', '').replace('0', '').replace('1', '').replace('2', '').replace('3', '').replace('4', '').replace('5', '').replace('6', '').replace('7', '').replace('8', '').replace('9', '') == '':
                    info['supercell'] = part
            return info

        # Check for interstitial (int) or substitutional (sub)
        if 'int' in parts:
            info['doping_type'] = 'interstitial'
            doping_idx = parts.index('int')
        elif 'sub' in parts:
            info['doping_type'] = 'substitutional'
            doping_idx = parts.index('sub')
        else:
            return info

        # Extract dopant element (should be right after 'int' or 'sub')
        if doping_idx + 1 < len(parts):
            potential_dopant = parts[doping_idx + 1]
            # Check if it's a valid element (starts with capital letter)
            if potential_dopant and potential_dopant[0].isupper():
                # Handle two-letter elements (e.g., Al, Ru, etc.)
                if len(potential_dopant) >= 2 and potential_dopant[1].islower():
                    info['dopant'] = potential_dopant[:2]
                else:
                    info['dopant'] = potential_dopant[0]

                # Verify it's in our chemical potentials list
                if info['dopant'] not in CHEMICAL_POTENTIALS:
                    # Try the full part in case it's a multi-char element
                    if potential_dopant in CHEMICAL_POTENTIALS:
                        info['dopant'] = potential_dopant

        # Extract site information (for interstitial)
        if info['doping_type'] == 'interstitial':
            # Site is typically after the element (hollow, bridge, above_atom, etc.)
            site_parts = []
            for i in range(doping_idx + 2, len(parts)):
                part = parts[i]
                # Stop if we hit a supercell designation
                if 'x' in part and len(part) <= 6:  # e.g., 2x2x1
                    break
                site_parts.append(part)
            if site_parts:
                info['site'] = '_'.join(site_parts)

        # Extract supercell information (e.g., 2x2x1, 3x3x1, 4x4x1)
        for part in parts:
            if 'x' in part.lower():
                # Check if it looks like a supercell (e.g., 2x2x1)
                subparts = part.lower().split('x')
                if len(subparts) == 3:
                    try:
                        # Verify all are numbers
                        [int(x) for x in subparts]
                        info['supercell'] = part
                        break
                    except ValueError:
                        continue

        return info

    def extract_lattice_parameters(self, structure):
        """Extract lattice parameters from structure"""
        lattice = structure.lattice
        return {
            'a': lattice.a,
            'b': lattice.b,
            'c': lattice.c,
            'alpha': lattice.alpha,
            'beta': lattice.beta,
            'gamma': lattice.gamma,
            'volume': lattice.volume,
        }

    def calculate_interlayer_spacing(self, structure):
        """
        Calculate interlayer spacing for graphite
        Calculates distance between average z-positions of the two carbon layers
        Only considers carbon atoms to avoid including interstitial dopants

        IMPORTANT: Due to periodic boundary conditions (PBC), there are effectively three layers:
        - Layer A (near z=0)
        - Layer B (near z=0.5)
        - Layer C (near z=1.0, which is equivalent to Layer A due to PBC)

        When doping causes expansion, Layer A can be pushed to negative z (wraps to ~z=0.9-1.0).
        This compresses the spacing between B and C (or A in the next cell).
        We must measure the EXPANDED spacing between layers near z=0 and z=0.5,
        NOT the compressed spacing to the layer near z=1.0.
        """
        # Get z-coordinates of carbon atoms only (graphene layers)
        z_coords = np.array([site.frac_coords[2] for site in structure if site.species_string == 'C'])

        if len(z_coords) < 2:
            return {
                'avg_interlayer_spacing': None,
                'min_interlayer_spacing': None,
                'max_interlayer_spacing': None,
                'num_layers': 0,
            }

        # Normalize z-coordinates to [0, 1) to handle atoms that may have wrapped
        # due to periodic boundary conditions
        z_coords_normalized = z_coords % 1.0

        # Sort z-coordinates
        z_coords_sorted = np.sort(z_coords_normalized)

        # Identify two layers by finding the largest gap in z-coordinates
        # This separates the two graphene layers
        if len(z_coords_sorted) >= 2:
            # Calculate gaps between consecutive atoms
            gaps = np.diff(z_coords_sorted)

            # Find the largest gap - this separates the two layers
            max_gap_idx = np.argmax(gaps)

            # Split into two layers
            layer1 = z_coords_sorted[:max_gap_idx + 1]
            layer2 = z_coords_sorted[max_gap_idx + 1:]

            # Handle periodic boundary case: check if last and first atoms are closer
            # than the identified gap (i.e., the gap wraps around z=0/z=1 boundary)
            boundary_gap = 1.0 - z_coords_sorted[-1] + z_coords_sorted[0]
            if boundary_gap > gaps[max_gap_idx]:
                # The max gap is correct (layers don't wrap)
                avg_z1 = np.mean(layer1)
                avg_z2 = np.mean(layer2)
            else:
                # The layers wrap around the periodic boundary
                # Split at a different point
                layer1 = z_coords_sorted[max_gap_idx + 1:]
                layer2 = z_coords_sorted[:max_gap_idx + 1]
                avg_z1 = np.mean(layer1)
                avg_z2 = np.mean(layer2)

            # Calculate interlayer spacing
            spacing_frac = abs(avg_z2 - avg_z1)

            # Also consider periodic boundary
            spacing_frac_periodic = 1.0 - spacing_frac

            # KEY FIX: We want the spacing between layer near z=0 and layer near z=0.5
            # NOT the spacing to the layer near z=1.0 (which is compressed after expansion)
            # In ideal graphite, spacing ≈ 0.5 (half the c-axis)
            # After interstitial doping, one spacing expands (>0.5), one compresses (<0.5)
            # We want the EXPANDED spacing (the larger one), which represents the true
            # interlayer distance between the two physical layers in the unit cell
            spacing_frac = max(spacing_frac, spacing_frac_periodic)

            # Convert to Cartesian coordinates (Angstroms)
            spacing_angstrom = spacing_frac * structure.lattice.c

            return {
                'avg_interlayer_spacing': spacing_angstrom,
                'min_interlayer_spacing': spacing_angstrom,
                'max_interlayer_spacing': spacing_angstrom,
                'num_layers': 2,
            }
        else:
            return {
                'avg_interlayer_spacing': None,
                'min_interlayer_spacing': None,
                'max_interlayer_spacing': None,
                'num_layers': len(z_coords_sorted),
            }

    def extract_energy_data(self, vasprun_path, outcar_path):
        """Extract energy data from VASP output files"""
        energy_data = {}

        try:
            # Try to read from vasprun.xml (more reliable)
            if os.path.exists(vasprun_path):
                vasprun = Vasprun(vasprun_path, parse_dos=False, parse_eigen=False)
                energy_data['final_energy'] = vasprun.final_energy
                energy_data['energy_per_atom'] = vasprun.final_energy / len(vasprun.final_structure)

            # Also try OUTCAR
            elif os.path.exists(outcar_path):
                outcar = Outcar(outcar_path)
                energy_data['final_energy'] = outcar.final_energy
                # Get number of atoms from CONTCAR in same directory
                contcar_path = os.path.join(os.path.dirname(outcar_path), 'CONTCAR')
                if os.path.exists(contcar_path):
                    structure = Structure.from_file(contcar_path)
                    energy_data['energy_per_atom'] = outcar.final_energy / len(structure)

        except Exception as e:
            print(f"Warning: Could not extract energy from {vasprun_path}: {e}")
            energy_data['final_energy'] = None
            energy_data['energy_per_atom'] = None

        return energy_data

    def check_calculation_status(self, job_dir):
        """Check if calculation completed successfully"""
        outcar_path = job_dir / 'OUTCAR'

        if not outcar_path.exists():
            return 'not_started'

        try:
            with open(outcar_path, 'r') as f:
                content = f.read()

            if 'reached required accuracy' in content:
                return 'completed'
            elif 'ZBRENT: fatal error' in content or 'ERROR' in content:
                return 'failed'
            else:
                return 'running'
        except Exception as e:
            print(f"Warning: Could not read {outcar_path}: {e}")
            return 'unknown'

    def analyze_single_job(self, job_dir, structure_name=None):
        """Analyze results from a single calculation job"""
        job_name = job_dir.name
        # Use structure_name if provided for metadata lookup
        metadata_key = structure_name if structure_name else job_name
        print(f"Analyzing: {structure_name if structure_name else job_name} ({job_name})")

        result = {
            'job_name': metadata_key,
            'calc_type': job_name,
            'status': self.check_calculation_status(job_dir),
        }

        # Parse structure name to extract dopant information
        # This ensures we get dopant info even without metadata file
        parsed_info = self.parse_structure_name(metadata_key)
        result.update(parsed_info)

        # Add/override with metadata if available (metadata takes precedence)
        if metadata_key in self.metadata:
            result.update(self.metadata[metadata_key])

        # Only extract data from completed calculations
        if result['status'] != 'completed':
            print(f"  Skipping {metadata_key}: Status = {result['status']}")
            return result

        # Paths to output files
        contcar_path = job_dir / 'CONTCAR'
        vasprun_path = job_dir / 'vasprun.xml'
        outcar_path = job_dir / 'OUTCAR'

        try:
            # Extract structure information
            if contcar_path.exists():
                structure = Structure.from_file(str(contcar_path))

                # Lattice parameters
                lattice_params = self.extract_lattice_parameters(structure)
                result.update(lattice_params)

                # Interlayer spacing
                interlayer_data = self.calculate_interlayer_spacing(structure)
                result.update(interlayer_data)

                # Composition
                result['formula'] = structure.composition.formula
                result['num_atoms'] = len(structure)

            # Extract energy data
            energy_data = self.extract_energy_data(str(vasprun_path), str(outcar_path))
            result.update(energy_data)

            print(f"  ✓ Successfully extracted data")

        except Exception as e:
            print(f"  ✗ Error analyzing {job_name}: {e}")
            result['error'] = str(e)

        return result

    def analyze_all_jobs(self):
        """Analyze all calculation jobs in the directory"""
        print("="*70)
        print("Analyzing All Calculation Results")
        print("="*70)
        print()

        # Find all calculation directories
        # mpjob creates nested structure: structure_name/structure_name/calc_type/
        calc_dirs = []

        for structure_dir in self.calc_dir.iterdir():
            if not structure_dir.is_dir():
                continue

            structure_name = structure_dir.name

            # Pattern 1: structure_name/structure_name/calc_type/
            nested_dir = structure_dir / structure_name
            if nested_dir.is_dir():
                for calc_type_dir in nested_dir.iterdir():
                    if calc_type_dir.is_dir():
                        calc_dirs.append((calc_type_dir, structure_name))
            # Pattern 2: structure_name/calc_type/ (fallback)
            else:
                found_calc_dir = False
                for calc_type_dir in structure_dir.iterdir():
                    if calc_type_dir.is_dir() and calc_type_dir.name != structure_name:
                        calc_dirs.append((calc_type_dir, structure_name))
                        found_calc_dir = True

                # Pattern 3: Files directly in structure_name/ (old format)
                if not found_calc_dir:
                    if (structure_dir / 'OUTCAR').exists() or (structure_dir / 'CONTCAR').exists():
                        calc_dirs.append((structure_dir, structure_name))

        print(f"Found {len(calc_dirs)} calculation directories")
        print()

        # Analyze each job
        for calc_dir, structure_name in calc_dirs:
            result = self.analyze_single_job(calc_dir, structure_name)
            self.results.append(result)
            print()

        print("="*70)
        print(f"Analysis complete: {len(self.results)} jobs processed")
        print("="*70)

    def calculate_doping_concentration(self, result):
        """
        Calculate doping concentration from structure composition

        Returns:
            Doping concentration as percentage of dopant atoms to total atoms
        """
        if result.get('doping_type') == 'pure':
            return 0.0

        if 'num_atoms' in result and 'dopant' in result and result['dopant'] is not None:
            # Get structure composition
            composition = result.get('formula', '')
            if not composition:
                return None

            # Parse composition to count dopant atoms
            # This is a simple parser - for production use pymatgen.Composition
            dopant = result['dopant']
            num_atoms = result['num_atoms']

            # Count dopant atoms (assuming single dopant for now)
            # For more complex cases, use pymatgen
            dopant_count = 1  # Default for single substitution/interstitial

            # Calculate concentration as percentage
            concentration = (dopant_count / num_atoms) * 100.0
            return concentration

        return None

    def calculate_formation_energies(self, pure_energies_dict):
        """
        Calculate formation energies with proper chemical potentials

        Args:
            pure_energies_dict: Dictionary mapping supercell size to pure energy
                               e.g., {'1x1x1': -18.45, '2x2x1': -147.6, ...}

        Formation energy formulas:
        - Substitutional: E_f = E_doped - E_pure + n*E_C - n*E_dopant
        - Interstitial: E_f = E_doped - E_pure - n*E_dopant
        """
        print("\nCalculating formation energies with chemical potentials...")

        E_C = CHEMICAL_POTENTIALS.get('C', -9.2286654925)

        for result in self.results:
            if result.get('doping_type') == 'pure':
                result['formation_energy'] = 0.0
                result['formation_energy_per_atom'] = 0.0
                continue

            if result.get('final_energy') is None:
                continue

            # Get corresponding pure energy
            supercell = result.get('supercell', '1x1x1')
            E_pure = pure_energies_dict.get(supercell)

            if E_pure is None:
                print(f"  Warning: No pure energy for supercell {supercell}")
                continue

            E_doped = result['final_energy']
            dopant = result.get('dopant')
            doping_type = result.get('doping_type')

            if dopant is None or dopant not in CHEMICAL_POTENTIALS:
                print(f"  Warning: No chemical potential for dopant {dopant}")
                continue

            E_dopant = CHEMICAL_POTENTIALS[dopant]
            n_dopant = 1  # Assuming single dopant per structure

            # Calculate formation energy based on doping type
            if doping_type == 'substitutional':
                # E_f = E_doped - E_pure + n*E_C - n*E_dopant
                E_f = E_doped - E_pure + n_dopant * E_C - n_dopant * E_dopant
            elif doping_type == 'interstitial':
                # E_f = E_pure + n*E_dopant - E_doped
                E_f = E_doped - n_dopant * E_dopant - E_pure
            else:
                E_f = None

            result['formation_energy'] = E_f
            if result.get('num_atoms'):
                result['formation_energy_per_atom'] = E_f / result['num_atoms']

            # Calculate doping concentration
            concentration = self.calculate_doping_concentration(result)
            result['doping_concentration_percent'] = concentration

    def export_results(self, output_dir='../03_analysis'):
        """Export results to various formats"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Convert to DataFrame
        df = pd.DataFrame(self.results)

        # Save as CSV
        csv_path = output_dir / 'results_summary.csv'
        df.to_csv(csv_path, index=False)
        print(f"\n✓ Results saved to: {csv_path}")

        # Save as JSON (more complete)
        json_path = output_dir / 'results_complete.json'
        with open(json_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"✓ Complete results saved to: {json_path}")

        # Save summary statistics
        self.generate_summary_report(output_dir)

        return df

    def generate_summary_report(self, output_dir):
        """Generate a summary report of key findings"""
        report_path = output_dir / 'summary_report.txt'

        with open(report_path, 'w') as f:
            f.write("="*70 + "\n")
            f.write("High-Throughput Graphite Doping Study - Summary Report\n")
            f.write("="*70 + "\n\n")

            # Overall statistics
            df = pd.DataFrame(self.results)
            total = len(df)
            completed = len(df[df['status'] == 'completed'])

            f.write(f"Total calculations: {total}\n")
            f.write(f"Completed: {completed}\n")
            f.write(f"Completion rate: {completed/total*100:.1f}%\n\n")

            # Analysis by doping type
            if 'doping_type' in df.columns:
                f.write("Results by doping type:\n")
                f.write("-"*70 + "\n")
                for doping_type in df['doping_type'].unique():
                    if pd.isna(doping_type):
                        continue
                    subset = df[df['doping_type'] == doping_type]
                    completed_subset = subset[subset['status'] == 'completed']

                    f.write(f"\n{doping_type.capitalize()}:\n")
                    f.write(f"  Total: {len(subset)}\n")
                    f.write(f"  Completed: {len(completed_subset)}\n")

                    if len(completed_subset) > 0 and 'avg_interlayer_spacing' in completed_subset.columns:
                        avg_spacing = completed_subset['avg_interlayer_spacing'].mean()
                        f.write(f"  Avg interlayer spacing: {avg_spacing:.4f} Å\n")

            # Analysis by dopant, separated by doping type
            if 'dopant' in df.columns and 'doping_type' in df.columns:
                completed_df = df[df['status'] == 'completed']

                if len(completed_df) > 0:
                    # Split by doping type
                    for doping_type in ['interstitial', 'substitutional']:
                        f.write(f"\n\nResults by dopant element ({doping_type.capitalize()}):\n")
                        f.write("-"*70 + "\n")

                        type_df = completed_df[completed_df['doping_type'] == doping_type]

                        if len(type_df) > 0:
                            # Filter out None/NaN values before sorting
                            for dopant in sorted([d for d in type_df['dopant'].unique() if pd.notna(d)]):
                                if pd.isna(dopant):
                                    continue
                                subset = type_df[type_df['dopant'] == dopant]

                                if len(subset) > 0:
                                    f.write(f"\n{dopant}:\n")
                                    f.write(f"  Number of structures: {len(subset)}\n")

                                    if 'avg_interlayer_spacing' in subset.columns:
                                        mean_spacing = subset['avg_interlayer_spacing'].mean()
                                        std_spacing = subset['avg_interlayer_spacing'].std()
                                        f.write(f"  Interlayer spacing: {mean_spacing:.4f} ± {std_spacing:.4f} Å\n")

                                    if 'c' in subset.columns:
                                        mean_c = subset['c'].mean()
                                        std_c = subset['c'].std()
                                        f.write(f"  c parameter: {mean_c:.4f} ± {std_c:.4f} Å\n")

                                    if 'energy_per_atom' in subset.columns:
                                        mean_energy = subset['energy_per_atom'].mean()
                                        f.write(f"  Avg energy per atom: {mean_energy:.4f} eV\n")
                        else:
                            f.write(f"\nNo completed {doping_type} structures found.\n")

            f.write("\n" + "="*70 + "\n")

        print(f"✓ Summary report saved to: {report_path}")


def test_structure_name_parsing():
    """Test the structure name parsing function"""
    print("\n" + "="*70)
    print("Testing Structure Name Parsing")
    print("="*70)

    analyzer = GraphiteResultsAnalyzer('.', None)

    test_cases = [
        'graphite_int_Al_above_atom_2x2x1',
        'graphite_int_K_hollow_4x4x1',
        'graphite_int_Ru_bridge_alt',
        'graphite_sub_Ru_2x2x1',
        'graphite_pristine_3x3x1',
        'graphite_int_Ta_bridge',
        'graphite_int_Hf_bridge_alt_4x4x1',
    ]

    for test_name in test_cases:
        info = analyzer.parse_structure_name(test_name)
        print(f"\n{test_name}:")
        print(f"  Dopant: {info['dopant']}")
        print(f"  Type: {info['doping_type']}")
        print(f"  Site: {info['site']}")
        print(f"  Supercell: {info['supercell']}")

    print("\n" + "="*70 + "\n")


def main():
    """Main function"""
    CALC_DIR = "../02_calculations"
    METADATA_FILE = "../01_structure_generation/doped_structures/structure_metadata.json"
    OUTPUT_DIR = "../03_analysis"

    print("="*70)
    print("Graphite Doping Results Extraction and Analysis")
    print("="*70)
    print()

    # Initialize analyzer
    analyzer = GraphiteResultsAnalyzer(CALC_DIR, METADATA_FILE)

    # Analyze all jobs
    analyzer.analyze_all_jobs()

    # Extract pure structure energies for formation energy calculations
    print("\nExtracting pure structure energies...")
    pure_energies = {}
    for result in analyzer.results:
        if result.get('doping_type') == 'pure' and result.get('status') == 'completed':
            supercell = result.get('supercell', '1x1x1')
            energy = result.get('final_energy')
            if energy is not None:
                pure_energies[supercell] = energy
                print(f"  {supercell}: {energy:.6f} eV")

    if pure_energies:
        print(f"\nFound {len(pure_energies)} pure structure energies")
        # Calculate formation energies
        analyzer.calculate_formation_energies(pure_energies)
    else:
        print("\nWarning: No pure structure energies found. Skipping formation energy calculation.")
        print("Make sure to calculate pure graphite structures first!")

    # Export results
    df = analyzer.export_results(OUTPUT_DIR)

    # Display quick summary
    print("\nQuick Summary:")
    print("-"*70)
    print(f"Total jobs: {len(df)}")
    print(f"Completed: {len(df[df['status'] == 'completed'])}")
    print(f"Failed: {len(df[df['status'] == 'failed'])}")
    print(f"Running: {len(df[df['status'] == 'running'])}")
    if 'doping_concentration_percent' in df.columns:
        completed = df[df['status'] == 'completed']
        if len(completed) > 0:
            print(f"\nDoping concentrations: {completed['doping_concentration_percent'].min():.2f}% to {completed['doping_concentration_percent'].max():.2f}%")


if __name__ == "__main__":
    main()
