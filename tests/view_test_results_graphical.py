"""
Graphical visualization tool for test results.
Creates interactive charts and graphs to visualize test performance over time.
"""
import json
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import argparse

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.gridspec import GridSpec
    import numpy as np
except ImportError:
    print("Error: matplotlib is required for graphical visualization.")
    print("Install it with: pip install matplotlib")
    sys.exit(1)


def load_all_results(results_dir: Path) -> List[Dict]:
    """Load all test result files from directory."""
    results = []
    
    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        return results
    
    for result_file in sorted(results_dir.glob("test_results*.json"), reverse=True):
        try:
            with open(result_file, 'r') as f:
                data = json.load(f)
                data['_filename'] = result_file.name
                data['_filepath'] = str(result_file)
                results.append(data)
        except Exception as e:
            print(f"Error loading {result_file}: {e}")
    
    return results


def create_summary_dashboard(results: List[Dict], output_file: Optional[str] = None):
    """Create a comprehensive dashboard with multiple visualizations."""
    if not results:
        print("No test results found.")
        return
    
    # Sort by timestamp (oldest first for time series)
    results_sorted = sorted(results, key=lambda x: x.get('timestamp', ''))
    
    # Create figure with subplots
    fig = plt.figure(figsize=(16, 12))
    gs = GridSpec(3, 3, figure=fig, hspace=0.3, wspace=0.3)
    
    # 1. Pass Rate Over Time (top left)
    ax1 = fig.add_subplot(gs[0, 0])
    plot_pass_rate_trend(results_sorted, ax1)
    
    # 2. Execution Time Over Time (top middle)
    ax2 = fig.add_subplot(gs[0, 1])
    plot_execution_time_trend(results_sorted, ax2)
    
    # 3. Test Counts (top right)
    ax3 = fig.add_subplot(gs[0, 2])
    plot_test_counts(results_sorted, ax3)
    
    # 4. Test-by-Test Pass Rates (middle left, spans 2 columns)
    ax4 = fig.add_subplot(gs[1, :2])
    plot_test_by_test_pass_rates(results_sorted, ax4)
    
    # 5. Criteria Failure Breakdown (middle right)
    ax5 = fig.add_subplot(gs[1, 2])
    plot_criteria_failures(results_sorted, ax5)
    
    # 6. Latest Run Details (bottom, spans full width)
    ax6 = fig.add_subplot(gs[2, :])
    plot_latest_run_details(results_sorted[-1], ax6)
    
    # Add title
    fig.suptitle('CineMind Test Results Dashboard', fontsize=16, fontweight='bold', y=0.995)
    
    # Save or show
    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"Dashboard saved to: {output_file}")
    else:
        plt.show()


