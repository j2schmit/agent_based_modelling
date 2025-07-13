import random
import math
from typing import List, Optional, Union
from mesa import Model
from mesa import Agent, Model
from mesa.datacollection import DataCollector
from mesa.space import ContinuousSpace

from load import Load
from carrier import Carrier
from freighttech import FreightTech
from config_loader import ConfigLoader


class FreightBrokerageModel(Model):
    """
    Agent-based model of freight brokerage operations with carriers bidding on loads.
    """
    
    def __init__(self, 
                 config: Optional[Union[ConfigLoader, dict]] = None,
                 scenario: Optional[str] = None,
                 # Backward compatibility parameters
                 num_carriers: Optional[int] = None,
                 grid_size: Optional[int] = None,
                 time_step: Optional[float] = None,
                 load_generation_rate: Optional[float] = None,
                 weekly_volume_variation: Optional[float] = None):
        super().__init__()
        
        # Load configuration
        if config is None:
            config = ConfigLoader()
            config.load_config(scenario)
        elif isinstance(config, dict):
            # Direct config dict passed
            pass
        else:
            # ConfigLoader instance
            if not config._current_config:
                config.load_config(scenario)
        
        # Get simulation parameters from config or defaults
        if isinstance(config, ConfigLoader):
            sim_params = config.get_simulation_params()
        else:
            sim_params = config.get('simulation', {})
        
        # Model parameters (with backward compatibility)
        self.num_carriers = num_carriers if num_carriers is not None else sim_params.get('num_carriers', 20)
        self.grid_size = grid_size if grid_size is not None else sim_params.get('grid_size', 100)
        self.time_step = time_step if time_step is not None else sim_params.get('time_step', 0.1)
        self.load_generation_rate = load_generation_rate if load_generation_rate is not None else sim_params.get('load_generation_rate', 0.3)
        self.weekly_volume_variation = weekly_volume_variation if weekly_volume_variation is not None else sim_params.get('weekly_volume_variation', 0.2)
        self.steps_per_week = sim_params.get('steps_per_week', 70)
        
        # Store config for agents to use
        self.config = config
        self.current_step = 0
        self.current_week = 0
        
        # Mesa components  
        self.agent_list = []  # Simple list-based scheduling
        self.agent_id_map = {}
        self.space = ContinuousSpace(self.grid_size, self.grid_size, torus=False)
        
        # Create the freight broker
        self.broker = FreightTech("FreightTech", self)
        self.agent_list.append(self.broker)
        self.agent_id_map["FreightTech"] = self.broker
        
        # Create carriers
        self.carriers: List[Carrier] = []
        for i in range(self.num_carriers):
            # Random starting positions
            x = random.uniform(0, self.grid_size)
            y = random.uniform(0, self.grid_size)
            
            carrier = Carrier(f"Carrier_{i}", self, (x, y))
            self.carriers.append(carrier)
            self.agent_list.append(carrier)
            self.agent_id_map[f"Carrier_{i}"] = carrier
            self.space.place_agent(carrier, (x, y))
        
        # Data collection
        self.datacollector = DataCollector(
            model_reporters={
                "Active_Loads": lambda m: len(m.broker.active_loads),
                "Completed_Loads": lambda m: len(m.broker.completed_loads),
                "Expired_Loads": lambda m: len(m.broker.expired_loads),
                "Coverage_Rate": lambda m: m.broker.coverage_rate,
                "Total_Revenue": lambda m: m.broker.total_revenue,
                "Total_Cost": lambda m: m.broker.total_cost,
                "Total_Penalties": lambda m: m.broker.total_penalties,
                "Broker_Profit": lambda m: m.broker.total_revenue - m.broker.total_cost - m.broker.total_penalties,
                "Available_Carriers": lambda m: len(m.get_available_carriers()),
                "Average_Carrier_Revenue": lambda m: sum(c.total_revenue for c in m.carriers) / len(m.carriers),
                "Consecutive_Failures": lambda m: m.broker.consecutive_failures
            },
            agent_reporters={
                "Revenue": lambda a: getattr(a, 'total_revenue', 0),
                "Loads_Completed": lambda a: getattr(a, 'loads_completed', 0),
                "Available": lambda a: getattr(a, 'is_available', True),
                "Position_X": lambda a: getattr(a, 'position', (0, 0))[0] if hasattr(a, 'position') else 0,
                "Position_Y": lambda a: getattr(a, 'position', (0, 0))[1] if hasattr(a, 'position') else 0
            }
        )
        
        # Generate initial loads
        self.generate_initial_loads()
        
    def generate_initial_loads(self):
        """Generate some initial loads to start the simulation."""
        load_config = self._get_load_config()
        initial_load_count = max(1, int(self.num_carriers * 0.8))  # Start with fewer loads than carriers
        for _ in range(initial_load_count):
            load = Load.generate_random(self.grid_size, load_config)
            self.broker.add_load(load)
    
    def generate_new_loads(self):
        """Generate new loads based on current market conditions."""
        # Base generation rate with weekly variation
        week_factor = 1 + (random.uniform(-1, 1) * self.weekly_volume_variation)
        adjusted_rate = self.load_generation_rate * week_factor
        
        # Generate loads
        if random.random() < adjusted_rate:
            load_config = self._get_load_config()
            load = Load.generate_random(self.grid_size, load_config)
            self.broker.add_load(load)
    
    def _get_load_config(self):
        """Get load configuration from config."""
        if hasattr(self, 'config') and self.config:
            if hasattr(self.config, 'get_load_params'):
                return self.config.get_load_params()
            elif isinstance(self.config, dict):
                return self.config.get('load', {})
        return {}
    
    def get_available_carriers(self) -> List[Carrier]:
        """Get list of carriers that are currently available for new loads."""
        return [c for c in self.carriers if c.is_available]
    
    def get_carrier(self, carrier_id: str) -> Optional[Carrier]:
        """Get carrier by ID."""
        for carrier in self.carriers:
            if carrier.unique_id == carrier_id:
                return carrier
        return None
    
    def simulate_weekly_market_changes(self):
        """Simulate weekly changes in market conditions."""
        # Adjust number of active carriers (some may go offline/online)
        if random.random() < 0.1:  # 10% chance of carrier changes each week
            change = random.choice([-1, 0, 1])
            if change == 1 and len(self.carriers) < self.num_carriers * 1.2:
                # Add a new carrier
                x = random.uniform(0, self.grid_size)
                y = random.uniform(0, self.grid_size)
                new_id = f"Carrier_{len(self.carriers)}"
                carrier = Carrier(new_id, self, (x, y))
                self.carriers.append(carrier)
                self.agent_list.append(carrier)
                self.agent_id_map[new_id] = carrier
                self.space.place_agent(carrier, (x, y))
            elif change == -1 and len(self.carriers) > self.num_carriers * 0.8:
                # Remove a carrier (if available)
                available_carriers = self.get_available_carriers()
                if available_carriers:
                    carrier_to_remove = random.choice(available_carriers)
                    self.carriers.remove(carrier_to_remove)
                    self.agent_list.remove(carrier_to_remove)
                    del self.agent_id_map[carrier_to_remove.unique_id]
                    self.space.remove_agent(carrier_to_remove)
    
    def step(self):
        """Execute one step of the model."""
        self.current_step += 1
        
        # Check if we've entered a new week
        new_week = self.current_step // self.steps_per_week
        if new_week > self.current_week:
            self.current_week = new_week
            self.simulate_weekly_market_changes()
        
        # Generate new loads
        self.generate_new_loads()
        
        # Step all agents
        for agent in self.agent_list:
            agent.step()
        
        # Collect data
        self.datacollector.collect(self)
    
    def run_model(self, steps: int = 1000):
        """Run the model for a specified number of steps."""
        for _ in range(steps):
            self.step()
    
    def get_model_summary(self) -> dict:
        """Get a summary of the current model state."""
        broker_summary = self.broker.get_performance_summary()
        
        # Carrier statistics
        available_carriers = len(self.get_available_carriers())
        avg_carrier_revenue = sum(c.total_revenue for c in self.carriers) / len(self.carriers)
        total_loads_moved = sum(c.loads_completed for c in self.carriers)
        
        return {
            **broker_summary,
            'simulation_steps': self.current_step,
            'simulation_weeks': self.current_week,
            'total_carriers': len(self.carriers),
            'available_carriers': available_carriers,
            'avg_carrier_revenue': avg_carrier_revenue,
            'total_loads_moved': total_loads_moved,
            'utilization_rate': (len(self.carriers) - available_carriers) / len(self.carriers)
        }
    
    def print_status(self):
        """Print current status of the model."""
        summary = self.get_model_summary()
        print(f"\n=== Simulation Step {self.current_step} (Week {self.current_week}) ===")
        print(f"Broker: {summary['coverage_rate']:.1%} coverage, ${summary['profit']:.0f} profit")
        print(f"Loads: {summary['active_loads']} active, {summary['loads_covered']} covered, {summary['loads_expired']} expired")
        print(f"Carriers: {summary['available_carriers']}/{summary['total_carriers']} available")
        print(f"Market: ${summary['avg_carrier_revenue']:.0f} avg carrier revenue")
        
        if summary['consecutive_failures'] > 0:
            print(f"⚠️  {summary['consecutive_failures']} consecutive load failures")


