import random
import math
from typing import Tuple, Optional, List
from mesa import Agent
from load import Load


class Carrier(Agent):
    """
    Represents a freight carrier with one truck that can bid on loads.
    """
    
    def __init__(self, unique_id: str, model, position: Tuple[float, float]):
        super().__init__(model)
        self.position = position  # Current truck location (x, y)
        self.is_available = True
        self.current_load: Optional[Load] = None
        
        # Carrier characteristics
        self.cost_per_mile = random.uniform(1.2, 1.8)  # Operating cost per mile
        self.fixed_cost = random.uniform(100, 300)  # Fixed cost per load
        self.desired_margin = random.uniform(0.15, 0.35)  # Profit margin target (15-35%)
        self.max_bid_distance = random.uniform(200, 500)  # Max distance willing to travel to pickup
        self.aggressiveness = random.uniform(0.1, 0.9)  # How aggressive in bidding (0-1)
        
        # Tracking
        self.loads_completed = 0
        self.total_revenue = 0
        self.total_profit = 0
        
    def get_distance_to_origin(self, load: Load) -> float:
        """Calculate distance from current position to load origin."""
        return math.sqrt(
            (load.origin[0] - self.position[0])**2 + 
            (load.origin[1] - self.position[1])**2
        )
    
    def get_total_trip_distance(self, load: Load) -> float:
        """Calculate total distance: current position -> origin -> destination."""
        to_origin = self.get_distance_to_origin(load)
        load_distance = load.get_distance()
        return to_origin + load_distance
    
    def calculate_cost(self, load: Load) -> float:
        """Calculate total cost to complete this load."""
        total_distance = self.get_total_trip_distance(load)
        return (total_distance * self.cost_per_mile) + self.fixed_cost
    
    def calculate_minimum_bid(self, load: Load) -> float:
        """Calculate minimum acceptable bid (cost + desired margin)."""
        cost = self.calculate_cost(load)
        return cost * (1 + self.desired_margin)
    
    def is_interested_in_load(self, load: Load) -> bool:
        """Determine if carrier would be interested in bidding on this load."""
        if not self.is_available:
            return False
            
        # Too far to origin
        distance_to_origin = self.get_distance_to_origin(load)
        if distance_to_origin > self.max_bid_distance:
            return False
            
        # Not profitable enough
        min_bid = self.calculate_minimum_bid(load)
        if min_bid > load.market_rate * 1.4:  # Won't bid if need >40% above market
            return False
            
        # Lead time too short for the distance
        if load.lead_time < (distance_to_origin / 500):  # Assuming 500 miles/day travel
            return False
            
        return True
    
    def generate_bid(self, load: Load) -> Optional[float]:
        """Generate a bid for the given load."""
        if not self.is_interested_in_load(load):
            return None
            
        min_bid = self.calculate_minimum_bid(load)
        
        # Competitive adjustment based on market conditions
        market_factor = random.uniform(0.9, 1.1)  # ±10% market adjustment
        
        # Urgency factor - bid lower if load is urgent (less competition expected)
        urgency_factor = 1 - (load.get_urgency_factor() * 0.1 * self.aggressiveness)
        
        # Calculate bid
        bid = min_bid * market_factor * urgency_factor
        
        # Don't bid below cost
        cost = self.calculate_cost(load)
        bid = max(bid, cost * 1.05)  # At least 5% margin
        
        return round(bid, 2)
    
    def accept_load(self, load: Load, agreed_price: float):
        """Accept a load assignment and update carrier state."""
        if not self.is_available:
            raise ValueError(f"Carrier {self.unique_id} is not available")
            
        self.current_load = load
        self.is_available = False
        
        # Calculate profit
        cost = self.calculate_cost(load)
        profit = agreed_price - cost
        
        self.total_revenue += agreed_price
        self.total_profit += profit
        
    def complete_current_load(self):
        """Complete the current load and update position to destination."""
        if self.current_load is None:
            return
            
        # Move to destination
        self.position = self.current_load.destination
        self.loads_completed += 1
        
        # Reset state
        self.current_load = None
        self.is_available = True
    
    def step(self):
        """Mesa agent step function - called each simulation step."""
        # If carrying a load, simulate progress (simplified - complete in one step)
        if self.current_load and not self.is_available:
            # In a more complex model, this would track delivery progress
            self.complete_current_load()
    
    def get_status_summary(self) -> dict:
        """Get summary of carrier's current status and performance."""
        profit_margin = (self.total_profit / self.total_revenue) if self.total_revenue > 0 else 0
        
        return {
            'id': self.unique_id,
            'position': self.position,
            'available': self.is_available,
            'loads_completed': self.loads_completed,
            'total_revenue': self.total_revenue,
            'total_profit': self.total_profit,
            'profit_margin': profit_margin,
            'cost_per_mile': self.cost_per_mile,
            'aggressiveness': self.aggressiveness
        }
    
    def __str__(self) -> str:
        status = "Available" if self.is_available else "Busy"
        return (f"Carrier {self.unique_id} at {self.position} - {status} "
                f"(Completed: {self.loads_completed}, Revenue: ${self.total_revenue:.0f})")