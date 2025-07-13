import uuid
from dataclasses import dataclass
from typing import Tuple, Optional
import random
import math


@dataclass
class Load:
    """
    Represents a freight load that needs to be transported.
    """
    id: str
    origin: Tuple[float, float]  # (x, y) coordinates
    destination: Tuple[float, float]  # (x, y) coordinates
    market_rate: float  # Base market rate for this lane
    lead_time: float  # Days until pickup deadline
    initial_lead_time: float  # Original lead time for tracking urgency
    penalty_rate: float = 0.20  # Base penalty as fraction of market rate
    assigned_carrier_id: Optional[str] = None
    current_bid: Optional[float] = None
    current_bidder_id: Optional[str] = None
    negotiation_rounds: int = 0
    is_covered: bool = False
    is_expired: bool = False
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
    
    @classmethod
    def generate_random(cls, grid_size: int = 100, load_config: Optional[dict] = None) -> 'Load':
        """Generate a random load with realistic parameters."""
        if load_config is None:
            load_config = {}
        
        origin = (random.uniform(0, grid_size), random.uniform(0, grid_size))
        destination = (random.uniform(0, grid_size), random.uniform(0, grid_size))
        
        # Calculate distance for market rate using config
        distance = math.sqrt((destination[0] - origin[0])**2 + (destination[1] - origin[1])**2)
        
        pricing_config = load_config.get('pricing', {})
        base_rate_per_mile = pricing_config.get('base_rate_per_mile', 2.0)
        minimum_rate = pricing_config.get('minimum_rate', 500)
        rate_variation = pricing_config.get('rate_variation', 100)
        
        market_rate = max(minimum_rate, distance * base_rate_per_mile + random.uniform(-rate_variation, rate_variation))
        
        # Generate lead time based on config distribution
        lead_time_config = load_config.get('lead_time', {})
        min_time = lead_time_config.get('min', 0.5)
        max_time = lead_time_config.get('max', 5.0)
        mean_time = lead_time_config.get('mean', 3.0)
        std_time = lead_time_config.get('std', 1.0)
        
        # Generate lead time using normal distribution, clipped to min/max bounds
        lead_time = random.normalvariate(mean_time, std_time)
        lead_time = max(min_time, min(max_time, lead_time))
        
        # Get penalty rate from config
        penalty_rate = load_config.get('penalty_rate', 0.20)
        
        return cls(
            id="",  # Will be auto-generated
            origin=origin,
            destination=destination,
            market_rate=market_rate,
            lead_time=lead_time,
            initial_lead_time=lead_time,
            penalty_rate=penalty_rate
        )
    
    def get_distance(self) -> float:
        """Calculate the distance between origin and destination."""
        return math.sqrt(
            (self.destination[0] - self.origin[0])**2 + 
            (self.destination[1] - self.origin[1])**2
        )
    
    def get_urgency_factor(self) -> float:
        """Calculate urgency factor based on remaining lead time (0-1, higher = more urgent)."""
        if self.lead_time <= 0:
            return 1.0
        return 1 - (self.lead_time / self.initial_lead_time)
    
    def get_penalty_cost(self, consecutive_failures: int = 0) -> float:
        """Calculate penalty cost with escalation for consecutive failures."""
        base_penalty = self.market_rate * self.penalty_rate
        escalation_multiplier = 1 + (consecutive_failures * 0.1)  # 10% increase per failure
        return base_penalty * escalation_multiplier
    
    def update_lead_time(self, time_step: float = 0.1):
        """Decrease lead time by one time step (representing time passage)."""
        self.lead_time = max(0, self.lead_time - time_step)
        if self.lead_time <= 0 and not self.is_covered:
            self.is_expired = True
    
    def accept_bid(self, carrier_id: str, bid_amount: float):
        """Accept a carrier's bid and mark load as covered."""
        self.assigned_carrier_id = carrier_id
        self.current_bid = bid_amount
        self.current_bidder_id = carrier_id
        self.is_covered = True
    
    def receive_bid(self, carrier_id: str, bid_amount: float):
        """Receive a new bid from a carrier."""
        self.current_bid = bid_amount
        self.current_bidder_id = carrier_id
        self.negotiation_rounds += 1
    
    def __str__(self) -> str:
        return (f"Load {self.id}: {self.origin} → {self.destination}, "
                f"${self.market_rate:.0f}, {self.lead_time:.1f} days left")