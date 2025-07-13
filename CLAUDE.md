# Freight Brokerage Negotiation ABM Design

## Overview
Agent-based model simulating carriers bidding on loads from FreightTech LLC, a freight brokerage. The goal is to find optimal negotiation strategies for the broker when deciding whether to accept or counter carrier bids on time-sensitive loads.

## Agent Types

### 1. FreightTech (Broker Agent)
**Role:** Central agent managing multiple loads and negotiating with carriers
**Properties:**
- Manages portfolio of active loads
- Tracks penalty history and escalation
- Maintains negotiation strategies per lead time

**Behaviors:**
- Posts loads with origin, destination, market rate, deadline
- Receives and evaluates carrier bids
- Decides to accept, counter-offer, or wait for better bids
- Adapts strategy based on lead time urgency and penalty risk

### 2. Carrier Agents
**Role:** Independent trucking companies with single trucks
**Properties:**
- Current truck location (x, y coordinates)
- Cost structure (fuel, driver wages, overhead)
- Profit margin requirements
- Bidding aggressiveness

**Behaviors:**
- Evaluate loads based on distance to origin
- Submit bids above minimum acceptable rate
- Compete with other carriers on same lanes
- Relocate to destination after completing loads

### 3. Load Entities
**Role:** Freight shipments requiring transportation
**Properties:**
- Origin coordinates (pickup location)
- Destination coordinates (delivery location)
- Market rate (lane-specific baseline price)
- Lead time (time until pickup deadline)
- Penalty cost if uncovered

## Model Parameters

### Time & Geography
- **Lead time distribution:** 0.5-5 days (majority ~3 days)
- **Geographic space:** 2D grid representing geographic regions
- **Distance calculation:** Euclidean distance for simplicity

### Economics
- **Market rates:** Lane-specific baseline pricing
- **Penalty structure:** Base 20% of market rate, escalating with consecutive failures
- **Carrier costs:** Distance-based transportation costs + fixed overhead

### Market Dynamics
- **Population balance:** Roughly equal carriers and loads
- **Weekly fluctuation:** ±20% variation in carrier and load volumes
- **Capacity:** One truck per carrier (simplified)

## Negotiation Strategies

### FreightTech Strategy (Time-Based)
- **Early lead time (>2 days):**
  - Start below market rate
  - Patient negotiation approach
  - Multiple counter-offers acceptable
  
- **Medium lead time (1-2 days):**
  - Offer at or slightly above market rate
  - Moderate urgency in negotiations
  - Limited counter-offer rounds
  
- **Late lead time (<1 day):**
  - Offer above market rate
  - Accept quickly to avoid penalties
  - Minimal negotiation rounds

### Carrier Strategy (Profit-Driven)
- **Distance evaluation:** Only bid if origin within profitable range
- **Profit targeting:** Bid = market rate + costs + desired margin
- **Competitive response:** Adjust bids based on competition level
- **Opportunistic pricing:** Higher bids during high-demand periods

### Penalty Escalation System
- **Base penalty:** 20% of market rate for uncovered loads
- **Escalation mechanism:** Penalty increases with consecutive failures
- **Reset condition:** Successful coverage streak resets penalty multiplier
- **Strategic impact:** Influences FreightTech's risk tolerance

## Model Mechanics

### Simulation Flow
1. **Load generation:** New loads posted with random origins/destinations
2. **Carrier evaluation:** Carriers assess loads and submit bids
3. **Negotiation rounds:** Multi-round bidding with counters
4. **Load assignment:** Successful matches remove load and relocate carrier
5. **Penalty assessment:** Uncovered loads trigger penalties
6. **Weekly reset:** Volume fluctuations and market adjustments

### Key Metrics
- **Coverage rate:** Percentage of loads successfully assigned
- **Average negotiation time:** Time from posting to assignment
- **Profit margins:** Broker and carrier profitability
- **Penalty frequency:** Rate of uncovered loads
- **Market efficiency:** Price discovery and convergence

## Implementation Notes

### Technology Stack
- **Framework:** Mesa (Python ABM library)
- **Visualization:** Mesa's built-in visualization tools
- **Data collection:** Mesa's data collector for metrics

### Initial Simplifications
- Single truck per carrier
- No carrier reputation system
- Fixed market rates per lane
- Simplified geographic model
- No seasonal/cyclical demand patterns

### Future Extensions
- Multi-truck carriers
- Reputation and relationship building
- Dynamic market rate adjustments
- Real geographic data integration
- Advanced negotiation strategies
- Machine learning strategy optimization