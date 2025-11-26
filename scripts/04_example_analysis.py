#!/usr/bin/env python3
"""
Example analysis script for doped graphite results
Demonstrates various analysis and visualization techniques
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path

# Optional: matplotlib for plotting
try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # For non-interactive backend
    from scipy import stats
    from sklearn.linear_model import LinearRegression
    HAS_MATPLOTLIB = True
    HAS_SCIPY = True
except ImportError:
    print("Warning: matplotlib/scipy not available. Plotting disabled.")
    HAS_MATPLOTLIB = False
    HAS_SCIPY = False


def load_results(results_file='../03_analysis/results_summary.csv'):
    """Load results from CSV file"""
    df = pd.read_csv(results_file)
    # Filter only completed calculations
    df_complete = df[df['status'] == 'completed'].copy()
    print(f"Loaded {len(df_complete)} completed calculations out of {len(df)} total")
    return df_complete


def analyze_interlayer_spacing(df):
    """Analyze interlayer spacing by dopant and doping type"""
    print("\n" + "="*70)
    print("INTERLAYER SPACING ANALYSIS")
    print("="*70)

    if 'avg_interlayer_spacing' not in df.columns:
        print("No interlayer spacing data available")
        return None

    # Overall statistics
    print("\nOverall Statistics:")
    print(f"  Mean interlayer spacing: {df['avg_interlayer_spacing'].mean():.4f} Å")
    print(f"  Std deviation: {df['avg_interlayer_spacing'].std():.4f} Å")
    print(f"  Min: {df['avg_interlayer_spacing'].min():.4f} Å")
    print(f"  Max: {df['avg_interlayer_spacing'].max():.4f} Å")

    # By dopant element
    if 'dopant' in df.columns:
        print("\n\nBy Dopant Element:")
        print("-"*70)
        spacing_by_dopant = df.groupby('dopant')['avg_interlayer_spacing'].agg(['mean', 'std', 'count'])
        spacing_by_dopant = spacing_by_dopant.sort_values('mean', ascending=False)
        print(spacing_by_dopant.to_string())

    # By doping type
    if 'doping_type' in df.columns:
        print("\n\nBy Doping Type:")
        print("-"*70)
        spacing_by_type = df.groupby('doping_type')['avg_interlayer_spacing'].agg(['mean', 'std', 'count'])
        print(spacing_by_type.to_string())

    # Dopant + Type combination
    if 'dopant' in df.columns and 'doping_type' in df.columns:
        print("\n\nBy Dopant and Doping Type:")
        print("-"*70)
        pivot = df.pivot_table(
            values='avg_interlayer_spacing',
            index='dopant',
            columns='doping_type',
            aggfunc='mean'
        )
        print(pivot.to_string())

    return spacing_by_dopant


def analyze_lattice_parameters(df):
    """Analyze lattice parameters"""
    print("\n" + "="*70)
    print("LATTICE PARAMETER ANALYSIS")
    print("="*70)

    lattice_params = ['a', 'b', 'c', 'volume']
    available_params = [p for p in lattice_params if p in df.columns]

    if not available_params:
        print("No lattice parameter data available")
        return None

    for param in available_params:
        print(f"\n{param.upper()} Parameter:")
        print(f"  Mean: {df[param].mean():.4f}")
        print(f"  Std: {df[param].std():.4f}")
        print(f"  Range: [{df[param].min():.4f}, {df[param].max():.4f}]")

    # c parameter by dopant (most relevant for graphite)
    if 'c' in df.columns and 'dopant' in df.columns:
        print("\n\nc Parameter by Dopant:")
        print("-"*70)
        c_by_dopant = df.groupby('dopant')['c'].agg(['mean', 'std', 'count'])
        c_by_dopant = c_by_dopant.sort_values('mean', ascending=False)
        print(c_by_dopant.to_string())

    return df[available_params].describe()


def analyze_energies(df):
    """Analyze energies and formation energies"""
    print("\n" + "="*70)
    print("ENERGY ANALYSIS")
    print("="*70)

    if 'energy_per_atom' not in df.columns:
        print("No energy data available")
        return None

    print("\nEnergy per Atom:")
    print(f"  Mean: {df['energy_per_atom'].mean():.4f} eV/atom")
    print(f"  Std: {df['energy_per_atom'].std():.4f} eV/atom")
    print(f"  Range: [{df['energy_per_atom'].min():.4f}, {df['energy_per_atom'].max():.4f}] eV/atom")

    # By dopant
    if 'dopant' in df.columns:
        print("\n\nEnergy per Atom by Dopant:")
        print("-"*70)
        energy_by_dopant = df.groupby('dopant')['energy_per_atom'].agg(['mean', 'std', 'count'])
        energy_by_dopant = energy_by_dopant.sort_values('mean')
        print(energy_by_dopant.to_string())

    # Formation energy analysis
    if 'formation_energy_per_atom' in df.columns:
        print("\n\nFormation Energy per Atom:")
        print(f"  Mean: {df['formation_energy_per_atom'].mean():.4f} eV/atom")
        print(f"  Std: {df['formation_energy_per_atom'].std():.4f} eV/atom")

        if 'dopant' in df.columns:
            print("\n\nFormation Energy by Dopant:")
            print("-"*70)
            fe_by_dopant = df.groupby('dopant')['formation_energy_per_atom'].agg(['mean', 'std', 'count'])
            fe_by_dopant = fe_by_dopant.sort_values('mean')
            print(fe_by_dopant.to_string())

            print("\n\nMost Stable Doping Configurations (lowest formation energy):")
            print("-"*70)
            stable = df.nsmallest(10, 'formation_energy_per_atom')[
                ['job_name', 'dopant', 'doping_type', 'formation_energy_per_atom']
            ]
            print(stable.to_string(index=False))

    return energy_by_dopant if 'dopant' in df.columns else None


def identify_graphitization_promoters(df):
    """Identify dopants that promote graphitization (increase interlayer spacing)"""
    print("\n" + "="*70)
    print("GRAPHITIZATION PROMOTERS")
    print("="*70)

    if 'avg_interlayer_spacing' not in df.columns or 'dopant' not in df.columns:
        print("Insufficient data for graphitization analysis")
        return None

    # Calculate average spacing by dopant
    spacing_by_dopant = df.groupby('dopant')['avg_interlayer_spacing'].mean().sort_values(ascending=False)

    print("\nDopants Ranked by Interlayer Spacing (High = Promotes Graphitization):")
    print("-"*70)
    for i, (dopant, spacing) in enumerate(spacing_by_dopant.items(), 1):
        print(f"{i:2d}. {dopant:4s}: {spacing:.4f} Å")

    # Top promoters
    print("\n\nTop 5 Graphitization Promoters:")
    print("-"*70)
    top_promoters = df[df['dopant'].isin(spacing_by_dopant.head(5).index)]
    for dopant in spacing_by_dopant.head(5).index:
        subset = top_promoters[top_promoters['dopant'] == dopant]
        print(f"\n{dopant}:")
        print(f"  Average spacing: {subset['avg_interlayer_spacing'].mean():.4f} Å")
        print(f"  Configurations: {len(subset)}")
        if 'c' in subset.columns:
            print(f"  Average c parameter: {subset['c'].mean():.4f} Å")

    return spacing_by_dopant


def plot_concentration_analysis(df, output_dir='../03_analysis'):
    """
    Plot doping concentration vs various properties with linear regression

    Plots: concentration vs a, c, layer_spacing, volume, formation_energy
    """
    if not HAS_MATPLOTLIB:
        print("\nSkipping concentration plots: matplotlib not available")
        return

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "="*70)
    print("CONCENTRATION ANALYSIS PLOTS")
    print("="*70)

    # Filter only doped structures (exclude pure)
    df_doped = df[df.get('doping_type', '') != 'pure'].copy()

    if 'doping_concentration_percent' not in df_doped.columns:
        print("No doping concentration data available")
        return

    # Remove NaN values
    df_doped = df_doped.dropna(subset=['doping_concentration_percent'])

    if len(df_doped) == 0:
        print("No doped structures with concentration data")
        return

    # Properties to plot
    properties = {
        'a': ('Lattice Parameter a (Å)', 'concentration_vs_a.png'),
        'c': ('Lattice Parameter c (Å)', 'concentration_vs_c.png'),
        'avg_interlayer_spacing': ('Layer Spacing (Å)', 'concentration_vs_spacing.png'),
        'volume': ('Volume (Å³)', 'concentration_vs_volume.png'),
        'formation_energy': ('Formation Energy (eV)', 'concentration_vs_formation_energy.png'),
    }

    regression_results = {}

    for prop, (ylabel, filename) in properties.items():
        if prop not in df_doped.columns:
            print(f"  Skipping {prop}: not in data")
            continue

        # Filter valid data
        df_plot = df_doped.dropna(subset=[prop, 'doping_concentration_percent'])

        if len(df_plot) < 3:
            print(f"  Skipping {prop}: insufficient data points")
            continue

        X = df_plot['doping_concentration_percent'].values.reshape(-1, 1)
        y = df_plot[prop].values

        # Create figure
        fig, ax = plt.subplots(figsize=(10, 7))

        # Color by dopant if available
        if 'dopant' in df_plot.columns:
            dopants = df_plot['dopant'].unique()
            colors = plt.cm.tab10(np.linspace(0, 1, len(dopants)))

            for dopant, color in zip(dopants, colors):
                subset = df_plot[df_plot['dopant'] == dopant]
                ax.scatter(
                    subset['doping_concentration_percent'],
                    subset[prop],
                    label=dopant,
                    s=100,
                    alpha=0.7,
                    color=color,
                    edgecolors='black',
                    linewidths=0.5
                )
        else:
            ax.scatter(X, y, s=100, alpha=0.7, edgecolors='black', linewidths=0.5)

        # Linear regression
        if HAS_SCIPY and len(df_plot) >= 3:
            model = LinearRegression()
            model.fit(X, y)
            y_pred = model.predict(X)

            # Calculate R²
            slope = model.coef_[0]
            intercept = model.intercept_
            r_squared = model.score(X, y)

            # Plot regression line
            x_line = np.linspace(X.min(), X.max(), 100).reshape(-1, 1)
            y_line = model.predict(x_line)
            ax.plot(x_line, y_line, 'r--', linewidth=2,
                   label=f'Linear fit: y={slope:.4f}x+{intercept:.4f}\nR²={r_squared:.4f}')

            # Store regression results
            regression_results[prop] = {
                'slope': slope,
                'intercept': intercept,
                'r_squared': r_squared,
                'n_points': len(df_plot)
            }

            print(f"  {prop}: slope={slope:.4f}, R²={r_squared:.4f}")

        ax.set_xlabel('Doping Concentration (%)', fontsize=12, fontweight='bold')
        ax.set_ylabel(ylabel, fontsize=12, fontweight='bold')
        ax.set_title(f'Doping Concentration vs {ylabel.split("(")[0].strip()}',
                    fontsize=14, fontweight='bold')
        ax.legend(fontsize=9)
        ax.grid(alpha=0.3)
        plt.tight_layout()

        plot_path = output_dir / filename
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {plot_path}")
        plt.close()

    # Save regression results to JSON
    if regression_results:
        regression_path = output_dir / 'concentration_regression_results.json'
        with open(regression_path, 'w') as f:
            json.dump(regression_results, f, indent=2)
        print(f"\n✓ Regression results saved to: {regression_path}")

    return regression_results


def create_plots(df, output_dir='../03_analysis'):
    """Create visualization plots"""
    if not HAS_MATPLOTLIB:
        print("\nSkipping plots: matplotlib not available")
        return

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "="*70)
    print("CREATING PLOTS")
    print("="*70)

    # Plot 1: Interlayer spacing by dopant
    if 'dopant' in df.columns and 'avg_interlayer_spacing' in df.columns:
        fig, ax = plt.subplots(figsize=(10, 6))
        spacing_by_dopant = df.groupby('dopant')['avg_interlayer_spacing'].mean().sort_values()
        spacing_by_dopant.plot(kind='barh', ax=ax, color='steelblue')
        ax.set_xlabel('Average Interlayer Spacing (Å)', fontsize=12)
        ax.set_ylabel('Dopant Element', fontsize=12)
        ax.set_title('Effect of Doping on Graphite Interlayer Spacing', fontsize=14, fontweight='bold')
        ax.grid(axis='x', alpha=0.3)
        plt.tight_layout()
        plot_path = output_dir / 'interlayer_spacing_by_dopant.png'
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {plot_path}")
        plt.close()

    # Plot 2: Comparison by doping type
    if 'dopant' in df.columns and 'doping_type' in df.columns and 'avg_interlayer_spacing' in df.columns:
        fig, ax = plt.subplots(figsize=(12, 6))
        pivot = df.pivot_table(
            values='avg_interlayer_spacing',
            index='dopant',
            columns='doping_type',
            aggfunc='mean'
        )

        # Sort by first column if available
        if len(pivot.columns) > 0:
            pivot = pivot.sort_values(by=pivot.columns[0])

        pivot.plot(kind='bar', ax=ax, width=0.8)
        ax.set_xlabel('Dopant Element', fontsize=12)
        ax.set_ylabel('Interlayer Spacing (Å)', fontsize=12)
        ax.set_title('Substitutional vs Interstitial Doping Effects', fontsize=14, fontweight='bold')
        ax.legend(title='Doping Type', fontsize=10)
        ax.grid(axis='y', alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plot_path = output_dir / 'doping_type_comparison.png'
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {plot_path}")
        plt.close()

    # Plot 3: Formation energy vs interlayer spacing
    if 'formation_energy_per_atom' in df.columns and 'avg_interlayer_spacing' in df.columns:
        fig, ax = plt.subplots(figsize=(10, 8))

        if 'dopant' in df.columns:
            dopants = df['dopant'].unique()
            colors = plt.cm.tab10(np.linspace(0, 1, len(dopants)))

            for dopant, color in zip(dopants, colors):
                subset = df[df['dopant'] == dopant]
                ax.scatter(
                    subset['formation_energy_per_atom'],
                    subset['avg_interlayer_spacing'],
                    label=dopant,
                    s=100,
                    alpha=0.7,
                    color=color
                )
        else:
            ax.scatter(
                df['formation_energy_per_atom'],
                df['avg_interlayer_spacing'],
                s=100,
                alpha=0.7
            )

        ax.set_xlabel('Formation Energy per Atom (eV/atom)', fontsize=12)
        ax.set_ylabel('Interlayer Spacing (Å)', fontsize=12)
        ax.set_title('Formation Energy vs Interlayer Spacing', fontsize=14, fontweight='bold')
        ax.legend(fontsize=9, ncol=2)
        ax.grid(alpha=0.3)
        plt.tight_layout()
        plot_path = output_dir / 'energy_vs_spacing.png'
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {plot_path}")
        plt.close()

    print("\nAll plots saved to:", output_dir)


def export_key_findings(df, output_dir='../03_analysis'):
    """Export key findings to a JSON file"""
    output_dir = Path(output_dir)
    findings = {}

    # Overall statistics
    if 'avg_interlayer_spacing' in df.columns:
        findings['interlayer_spacing'] = {
            'mean': float(df['avg_interlayer_spacing'].mean()),
            'std': float(df['avg_interlayer_spacing'].std()),
            'min': float(df['avg_interlayer_spacing'].min()),
            'max': float(df['avg_interlayer_spacing'].max()),
        }

    # Best promoters
    if 'dopant' in df.columns and 'avg_interlayer_spacing' in df.columns:
        spacing_by_dopant = df.groupby('dopant')['avg_interlayer_spacing'].mean().sort_values(ascending=False)
        findings['top_graphitization_promoters'] = {
            dopant: float(spacing)
            for dopant, spacing in spacing_by_dopant.head(5).items()
        }

    # Most stable
    if 'formation_energy_per_atom' in df.columns:
        most_stable = df.nsmallest(5, 'formation_energy_per_atom')
        findings['most_stable_configurations'] = [
            {
                'job_name': row['job_name'],
                'dopant': row.get('dopant', 'unknown'),
                'doping_type': row.get('doping_type', 'unknown'),
                'formation_energy': float(row['formation_energy_per_atom']),
            }
            for _, row in most_stable.iterrows()
        ]

    # Save
    findings_path = output_dir / 'key_findings.json'
    with open(findings_path, 'w') as f:
        json.dump(findings, f, indent=2)

    print(f"\n✓ Key findings saved to: {findings_path}")
    return findings


def main():
    """Main analysis workflow"""
    print("="*70)
    print("EXAMPLE ANALYSIS: Doped Graphite High-Throughput Study")
    print("="*70)

    # Load results
    try:
        df = load_results()
    except FileNotFoundError:
        print("\nError: Results file not found!")
        print("Please run 03_extract_results.py first")
        return

    if len(df) == 0:
        print("\nNo completed calculations found. Nothing to analyze.")
        return

    # Run analyses
    analyze_interlayer_spacing(df)
    analyze_lattice_parameters(df)
    analyze_energies(df)
    identify_graphitization_promoters(df)

    # Concentration analysis with linear regression
    plot_concentration_analysis(df)

    # Create plots
    create_plots(df)

    # Export findings
    export_key_findings(df)

    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)
    print("\nGenerated files in 03_analysis/:")
    print("  - interlayer_spacing_by_dopant.png")
    print("  - doping_type_comparison.png")
    print("  - energy_vs_spacing.png")
    print("  - key_findings.json")


if __name__ == "__main__":
    main()
