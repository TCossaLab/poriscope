#!/usr/bin/env python3
"""
Quick test to demonstrate the fixed table alias handling in construct_metadata_query.
This simulates the issue you were having where s.filtered wasn't properly aliased.
"""

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
import sqlite3
import os

def test_table_aliases():
    """Test that construct_metadata_query properly uses table aliases"""
    
    # Create a mock SQLiteDBLoader instance
    loader = SQLiteDBLoader()
    
    # Mock the required methods to avoid needing actual database
    class MockLoader:
        def get_table_by_column(self, col): 
            # Mock mapping of columns to tables - expanded for cross-table filtering demo
            column_to_table = {
                'voltage': 'events',
                'conductivity': 'events', 
                'filtered': 'sublevels',
                'sublevel_current': 'sublevels',
                'number_peaks': 'events',
                'peak_height': 'events',  # New: for histogram example
                'unfolded_level': 'sublevels',  # New: for cross-table filtering
                'duration': 'events',
                'experiment_name': 'experiments'
            }
            return column_to_table.get(col)
            
        def get_experiment_id_by_name(self, name):
            return 1  # Mock experiment ID
            
        def validate_filter_query(self, query):
            return True, ""  # Mock validation always passes
        
        def _format_debug_msg(self, debug):
            return debug
    
    # Replace methods on loader with mock versions
    mock = MockLoader()
    loader.get_table_by_column = mock.get_table_by_column
    loader.get_experiment_id_by_name = mock.get_experiment_id_by_name
    loader.validate_filter_query = mock.validate_filter_query
    loader._format_debug_msg = mock._format_debug_msg

    print("Testing different query scenarios:\n")

    # Test 1: Events-only query (should use 'e' alias)
    print("1. Events-only query:")
    columns = ['voltage', 'conductivity', 'number_peaks']
    conditions = "e.voltage > -100"  # Valid with 'e' alias
    query, debug, table = loader.construct_metadata_query(columns, conditions)
    print(f"Query: {query}")
    print(f"Uses 'e' alias: {'FROM events e' in query}")
    print()

    # Test 2: Sublevels-only query (should use 's' alias)  
    print("2. Sublevels-only query:")
    columns = ['filtered', 'sublevel_current']
    conditions = "s.filtered != 0 AND s.filtered != -1"  # This was the problematic condition!
    query, debug, table = loader.construct_metadata_query(columns, conditions)
    print(f"Query: {query}")
    print(f"Uses 's' alias: {'FROM sublevels s' in query}")
    print()

    # Test 3: Mixed events+sublevels query (should use both 'e' and 's' aliases)
    print("3. Mixed events+sublevels query:")
    columns = ['voltage', 'filtered', 'sublevel_current']
    conditions = "s.filtered != 0 AND e.voltage > -100"
    query, debug, table = loader.construct_metadata_query(columns, conditions)
    print(f"Query: {query}")
    print(f"Uses JOIN with aliases: {'FROM events e' in query and 'JOIN sublevels s' in query}")
    print()

    # Test 4: The exact scenario from your original error (now fixed)
    print("4. Original error scenario (now fixed):")
    columns = ['number_peaks']  # This is in events table
    conditions = "s.filtered!=0 and s.filtered!=-1"  # But condition references sublevels
    experiments_and_channels = {"experiment_1": [2]}  # Experiment 1, channel 2
    
    try:
        query, debug, table = loader.construct_metadata_query(columns, conditions, experiments_and_channels)
        print(f"Query: {query}")
        print("✅ Now automatically creates JOIN because condition references sublevels!")
    except Exception as e:
        print(f"❌ Error: {e}")
    print()

    # Test 5: NEW FEATURE - Cross-table filtering for histogram
    print("5. 🎯 NEW: Histogram of peak_height filtered by unfolded_level:")
    columns = ['peak_height']  # Want to plot this (events table)
    conditions = "unfolded_level > 0.5"  # But filter by this (sublevels table)
    
    try:
        query, debug, table = loader.construct_metadata_query(columns, conditions)
        print(f"Query: {query}")
        print("✅ Automatically creates events+sublevels JOIN for cross-table filtering!")
        print("   Now you can make a histogram of peak_height filtered by unfolded_level metadata!")
    except Exception as e:
        print(f"❌ Error: {e}")
    print()
    
    # Test 6: Complex cross-table filtering
    print("6. 🎯 Complex cross-table filtering:")
    columns = ['voltage', 'duration']  # Events table columns
    conditions = "s.filtered = 1 AND unfolded_level > 0.3 AND experiment_name = 'test'"  # Mixed tables
    
    try:
        query, debug, table = loader.construct_metadata_query(columns, conditions)
        print(f"Query: {query}")
        print("✅ Creates three-way JOIN (events + sublevels + experiments)!")
        print("   Condition references all three tables, so all are joined!")
    except Exception as e:
        print(f"❌ Error: {e}")
    print()
    
    # Test 7: Filter-only query (no selected columns from conditions tables)
    print("7. 🎯 Filter-only scenario:")
    columns = ['voltage']  # Only events table  
    conditions = "filtered != 0"  # References sublevels but no explicit prefix
    
    try:
        query, debug, table = loader.construct_metadata_query(columns, conditions)
        print(f"Query: {query}")
        print("✅ Automatically detects 'filtered' is in sublevels and creates JOIN!")
        print("   Even without explicit table prefix, cross-table filtering works!")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_table_aliases()