from typing import List, Dict, Optional, Tuple
from mesa import Agent
from load import Load
from carrier import Carrier
import random


class FreightTech(Agent):
    """
    Represents the freight brokerage that manages loads and negotiates with carriers.
    """
    
    def __init__(self, unique_id: str, model):
        super().__init__(model)
        
        # Active loads being managed
        self.active_loads: List[Load] = []
        self.completed_loads: List[Load] = []
        self.expired_loads: List[Load] = []
        
        # Negotiation tracking
        self.pending_negotiations: Dict[str, List[Tuple[str, float]]] = {}  # load_id -> [(carrier_id, bid)]
        
        # Performance tracking
        self.total_revenue = 0  # What we charged customers
        self.total_cost = 0    # What we paid carriers
        self.total_penalties = 0
        self.consecutive_failures = 0
        self.coverage_rate = 0.0
        
        # Strategy parameters
        self.max_negotiation_rounds = 3
        self.patience_factor = 0.8  # How patient to be (0-1, higher = more patient)
        
    def add_load(self, load: Load):
        """Add a new load to manage."""
        self.active_loads.append(load)
        self.pending_negotiations[load.id] = []
        
    def get_urgency_threshold(self, load: Load) -> float:
        """Calculate price threshold based on load urgency and strategy."""
        base_threshold = load.market_rate
        urgency_factor = load.get_urgency_factor()
        
        # More urgent = willing to pay more
        if urgency_factor > 0.8:  # Very urgent (< 20% lead time left)
            return base_threshold * 1.3
        elif urgency_factor > 0.5:  # Moderate urgency
            return base_threshold * 1.15
        else:  # Not urgent
            return base_threshold * 0.95  # Try to get below market rate
    
    def should_accept_bid(self, load: Load, bid: float, carrier_id: str) -> bool:
        """Decide whether to accept a carrier's bid."""
        threshold = self.get_urgency_threshold(load)
        
        # Always accept if below threshold
        if bid <= threshold:
            return True
        
        # If above threshold, consider other factors
        urgency = load.get_urgency_factor()
        penalty_cost = load.get_penalty_cost(self.consecutive_failures)
        
        # Accept if bid is less than potential penalty
        if bid < penalty_cost:
            return True
            
        # Accept if very urgent and we've been negotiating for a while
        if urgency > 0.9 and load.negotiation_rounds >= 2:
            return True
            
        return False
    
    def generate_counter_offer(self, load: Load, original_bid: float) -> Optional[float]:
        """Generate a counter-offer to a carrier's bid."""
        if load.negotiation_rounds >= self.max_negotiation_rounds:
            return None  # Stop negotiating
            
        threshold = self.get_urgency_threshold(load)
        urgency = load.get_urgency_factor()
        
        # Counter-offer strategy based on urgency
        if urgency < 0.3:  # Not urgent - be aggressive
            counter = threshold * 0.9
        elif urgency < 0.7:  # Moderate urgency
            counter = threshold * 0.95
        else:  # Very urgent - be generous
            counter = threshold * 1.05
        
        # Don't counter below reasonable minimum
        min_counter = load.market_rate * 0.8
        counter = max(counter, min_counter)
        
        # Don't counter if it's higher than their bid
        if counter >= original_bid:
            return None
            
        return round(counter, 2)
    
    def process_bids(self, load: Load, bids: List[Tuple[str, float]]):
        """Process all bids for a load and make decisions."""
        if not bids:
            return
            
        # Sort bids by price (lowest first)
        sorted_bids = sorted(bids, key=lambda x: x[1])
        best_carrier_id, best_bid = sorted_bids[0]
        
        # Check if we should accept the best bid
        if self.should_accept_bid(load, best_bid, best_carrier_id):
            self.accept_bid(load, best_carrier_id, best_bid)
            return
        
        # Try to counter-offer to the best bidder
        counter_offer = self.generate_counter_offer(load, best_bid)
        if counter_offer is not None:
            # In a real system, this would send the counter to the carrier
            # For simulation, we'll assume carrier might accept or reject
            carrier = self.model.get_carrier(best_carrier_id)
            if carrier and self.carrier_accepts_counter(carrier, load, counter_offer):
                self.accept_bid(load, best_carrier_id, counter_offer)
                return
        
        # Store bid for potential future acceptance
        load.receive_bid(best_carrier_id, best_bid)
    
    def carrier_accepts_counter(self, carrier: Carrier, load: Load, counter_offer: float) -> bool:
        """Simulate whether a carrier would accept our counter-offer."""
        min_acceptable = carrier.calculate_minimum_bid(load)
        
        # Carrier accepts if counter is above their minimum + some tolerance
        tolerance_factor = 1 + (carrier.aggressiveness * 0.1)  # More aggressive = less tolerant
        return counter_offer >= (min_acceptable * tolerance_factor)
    
    def accept_bid(self, load: Load, carrier_id: str, agreed_price: float):
        """Accept a bid and assign the load to the carrier."""
        # Update load
        load.accept_bid(carrier_id, agreed_price)
        
        # Update carrier
        carrier = self.model.get_carrier(carrier_id)
        if carrier:
            carrier.accept_load(load, agreed_price)
        
        # Update broker finances
        customer_rate = load.market_rate * random.uniform(1.05, 1.25)  # We charge customers 5-25% above market
        self.total_revenue += customer_rate
        self.total_cost += agreed_price
        
        # Move load to completed
        self.active_loads.remove(load)
        self.completed_loads.append(load)
        
        # Reset consecutive failures
        self.consecutive_failures = 0
        
        # Clean up negotiations
        if load.id in self.pending_negotiations:
            del self.pending_negotiations[load.id]
    
    def handle_expired_load(self, load: Load):
        """Handle a load that expired without coverage."""
        penalty = load.get_penalty_cost(self.consecutive_failures)
        self.total_penalties += penalty
        self.consecutive_failures += 1
        
        # Move to expired loads
        self.active_loads.remove(load)
        self.expired_loads.append(load)
        
        # Clean up negotiations
        if load.id in self.pending_negotiations:
            del self.pending_negotiations[load.id]
    
    def step(self):
        """Mesa agent step function - called each simulation step."""
        # Update lead times and handle expired loads
        expired_loads = []
        for load in self.active_loads:
            load.update_lead_time(self.model.time_step)
            if load.is_expired:
                expired_loads.append(load)
        
        # Handle expired loads
        for load in expired_loads:
            self.handle_expired_load(load)
        
        # Collect bids from carriers for active loads
        for load in self.active_loads:
            if load.is_covered:
                continue
                
            current_bids = []
            for carrier in self.model.get_available_carriers():
                bid = carrier.generate_bid(load)
                if bid is not None:
                    current_bids.append((carrier.unique_id, bid))
            
            # Process bids if any
            if current_bids:
                self.process_bids(load, current_bids)
        
        # Update performance metrics
        self.update_metrics()
    
    def update_metrics(self):
        """Update performance tracking metrics."""
        total_loads = len(self.completed_loads) + len(self.expired_loads)
        if total_loads > 0:
            self.coverage_rate = len(self.completed_loads) / total_loads
    
    def get_performance_summary(self) -> dict:
        """Get summary of broker's performance."""
        total_loads = len(self.completed_loads) + len(self.expired_loads)
        profit = self.total_revenue - self.total_cost - self.total_penalties
        profit_margin = (profit / self.total_revenue) if self.total_revenue > 0 else 0
        
        return {
            'total_loads_handled': total_loads,
            'loads_covered': len(self.completed_loads),
            'loads_expired': len(self.expired_loads),
            'coverage_rate': self.coverage_rate,
            'total_revenue': self.total_revenue,
            'total_cost': self.total_cost,
            'total_penalties': self.total_penalties,
            'profit': profit,
            'profit_margin': profit_margin,
            'consecutive_failures': self.consecutive_failures,
            'active_loads': len(self.active_loads)
        }
    
    def __str__(self) -> str:
        return (f"FreightTech: {len(self.active_loads)} active loads, "
                f"{self.coverage_rate:.1%} coverage rate, "
                f"${self.total_revenue - self.total_cost - self.total_penalties:.0f} profit")