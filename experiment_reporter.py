import json
import yaml
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import shutil
import numpy as np

from freight_model import FreightBrokerageModel
from config_loader import ConfigLoader


class ExperimentReporter:
    """
    Generates comprehensive experiment reports including plots, data exports,
    and configuration documentation for ABM simulation runs.
    """
    
    def __init__(self, output_dir: str = "experiments"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.experiment_dir = None
        self.experiment_name = None
        
    def create_experiment_directory(self, scenario_name: Optional[str] = None) -> Path:
        """Create timestamped experiment directory."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        if scenario_name:
            self.experiment_name = f"{scenario_name}_{timestamp}"
        else:
            self.experiment_name = f"baseline_{timestamp}"
            
        self.experiment_dir = self.output_dir / self.experiment_name
        self.experiment_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        (self.experiment_dir / "plots").mkdir(exist_ok=True)
        
        return self.experiment_dir
    
    def save_config(self, config_loader: ConfigLoader, scenario: Optional[str] = None):
        """Save the configuration used for this experiment."""
        if not self.experiment_dir:
            raise ValueError("Must create experiment directory first")
            
        # Save the exact config used
        config_path = self.experiment_dir / "config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config_loader._current_config, f, default_flow_style=False, indent=2)
        
        # Also save metadata about the experiment
        metadata = {
            "experiment_name": self.experiment_name,
            "scenario": scenario or "baseline",
            "timestamp": datetime.now().isoformat(),
            "description": "ABM freight brokerage simulation experiment"
        }
        
        metadata_path = self.experiment_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def extract_timeseries_data(self, model: FreightBrokerageModel) -> pd.DataFrame:
        """Extract time series data from model's datacollector."""
        model_data = model.datacollector.get_model_vars_dataframe()
        
        # Reset index to make Step a column
        model_data = model_data.reset_index()
        
        # The index column name might be different, let's rename it to 'Step'
        if 'index' in model_data.columns:
            model_data = model_data.rename(columns={'index': 'Step'})
        elif model_data.index.name:
            model_data = model_data.reset_index()
            if 'Step' not in model_data.columns and len(model_data.columns) > 0:
                # Find the first integer column that looks like steps
                for col in model_data.columns:
                    if model_data[col].dtype in ['int64', 'int32'] and (model_data[col] == range(len(model_data))).all():
                        model_data = model_data.rename(columns={col: 'Step'})
                        break
        
        # If still no Step column, create one
        if 'Step' not in model_data.columns:
            model_data['Step'] = range(len(model_data))
        
        # Add derived metrics
        model_data['Week'] = model_data['Step'] // model.steps_per_week
        model_data['Profit_Margin'] = (model_data['Broker_Profit'] / model_data['Total_Revenue'].replace(0, np.nan)) * 100
        model_data['Load_Success_Rate'] = model_data['Completed_Loads'] / (model_data['Completed_Loads'] + model_data['Expired_Loads']).replace(0, np.nan)
        
        return model_data
    
    def generate_summary_metrics(self, model: FreightBrokerageModel, timeseries_df: pd.DataFrame) -> Dict[str, Any]:
        """Generate summary statistics for the experiment."""
        final_step = timeseries_df.iloc[-1]
        
        summary = {
            # Simulation parameters
            "simulation": {
                "total_steps": len(timeseries_df),
                "total_weeks": final_step['Week'],
                "num_carriers": len(model.carriers),
                "scenario": getattr(model, '_scenario_name', 'baseline')
            },
            
            # Final performance metrics
            "final_metrics": {
                "coverage_rate": float(final_step['Coverage_Rate']),
                "total_loads_covered": int(final_step['Completed_Loads']),
                "total_loads_expired": int(final_step['Expired_Loads']),
                "broker_profit": float(final_step['Broker_Profit']),
                "total_revenue": float(final_step['Total_Revenue']),
                "total_cost": float(final_step['Total_Cost']),
                "total_penalties": float(final_step['Total_Penalties']),
                "avg_carrier_revenue": float(final_step['Average_Carrier_Revenue']),
                "consecutive_failures": int(final_step['Consecutive_Failures'])
            },
            
            # Performance trends (last 25% of simulation)
            "performance_trends": {},
            
            # Market efficiency metrics
            "market_metrics": {
                "avg_utilization_rate": float(timeseries_df['Available_Carriers'].mean() / len(model.carriers)),
                "profit_margin_avg": float(timeseries_df['Profit_Margin'].mean()),
                "load_generation_total": int(final_step['Completed_Loads'] + final_step['Expired_Loads'])
            }
        }
        
        # Calculate trends for last quarter of simulation
        last_quarter = timeseries_df.iloc[-len(timeseries_df)//4:]
        if len(last_quarter) > 1:
            summary["performance_trends"] = {
                "coverage_rate_trend": float(last_quarter['Coverage_Rate'].mean()),
                "profit_growth_rate": float((last_quarter['Broker_Profit'].iloc[-1] - last_quarter['Broker_Profit'].iloc[0]) / len(last_quarter)),
                "carrier_revenue_growth": float((last_quarter['Average_Carrier_Revenue'].iloc[-1] - last_quarter['Average_Carrier_Revenue'].iloc[0]) / len(last_quarter))
            }
        
        return summary
    
    def create_plots(self, timeseries_df: pd.DataFrame, summary: Dict[str, Any]):
        """Generate visualization plots for the experiment."""
        if not self.experiment_dir:
            raise ValueError("Must create experiment directory first")
            
        plots_dir = self.experiment_dir / "plots"
        
        # Set style for consistent, professional plots
        plt.style.use('default')
        plt.rcParams['figure.figsize'] = (12, 8)
        plt.rcParams['font.size'] = 10
        
        # 1. Coverage Rate and Load Dynamics
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        ax1.plot(timeseries_df['Step'], timeseries_df['Coverage_Rate'] * 100, 'b-', linewidth=2, label='Coverage Rate')
        ax1.set_ylabel('Coverage Rate (%)', fontsize=12)
        ax1.set_title('Load Coverage Performance Over Time', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        ax1.set_ylim([0, 105])
        
        ax2.plot(timeseries_df['Step'], timeseries_df['Active_Loads'], 'r-', linewidth=2, label='Active Loads')
        ax2.plot(timeseries_df['Step'], timeseries_df['Completed_Loads'], 'g-', linewidth=2, label='Completed Loads')
        ax2.plot(timeseries_df['Step'], timeseries_df['Expired_Loads'], 'orange', linewidth=2, label='Expired Loads')
        ax2.set_xlabel('Simulation Step', fontsize=12)
        ax2.set_ylabel('Number of Loads', fontsize=12)
        ax2.set_title('Load Dynamics', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        
        plt.tight_layout()
        plt.savefig(plots_dir / "load_dynamics.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        # 2. Profit and Revenue Analysis
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        ax1.plot(timeseries_df['Step'], timeseries_df['Broker_Profit'], 'g-', linewidth=2, label='Broker Profit')
        ax1.plot(timeseries_df['Step'], timeseries_df['Total_Revenue'], 'b-', linewidth=2, label='Total Revenue')
        ax1.plot(timeseries_df['Step'], timeseries_df['Total_Cost'], 'r-', linewidth=2, label='Total Cost')
        ax1.set_ylabel('Amount ($)', fontsize=12)
        ax1.set_title('Financial Performance Over Time', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        
        ax2.plot(timeseries_df['Step'], timeseries_df['Average_Carrier_Revenue'], 'purple', linewidth=2, label='Avg Carrier Revenue')
        if not timeseries_df['Total_Penalties'].eq(0).all():
            ax2.plot(timeseries_df['Step'], timeseries_df['Total_Penalties'], 'orange', linewidth=2, label='Total Penalties')
        ax2.set_xlabel('Simulation Step', fontsize=12)
        ax2.set_ylabel('Amount ($)', fontsize=12)
        ax2.set_title('Carrier Performance and Penalties', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        
        plt.tight_layout()
        plt.savefig(plots_dir / "financial_performance.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        # 3. Market Utilization
        fig, ax = plt.subplots(figsize=(12, 6))
        
        utilization_rate = (len(timeseries_df.columns) - timeseries_df['Available_Carriers']) / summary['simulation']['num_carriers'] * 100
        ax.plot(timeseries_df['Step'], utilization_rate, 'navy', linewidth=2, label='Carrier Utilization Rate')
        ax.fill_between(timeseries_df['Step'], utilization_rate, alpha=0.3, color='navy')
        ax.set_xlabel('Simulation Step', fontsize=12)
        ax.set_ylabel('Utilization Rate (%)', fontsize=12)
        ax.set_title('Carrier Market Utilization', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend()
        ax.set_ylim([0, 100])
        
        plt.tight_layout()
        plt.savefig(plots_dir / "market_utilization.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        # 4. Performance Summary Dashboard
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
        
        # Coverage rate histogram
        ax1.hist(timeseries_df['Coverage_Rate'] * 100, bins=20, color='skyblue', alpha=0.7, edgecolor='black')
        ax1.set_xlabel('Coverage Rate (%)')
        ax1.set_ylabel('Frequency')
        ax1.set_title('Coverage Rate Distribution')
        ax1.grid(True, alpha=0.3)
        
        # Profit margin over time
        ax2.plot(timeseries_df['Step'], timeseries_df['Profit_Margin'], 'green', linewidth=2)
        ax2.set_xlabel('Simulation Step')
        ax2.set_ylabel('Profit Margin (%)')
        ax2.set_title('Profit Margin Trend')
        ax2.grid(True, alpha=0.3)
        
        # Consecutive failures
        ax3.plot(timeseries_df['Step'], timeseries_df['Consecutive_Failures'], 'red', linewidth=2)
        ax3.set_xlabel('Simulation Step')
        ax3.set_ylabel('Consecutive Failures')
        ax3.set_title('Risk Indicator: Consecutive Failures')
        ax3.grid(True, alpha=0.3)
        
        # Weekly performance
        weekly_data = timeseries_df.groupby('Week').agg({
            'Completed_Loads': 'sum',
            'Broker_Profit': 'last'
        }).reset_index()
        
        ax4.bar(weekly_data['Week'], weekly_data['Completed_Loads'], color='lightcoral', alpha=0.7)
        ax4.set_xlabel('Week')
        ax4.set_ylabel('Loads Completed')
        ax4.set_title('Weekly Load Completion')
        ax4.grid(True, alpha=0.3)
        
        plt.suptitle(f'Experiment Dashboard: {self.experiment_name}', fontsize=16, fontweight='bold')
        plt.tight_layout()
        plt.savefig(plots_dir / "dashboard.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def generate_markdown_report(self, summary: Dict[str, Any], config_loader: ConfigLoader, scenario: Optional[str] = None):
        """Generate a human-readable markdown report."""
        if not self.experiment_dir:
            raise ValueError("Must create experiment directory first")
            
        report_path = self.experiment_dir / "report.md"
        
        with open(report_path, 'w') as f:
            f.write(f"# Freight Brokerage ABM Experiment Report\n\n")
            f.write(f"**Experiment:** {self.experiment_name}  \n")
            f.write(f"**Scenario:** {scenario or 'baseline'}  \n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n\n")
            
            # Configuration summary
            f.write("## Configuration\n\n")
            sim_params = config_loader.get_simulation_params()
            broker_params = config_loader.get_broker_params()
            carrier_params = config_loader.get_carrier_params()
            load_params = config_loader.get_load_params()
            
            f.write(f"- **Carriers:** {sim_params['num_carriers']}\n")
            f.write(f"- **Grid Size:** {sim_params['grid_size']}x{sim_params['grid_size']}\n")
            f.write(f"- **Load Generation Rate:** {sim_params['load_generation_rate']} per step\n")
            f.write(f"- **Market Volatility:** ±{sim_params['weekly_volume_variation']*100}%\n")
            f.write(f"- **Broker Patience:** {broker_params['patience_factor']}\n")
            f.write(f"- **Max Negotiation Rounds:** {broker_params['max_negotiation_rounds']}\n")
            f.write(f"- **Penalty Rate:** {load_params['penalty_rate']*100}%\n\n")
            
            # Performance Summary
            f.write("## Performance Summary\n\n")
            final = summary['final_metrics']
            f.write(f"| Metric | Value |\n")
            f.write(f"|--------|-------|\n")
            f.write(f"| Coverage Rate | {final['coverage_rate']*100:.1f}% |\n")
            f.write(f"| Total Loads Covered | {final['total_loads_covered']:,} |\n")
            f.write(f"| Total Loads Expired | {final['total_loads_expired']:,} |\n")
            f.write(f"| Broker Profit | ${final['broker_profit']:,.0f} |\n")
            f.write(f"| Total Revenue | ${final['total_revenue']:,.0f} |\n")
            f.write(f"| Avg Carrier Revenue | ${final['avg_carrier_revenue']:,.0f} |\n")
            f.write(f"| Consecutive Failures | {final['consecutive_failures']} |\n\n")
            
            # Market Analysis
            f.write("## Market Analysis\n\n")
            market = summary['market_metrics']
            f.write(f"- **Average Carrier Utilization:** {(1-market['avg_utilization_rate'])*100:.1f}%\n")
            f.write(f"- **Average Profit Margin:** {market['profit_margin_avg']:.1f}%\n")
            f.write(f"- **Total Load Volume:** {market['load_generation_total']:,} loads\n\n")
            
            # Performance Trends
            if summary['performance_trends']:
                f.write("## Performance Trends (Final Quarter)\n\n")
                trends = summary['performance_trends']
                f.write(f"- **Average Coverage Rate:** {trends['coverage_rate_trend']*100:.1f}%\n")
                f.write(f"- **Profit Growth Rate:** ${trends['profit_growth_rate']:.2f} per step\n")
                f.write(f"- **Carrier Revenue Growth:** ${trends['carrier_revenue_growth']:.2f} per step\n\n")
            
            # Visualizations
            f.write("## Visualizations\n\n")
            f.write("### Load Dynamics\n")
            f.write("![Load Dynamics](plots/load_dynamics.png)\n\n")
            f.write("### Financial Performance\n")
            f.write("![Financial Performance](plots/financial_performance.png)\n\n")
            f.write("### Market Utilization\n")
            f.write("![Market Utilization](plots/market_utilization.png)\n\n")
            f.write("### Performance Dashboard\n")
            f.write("![Dashboard](plots/dashboard.png)\n\n")
            
            # Files Generated
            f.write("## Generated Files\n\n")
            f.write("- `config.yaml` - Configuration used for this experiment\n")
            f.write("- `summary.json` - Detailed metrics in JSON format\n")
            f.write("- `timeseries_data.csv` - Complete time series data\n")
            f.write("- `plots/` - Directory containing all visualization plots\n")
            f.write("- `report.md` - This human-readable report\n")
    
    def generate_full_report(self, model: FreightBrokerageModel, config_loader: ConfigLoader, scenario: Optional[str] = None):
        """Generate complete experiment report with all outputs."""
        print(f"Generating experiment report for {scenario or 'baseline'} scenario...")
        
        # Create experiment directory
        self.create_experiment_directory(scenario)
        
        # Save configuration
        self.save_config(config_loader, scenario)
        
        # Extract and save data
        timeseries_df = self.extract_timeseries_data(model)
        timeseries_df.to_csv(self.experiment_dir / "timeseries_data.csv", index=False)
        
        # Generate summary metrics
        summary = self.generate_summary_metrics(model, timeseries_df)
        with open(self.experiment_dir / "summary.json", 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Create visualizations
        self.create_plots(timeseries_df, summary)
        
        # Generate markdown report
        self.generate_markdown_report(summary, config_loader, scenario)
        
        print(f"✅ Experiment report saved to: {self.experiment_dir}")
        print(f"📊 View report: {self.experiment_dir / 'report.md'}")
        
        return self.experiment_dir


if __name__ == "__main__":
    # Example usage
    from freight_model import FreightBrokerageModel
    from config_loader import ConfigLoader
    
    # Run a small test experiment
    config = ConfigLoader()
    config.load_config('baseline')
    
    model = FreightBrokerageModel(config=config)
    model.run_model(100)  # Short run for testing
    
    # Generate report
    reporter = ExperimentReporter()
    output_dir = reporter.generate_full_report(model, config, 'baseline')
    
    print(f"Test experiment report generated at: {output_dir}")