# Convenience functions to create and run models

def run_freight_simulation_with_config(scenario: Optional[str] = None, steps: int = 1000, verbose: bool = False, generate_report: bool = False):
    """Run a freight brokerage simulation using config file."""
    config = ConfigLoader()
    config.load_config(scenario)
    
    if scenario:
        print(f"Running {scenario} scenario")
    config.print_config_summary()
    
    model = FreightBrokerageModel(config=config)
    model._scenario_name = scenario  # Store for reporting
    
    print(f"\nRunning simulation for {steps} steps...")
    
    for step in range(steps):
        model.step()
        
        if verbose and step % 100 == 0:
            model.print_status()
    
    print(f"\n=== Final Results ===")
    model.print_status()
    
    # Generate experiment report if requested
    if generate_report:
        from experiment_reporter import ExperimentReporter
        reporter = ExperimentReporter()
        reporter.generate_full_report(model, config, scenario)
    
    return model

def run_freight_simulation(steps: int = 1000, num_carriers: int = 20, verbose: bool = False, generate_report: bool = False):
    """Run a freight brokerage simulation (backward compatibility)."""
    model = FreightBrokerageModel(num_carriers=num_carriers)
    model._scenario_name = "custom"  # Store for reporting
    
    print(f"Starting freight brokerage simulation with {num_carriers} carriers...")
    print(f"Running for {steps} steps...")
    
    for step in range(steps):
        model.step()
        
        if verbose and step % 100 == 0:
            model.print_status()
    
    print(f"\n=== Final Results ===")
    model.print_status()
    
    # Generate experiment report if requested
    if generate_report:
        from experiment_reporter import ExperimentReporter
        from config_loader import ConfigLoader
        # Create a default config for reporting
        config = ConfigLoader()
        config.load_config()
        reporter = ExperimentReporter()
        reporter.generate_full_report(model, config, "custom")
    
    return model


if __name__ == "__main__":
    # Example run with config
    model = run_freight_simulation_with_config(steps=500, verbose=True)