def plot_pass_rate_trend(results: List[Dict], ax):
    """Plot pass rate over time."""
    timestamps = []
    pass_rates = []
    
    for result in results:
        timestamp_str = result.get('timestamp', '')
        try:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            timestamps.append(dt)
            summary = result.get('summary', {})
            pass_rates.append(summary.get('pass_rate', 0) * 100)
        except:
            continue
    
    if timestamps:
        ax.plot(timestamps, pass_rates, marker='o', linewidth=2, markersize=8, color='#2ecc71')
        ax.axhline(y=100, color='green', linestyle='--', alpha=0.3, label='100% Target')
        ax.axhline(y=80, color='orange', linestyle='--', alpha=0.3, label='80% Threshold')
        ax.set_xlabel('Date')
        ax.set_ylabel('Pass Rate (%)')
        ax.set_title('Pass Rate Over Time', fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend()
        ax.set_ylim(0, 105)
        
        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    else:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        ax.set_title('Pass Rate Over Time', fontweight='bold')


def plot_execution_time_trend(results: List[Dict], ax):
    """Plot average execution time over time."""
    timestamps = []
    exec_times = []
    
    for result in results:
        timestamp_str = result.get('timestamp', '')
        try:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            timestamps.append(dt)
            summary = result.get('summary', {})
            exec_times.append(summary.get('avg_execution_time_ms', 0))
        except:
            continue
    
    if timestamps:
        ax.plot(timestamps, exec_times, marker='s', linewidth=2, markersize=8, color='#3498db')
        ax.set_xlabel('Date')
        ax.set_ylabel('Avg Execution Time (ms)')
        ax.set_title('Execution Time Over Time', fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    else:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        ax.set_title('Execution Time Over Time', fontweight='bold')


def plot_test_counts(results: List[Dict], ax):
    """Plot test counts (passed/failed) for latest run."""
    if not results:
        return
    
    latest = results[-1]
    summary = latest.get('summary', {})
    passed = summary.get('passed', 0)
    failed = summary.get('failed', 0)
    
    if passed + failed > 0:
        colors = ['#2ecc71', '#e74c3c']
        labels = ['Passed', 'Failed']
        sizes = [passed, failed]
        
        wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%',
                                          startangle=90, textprops={'fontsize': 10, 'fontweight': 'bold'})
        ax.set_title(f'Latest Run: {passed + failed} Tests', fontweight='bold')
        
        # Make percentage text white for better visibility
        for autotext in autotexts:
            autotext.set_color('white')
    else:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        ax.set_title('Test Counts', fontweight='bold')


def plot_test_by_test_pass_rates(results: List[Dict], ax):
    """Plot pass rate for each individual test across all runs."""
    # Collect all unique test names
    test_names = set()
    for result in results:
        for test_result in result.get('results', []):
            test_names.add(test_result.get('test_name', 'Unknown'))
    
    if not test_names:
        ax.text(0.5, 0.5, 'No test data available', ha='center', va='center', transform=ax.transAxes)
        ax.set_title('Test-by-Test Pass Rates', fontweight='bold')
        return
    
    # Calculate pass rate for each test
    test_pass_rates = {}
    for test_name in test_names:
        passed_count = 0
        total_count = 0
        for result in results:
            for test_result in result.get('results', []):
                if test_result.get('test_name') == test_name:
                    total_count += 1
                    if test_result.get('passed', False):
                        passed_count += 1
        if total_count > 0:
            test_pass_rates[test_name] = (passed_count / total_count) * 100
    
    if test_pass_rates:
        # Sort by pass rate
        sorted_tests = sorted(test_pass_rates.items(), key=lambda x: x[1])
        test_names_sorted = [t[0] for t in sorted_tests]
        pass_rates_sorted = [t[1] for t in sorted_tests]
        
        # Create horizontal bar chart
        colors = ['#2ecc71' if rate == 100 else '#f39c12' if rate >= 50 else '#e74c3c' 
                 for rate in pass_rates_sorted]
        bars = ax.barh(test_names_sorted, pass_rates_sorted, color=colors, alpha=0.8)
        
        # Add value labels on bars
        for i, (bar, rate) in enumerate(zip(bars, pass_rates_sorted)):
            ax.text(rate + 1, i, f'{rate:.0f}%', va='center', fontweight='bold', fontsize=9)
        
        ax.set_xlabel('Pass Rate (%)')
        ax.set_title('Test-by-Test Pass Rates (Across All Runs)', fontweight='bold')
        ax.set_xlim(0, 105)
        ax.grid(True, alpha=0.3, axis='x')
        ax.invert_yaxis()  # Show highest pass rate at top
    else:
        ax.text(0.5, 0.5, 'No test data available', ha='center', va='center', transform=ax.transAxes)
        ax.set_title('Test-by-Test Pass Rates', fontweight='bold')


def plot_criteria_failures(results: List[Dict], ax):
    """Plot breakdown of which criteria fail most often."""
    criteria_failures = {}
    
    for result in results:
        for test_result in result.get('results', []):
            if not test_result.get('passed', True):
                for criterion_name, passed, message in test_result.get('criteria_results', []):
                    if not passed:
                        criteria_failures[criterion_name] = criteria_failures.get(criterion_name, 0) + 1
    
    if criteria_failures:
        # Sort by failure count
        sorted_criteria = sorted(criteria_failures.items(), key=lambda x: x[1], reverse=True)
        criteria_names = [c[0] for c in sorted_criteria]
        failure_counts = [c[1] for c in sorted_criteria]
        
        # Create bar chart
        colors = plt.cm.Reds(np.linspace(0.4, 0.8, len(criteria_names)))
        bars = ax.barh(criteria_names, failure_counts, color=colors, alpha=0.8)
        
        # Add value labels
        for i, (bar, count) in enumerate(zip(bars, failure_counts)):
            ax.text(count + 0.1, i, str(count), va='center', fontweight='bold', fontsize=9)
        
        ax.set_xlabel('Failure Count')
        ax.set_title('Criteria Failure Breakdown', fontweight='bold')
        ax.grid(True, alpha=0.3, axis='x')
        ax.invert_yaxis()
    else:
        ax.text(0.5, 0.5, 'No failures found!', ha='center', va='center', transform=ax.transAxes,
               fontsize=12, color='green', fontweight='bold')
        ax.set_title('Criteria Failure Breakdown', fontweight='bold')


def plot_latest_run_details(latest_result: Dict, ax):
    """Plot detailed breakdown of latest test run."""
    ax.axis('off')
    
    summary = latest_result.get('summary', {})
    timestamp = latest_result.get('timestamp', 'Unknown')
    
    # Parse timestamp
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        time_str = timestamp
    
    # Create text summary
    text_lines = [
        f"Latest Test Run: {time_str}",
        f"",
        f"Summary:",
        f"  Total Tests: {summary.get('total_tests', 0)}",
        f"  Passed: {summary.get('passed', 0)}",
        f"  Failed: {summary.get('failed', 0)}",
        f"  Pass Rate: {summary.get('pass_rate', 0):.1%}",
        f"  Avg Execution Time: {summary.get('avg_execution_time_ms', 0):.2f}ms",
        f"",
        f"Individual Test Results:",
    ]
    
    # Add individual test results
    for test_result in latest_result.get('results', []):
        status = "✓ PASS" if test_result.get('passed') else "✗ FAIL"
        test_name = test_result.get('test_name', 'Unknown')
        exec_time = test_result.get('execution_time_ms', 0)
        text_lines.append(f"  {status} {test_name} ({exec_time:.0f}ms)")
        
        # Show failed criteria
        if not test_result.get('passed'):
            for criterion_name, passed, message in test_result.get('criteria_results', []):
                if not passed:
                    text_lines.append(f"      - {criterion_name}: {message}")
    
    text_content = '\n'.join(text_lines)
    ax.text(0.05, 0.95, text_content, transform=ax.transAxes, fontsize=9,
           verticalalignment='top', family='monospace',
           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))


