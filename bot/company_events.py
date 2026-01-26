import random

class CompanyEvents:
    """Random events that can affect companies and stock prices"""
    
    # Negative events (reduce stock price)
    NEGATIVE_EVENTS = [
        {
            "name": "Supply Chain Disruption",
            "description": "A major supplier went bankrupt, disrupting operations",
            "impact": (-0.08, -0.03),  # -8% to -3%
            "weight": 15
        },
        {
            "name": "Product Recall",
            "description": "A product defect forced a costly recall",
            "impact": (-0.12, -0.05),  # -12% to -5%
            "weight": 10
        },
        {
            "name": "Data Breach",
            "description": "Customer data was compromised in a cyberattack",
            "impact": (-0.10, -0.04),  # -10% to -4%
            "weight": 8
        },
        {
            "name": "Regulatory Fine",
            "description": "The company was fined for compliance violations",
            "impact": (-0.07, -0.02),  # -7% to -2%
            "weight": 12
        },
        {
            "name": "Failed Product Launch",
            "description": "A highly anticipated product flopped in the market",
            "impact": (-0.15, -0.06),  # -15% to -6%
            "weight": 8
        },
        {
            "name": "Key Executive Departure",
            "description": "A crucial C-suite executive unexpectedly resigned",
            "impact": (-0.09, -0.03),  # -9% to -3%
            "weight": 10
        },
        {
            "name": "Factory Fire",
            "description": "A production facility was damaged by fire",
            "impact": (-0.11, -0.04),  # -11% to -4%
            "weight": 6
        },
        {
            "name": "Lawsuit Filed",
            "description": "Multiple customers filed a class-action lawsuit",
            "impact": (-0.08, -0.03),  # -8% to -3%
            "weight": 10
        },
        {
            "name": "Market Share Loss",
            "description": "Competitors captured significant market share",
            "impact": (-0.10, -0.04),  # -10% to -4%
            "weight": 12
        },
        {
            "name": "Accounting Scandal",
            "description": "Financial irregularities were discovered",
            "impact": (-0.20, -0.08),  # -20% to -8%
            "weight": 4
        }
    ]
    
    # Positive events (increase stock price)
    POSITIVE_EVENTS = [
        {
            "name": "Major Contract Win",
            "description": "Secured a lucrative multi-year contract",
            "impact": (0.03, 0.10),  # +3% to +10%
            "weight": 15
        },
        {
            "name": "Product Innovation",
            "description": "Launched a groundbreaking new product",
            "impact": (0.05, 0.12),  # +5% to +12%
            "weight": 10
        },
        {
            "name": "Market Expansion",
            "description": "Successfully entered a new geographic market",
            "impact": (0.04, 0.09),  # +4% to +9%
            "weight": 12
        },
        {
            "name": "Partnership Announced",
            "description": "Formed a strategic partnership with an industry leader",
            "impact": (0.03, 0.08),  # +3% to +8%
            "weight": 14
        },
        {
            "name": "Patent Granted",
            "description": "Received approval for a valuable patent",
            "impact": (0.04, 0.10),  # +4% to +10%
            "weight": 10
        },
        {
            "name": "Acquisition Completed",
            "description": "Successfully acquired a complementary business",
            "impact": (0.05, 0.11),  # +5% to +11%
            "weight": 8
        },
        {
            "name": "Efficiency Breakthrough",
            "description": "Achieved major operational cost reductions",
            "impact": (0.03, 0.07),  # +3% to +7%
            "weight": 12
        },
        {
            "name": "Industry Award",
            "description": "Received prestigious industry recognition",
            "impact": (0.02, 0.05),  # +2% to +5%
            "weight": 15
        }
    ]
    
    @staticmethod
    def calculate_event_chance(net_profit: float) -> float:
        """Calculate chance of event occurring based on net profit
        
        Returns probability from 0.0 to 1.0
        """
        # Base event chance: 25%
        base_chance = 0.25
        
        # Adjust based on performance
        if net_profit > 10000:
            # Very profitable - higher chance of positive events
            return base_chance * 1.2
        elif net_profit > 5000:
            # Profitable - normal chance
            return base_chance
        elif net_profit > 0:
            # Barely profitable - slightly higher chance
            return base_chance * 1.1
        else:
            # Unprofitable - higher chance of negative events
            return base_chance * 1.3
    
    @staticmethod
    def should_event_occur(net_profit: float) -> bool:
        """Determine if an event should occur"""
        chance = CompanyEvents.calculate_event_chance(net_profit)
        return random.random() < chance
    
    @staticmethod
    def get_random_event(net_profit: float):
        """Get a random event based on company performance
        
        Returns: dict with event details or None
        """
        if not CompanyEvents.should_event_occur(net_profit):
            return None
        
        # Determine if positive or negative
        if net_profit > 5000:
            # Profitable companies more likely to have positive events
            event_pool = (
                CompanyEvents.POSITIVE_EVENTS * 6 + 
                CompanyEvents.NEGATIVE_EVENTS * 4
            )
        elif net_profit > 0:
            # Barely profitable - equal chance
            event_pool = (
                CompanyEvents.POSITIVE_EVENTS * 5 + 
                CompanyEvents.NEGATIVE_EVENTS * 5
            )
        else:
            # Unprofitable - more likely negative
            event_pool = (
                CompanyEvents.POSITIVE_EVENTS * 3 + 
                CompanyEvents.NEGATIVE_EVENTS * 7
            )
        
        # Weighted random selection
        events_with_weights = []
        for event in event_pool:
            events_with_weights.extend([event] * event['weight'])
        
        selected_event = random.choice(events_with_weights)
        
        # Calculate actual impact within range
        min_impact, max_impact = selected_event['impact']
        actual_impact = random.uniform(min_impact, max_impact)
        
        return {
            'name': selected_event['name'],
            'description': selected_event['description'],
            'impact': actual_impact,
            'is_positive': actual_impact > 0
        }
