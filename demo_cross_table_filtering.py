#!/usr/bin/env python3
"""
Demonstration of Cross-Table Filtering Feature

This script shows how the enhanced construct_metadata_query method now supports 
filtering based on metadata from any table, regardless of what columns you're plotting.

Example use cases:
- Plot histogram of peak_height (events) filtered by unfolded_level (sublevels)  
- Plot voltage vs duration (events) filtered by filtered status (sublevels)
- Any combination of plot data from one table, filters from another

The system automatically determines which tables need to be JOINed based on:
1. The columns you want to select/plot
2. The columns referenced in your filter conditions
"""

def demonstrate_cross_table_filtering():
    print("=" * 80)
    print("🎯 CROSS-TABLE FILTERING DEMONSTRATION")
    print("=" * 80)
    print()
    
    print("BEFORE: You could only filter data from the same table you were plotting")
    print("- Plot peak_height (events) → could only filter by events columns")
    print("- Plot sublevel_current (sublevels) → could only filter by sublevels columns")
    print()
    
    print("AFTER: You can now filter by ANY metadata regardless of plot type!")
    print("- Plot peak_height (events) filtered by unfolded_level (sublevels) ✅") 
    print("- Plot voltage (events) filtered by filtered status (sublevels) ✅")
    print("- Plot any combination across events/sublevels/experiments tables ✅")
    print()
    
    print("HOW IT WORKS:")
    print("1. System analyzes your selected columns → determines base tables needed")
    print("2. System analyzes your filter conditions → finds additional tables needed") 
    print("3. Automatically creates appropriate JOINs between all required tables")
    print("4. Generates query with proper table aliases (e, s, exp)")
    print()
    
    print("EXAMPLE SCENARIOS:")
    print()
    
    scenarios = [
        {
            "description": "Histogram of peak heights, only events with good filtering",
            "columns": ["peak_height"],
            "conditions": "filtered = 1",
            "explanation": "Plots events.peak_height, filtered by sublevels.filtered"
        },
        {
            "description": "Voltage vs duration for high-quality unfolded events", 
            "columns": ["voltage", "duration"],
            "conditions": "unfolded_level > 0.8 AND filtered != 0",
            "explanation": "Plots events columns, filtered by sublevels metadata"
        },
        {
            "description": "Sublevel currents from specific experiment type",
            "columns": ["sublevel_current"], 
            "conditions": "experiment_name = 'high_salt'",
            "explanation": "Plots sublevels data, filtered by experiments metadata"
        },
        {
            "description": "Complex multi-table analysis",
            "columns": ["peak_height", "sublevel_current"],
            "conditions": "voltage > -200 AND filtered = 1 AND experiment_name LIKE '%test%'", 
            "explanation": "Uses all three tables: events + sublevels + experiments"
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"{i}. {scenario['description']}")
        print(f"   Columns: {scenario['columns']}")  
        print(f"   Filter: {scenario['conditions']}")
        print(f"   → {scenario['explanation']}")
        print()
    
    print("TECHNICAL DETAILS:")
    print("- Automatically detects table aliases in conditions (e.voltage, s.filtered)")
    print("- Looks up table for unaliased columns (voltage → events, filtered → sublevels)")
    print("- Creates minimal required JOINs (no unnecessary table joins)")
    print("- Maintains proper SQL syntax with consistent aliasing")
    print()
    
    print("BENEFITS:")
    print("✅ More flexible data analysis - filter by any relevant metadata")
    print("✅ No manual JOIN writing - system handles complexity automatically") 
    print("✅ Backward compatible - existing queries continue to work")
    print("✅ Performance optimized - only joins tables that are actually needed")
    print()
    
    print("To test this functionality, run: python test_table_alias_fix.py")
    print("=" * 80)

if __name__ == "__main__":
    demonstrate_cross_table_filtering()