def create_comparison_chart(results: List[Dict], limit: int = 5, output_file: Optional[str] = None):
    """Create a comparison chart of the last N test runs."""
    if len(results) < 2:
        print("Need at least 2 test runs to compare.")
        return
    
    recent = results[:limit]
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f'Comparison of Last {len(recent)} Test Runs', fontsize=14, fontweight='bold')
    
    # 1. Pass Rate Comparison
    ax1 = axes[0, 0]
    run_labels = [r.get('_filename', 'Unknown')[:20] for r in recent]
    pass_rates = [r.get('summary', {}).get('pass_rate', 0) * 100 for r in recent]
    colors = ['#2ecc71' if rate == 100 else '#f39c12' if rate >= 50 else '#e74c3c' for rate in pass_rates]
    bars = ax1.bar(range(len(recent)), pass_rates, color=colors, alpha=0.8)
    ax1.set_xticks(range(len(recent)))
    ax1.set_xticklabels([f"Run {i+1}" for i in range(len(recent))], rotation=45, ha='right')
    ax1.set_ylabel('Pass Rate (%)')
    ax1.set_title('Pass Rate Comparison', fontweight='bold')
    ax1.set_ylim(0, 105)
    ax1.grid(True, alpha=0.3, axis='y')
    for i, (bar, rate) in enumerate(zip(bars, pass_rates)):
        ax1.text(bar.get_x() + bar.get_width()/2, rate + 1, f'{rate:.0f}%',
                ha='center', va='bottom', fontweight='bold')
    
    # 2. Execution Time Comparison
    ax2 = axes[0, 1]
    exec_times = [r.get('summary', {}).get('avg_execution_time_ms', 0) for r in recent]
    bars = ax2.bar(range(len(recent)), exec_times, color='#3498db', alpha=0.8)
    ax2.set_xticks(range(len(recent)))
    ax2.set_xticklabels([f"Run {i+1}" for i in range(len(recent))], rotation=45, ha='right')
    ax2.set_ylabel('Avg Execution Time (ms)')
    ax2.set_title('Execution Time Comparison', fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')
    for i, (bar, time) in enumerate(zip(bars, exec_times)):
        ax2.text(bar.get_x() + bar.get_width()/2, time + max(exec_times)*0.01,
                f'{time:.0f}ms', ha='center', va='bottom', fontweight='bold', fontsize=8)
    
    # 3. Test Count Comparison
    ax3 = axes[1, 0]
    passed_counts = [r.get('summary', {}).get('passed', 0) for r in recent]
    failed_counts = [r.get('summary', {}).get('failed', 0) for r in recent]
    x = np.arange(len(recent))
    width = 0.35
    bars1 = ax3.bar(x - width/2, passed_counts, width, label='Passed', color='#2ecc71', alpha=0.8)
    bars2 = ax3.bar(x + width/2, failed_counts, width, label='Failed', color='#e74c3c', alpha=0.8)
    ax3.set_xticks(x)
    ax3.set_xticklabels([f"Run {i+1}" for i in range(len(recent))], rotation=45, ha='right')
    ax3.set_ylabel('Test Count')
    ax3.set_title('Passed vs Failed Tests', fontweight='bold')
    ax3.legend()
    ax3.grid(True, alpha=0.3, axis='y')
    
    # 4. Test-by-Test Comparison (heatmap style)
    ax4 = axes[1, 1]
    # Get all unique test names
    all_test_names = set()
    for result in recent:
        for test in result.get('results', []):
            all_test_names.add(test.get('test_name'))
    
    if all_test_names:
        test_names = sorted(all_test_names)
        # Create matrix: rows = tests, columns = runs
        matrix = []
        for test_name in test_names:
            row = []
            for result in recent:
                test_result = next(
                    (t for t in result.get('results', []) if t.get('test_name') == test_name),
                    None
                )
                # 1 = pass, 0 = fail, -1 = not found
                if test_result:
                    row.append(1 if test_result.get('passed') else 0)
                else:
                    row.append(-1)
            matrix.append(row)
        
        # Create heatmap
        im = ax4.imshow(matrix, cmap='RdYlGn', aspect='auto', vmin=-1, vmax=1)
        ax4.set_xticks(range(len(recent)))
        ax4.set_xticklabels([f"Run {i+1}" for i in range(len(recent))])
        ax4.set_yticks(range(len(test_names)))
        ax4.set_yticklabels(test_names, fontsize=8)
        ax4.set_title('Test-by-Test Status (Green=Pass, Red=Fail)', fontweight='bold')
        
        # Add colorbar
        cbar = plt.colorbar(im, ax=ax4, ticks=[-1, 0, 1])
        cbar.set_ticklabels(['N/A', 'Fail', 'Pass'])
    else:
        ax4.text(0.5, 0.5, 'No test data available', ha='center', va='center', transform=ax4.transAxes)
        ax4.set_title('Test-by-Test Status', fontweight='bold')
    
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"Comparison chart saved to: {output_file}")
    else:
        plt.show()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="View test results graphically")
    parser.add_argument(
        '--dir',
        default='data/test_results',
        help='Directory containing test results (default: data/test_results)'
    )
    parser.add_argument(
        '--dashboard',
        action='store_true',
        help='Show comprehensive dashboard (default)'
    )
    parser.add_argument(
        '--compare',
        type=int,
        metavar='N',
        help='Compare last N test runs (default: 5)'
    )
    parser.add_argument(
        '--output',
        help='Output file to save chart (e.g., dashboard.png)'
    )
    
    args = parser.parse_args()
    
    # Get results directory (relative to project root)
    project_root = Path(__file__).parent.parent
    results_dir = project_root / args.dir if not Path(args.dir).is_absolute() else Path(args.dir)
    
    # Load all results
    results = load_all_results(results_dir)
    
    if not results:
        print(f"No test results found in {results_dir}")
        return
    
    # Sort by timestamp (newest first)
    results = sorted(results, key=lambda x: x.get('timestamp', ''), reverse=True)
    
    # Handle different modes
    if args.compare:
        create_comparison_chart(results, limit=args.compare, output_file=args.output)
    else:
        # Default: show dashboard
        create_summary_dashboard(results, output_file=args.output)


if __name__ == "__main__":
    main()

