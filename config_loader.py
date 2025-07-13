import yaml
from typing import Dict, Any, Optional
from pathlib import Path
import copy


class ConfigLoader:
    """
    Utility for loading and managing ABM configuration from YAML files.
    Supports scenario-based configuration overrides.
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self._base_config = None
        self._current_config = None
        
    def load_config(self, scenario: Optional[str] = None) -> Dict[str, Any]:
        """
        Load configuration, optionally applying a scenario override.
        
        Args:
            scenario: Name of scenario from config.scenarios to apply
            
        Returns:
            Complete configuration dictionary
        """
        if self._base_config is None:
            self._load_base_config()
            
        # Start with base config
        config = copy.deepcopy(self._base_config)
        
        # Apply scenario overrides if specified
        if scenario:
            self._apply_scenario(config, scenario)
            
        self._current_config = config
        return config
    
    def _load_base_config(self):
        """Load the base configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
            
        with open(self.config_path, 'r') as f:
            self._base_config = yaml.safe_load(f)
    
    def _apply_scenario(self, config: Dict[str, Any], scenario_name: str):
        """Apply scenario-specific overrides to the config."""
        scenarios = config.get('scenarios', {})
        
        if scenario_name not in scenarios:
            available = list(scenarios.keys())
            raise ValueError(f"Scenario '{scenario_name}' not found. Available: {available}")
        
        scenario_config = scenarios[scenario_name]
        print(f"Applying scenario: {scenario_name} - {scenario_config.get('description', '')}")
        
        # Apply overrides (skip 'description' key)
        for section, overrides in scenario_config.items():
            if section == 'description':
                continue
                
            if section not in config:
                config[section] = {}
            
            # Deep merge the overrides
            self._deep_merge(config[section], overrides)
    
    def _deep_merge(self, base_dict: Dict[str, Any], override_dict: Dict[str, Any]):
        """Recursively merge override values into base dictionary."""
        for key, value in override_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_merge(base_dict[key], value)
            else:
                base_dict[key] = value
    
    def get_simulation_params(self) -> Dict[str, Any]:
        """Get simulation-level parameters for FreightBrokerageModel."""
        if self._current_config is None:
            self.load_config()
        return self._current_config['simulation']
    
    def get_broker_params(self) -> Dict[str, Any]:
        """Get broker strategy parameters for FreightTech."""
        if self._current_config is None:
            self.load_config()
        return self._current_config['broker']
    
    def get_carrier_params(self) -> Dict[str, Any]:
        """Get carrier behavior parameters."""
        if self._current_config is None:
            self.load_config()
        return self._current_config['carrier']
    
    def get_load_params(self) -> Dict[str, Any]:
        """Get load generation parameters."""
        if self._current_config is None:
            self.load_config()
        return self._current_config['load']
    
    def list_scenarios(self) -> Dict[str, str]:
        """Get available scenarios and their descriptions."""
        if self._base_config is None:
            self._load_base_config()
            
        scenarios = {}
        for name, config in self._base_config.get('scenarios', {}).items():
            scenarios[name] = config.get('description', 'No description')
        
        return scenarios
    
    def print_config_summary(self):
        """Print a summary of the current configuration."""
        if self._current_config is None:
            print("No configuration loaded. Call load_config() first.")
            return
            
        print("\n=== ABM Configuration Summary ===")
        
        sim = self._current_config['simulation']
        print(f"Simulation: {sim['num_carriers']} carriers, {sim['grid_size']}x{sim['grid_size']} grid")
        print(f"Load generation: {sim['load_generation_rate']} per step, ±{sim['weekly_volume_variation']*100}% variation")
        
        broker = self._current_config['broker']
        print(f"Broker: {broker['max_negotiation_rounds']} rounds, {broker['patience_factor']} patience")
        
        carrier = self._current_config['carrier']
        print(f"Carriers: ${carrier['cost_per_mile']['min']:.1f}-${carrier['cost_per_mile']['max']:.1f}/mile")
        print(f"Margins: {carrier['desired_margin']['min']*100:.0f}-{carrier['desired_margin']['max']*100:.0f}%")
        
        load = self._current_config['load']
        print(f"Loads: {load['penalty_rate']*100:.0f}% penalty, {load['lead_time']['min']}-{load['lead_time']['max']} day lead times")
        print("=" * 40)


# Convenience function for easy access
def load_abm_config(scenario: Optional[str] = None) -> ConfigLoader:
    """
    Load ABM configuration with optional scenario.
    
    Args:
        scenario: Scenario name (e.g., 'tight_market', 'urgent_freight')
        
    Returns:
        ConfigLoader instance with loaded configuration
    """
    loader = ConfigLoader()
    loader.load_config(scenario)
    return loader


if __name__ == "__main__":
    # Example usage
    loader = ConfigLoader()
    
    # List available scenarios
    print("Available scenarios:")
    for name, desc in loader.list_scenarios().items():
        print(f"  {name}: {desc}")
    
    # Load baseline config
    print("\n--- Baseline Configuration ---")
    loader.load_config()
    loader.print_config_summary()
    
    # Load with scenario
    print("\n--- Tight Market Scenario ---")
    loader.load_config('tight_market')
    loader.print_config_summary()