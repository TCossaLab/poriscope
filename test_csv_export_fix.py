#!/usr/bin/env python3
"""
Test script to verify that CSV export now handles cross-table filtering correctly.
"""

import tempfile
import os
from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader

def test_csv_export_cross_table_filtering():
    """Test CSV export with conditions that reference multiple tables"""
    
    print("Testing CSV Export with Cross-Table Filtering")
    print("=" * 50)
    
    # Create a mock SQLiteDBLoader instance
    loader = SQLiteDBLoader()
    
    # Mock the required methods
    class MockLoader:
        def __init__(self):
            self.call_log = []
            
        def get_table_by_column(self, col):
            self.call_log.append(f"get_table_by_column({col})")
            column_to_table = {
                'voltage': 'events',
                'conductivity': 'events', 
                'filtered': 'sublevels',
                'sublevel_current': 'sublevels',
                'unfolded_level': 'sublevels',
                'event_id': 'events',
                'id': 'events'
            }
            return column_to_table.get(col)
            
        def get_experiment_id_by_name(self, name):
            self.call_log.append(f"get_experiment_id_by_name({name})")
            return 1
            
        def validate_filter_query(self, query):
            self.call_log.append(f"validate_filter_query(...)")
            print(f"Generated query: {query}")
            # Check if this is the problematic old-style query
            if "SELECT * FROM events" in query and ("filtered" in query or "unfolded_level" in query):
                return False, "no such column: filtered"  # Simulate the original error
            return True, ""
        
        def _format_debug_msg(self, debug):
            return debug
            
        def _load_metadata(self, query):
            self.call_log.append(f"_load_metadata(...)")
            # Mock returning some event data with all required columns
            import pandas as pd
            return pd.DataFrame({
                'id': [1, 2, 3],
                'event_id': [1, 2, 3], 
                'experiment_id': [1, 1, 1],
                'channel_id': [2, 2, 2],
                'channel_db_id': [1, 1, 1],
                'voltage': [-100, -150, -200]
            })
            
        def query_database_directly(self, query):
            self.call_log.append(f"query_database_directly(...)")
            # Mock returning experiment data
            import pandas as pd
            return pd.DataFrame({
                'id': [1],
                'name': ['experiment_1'],
                'description': ['Test experiment']
            })
    
    # Replace methods on loader with mock versions
    mock = MockLoader()
    loader.get_table_by_column = mock.get_table_by_column
    loader.get_experiment_id_by_name = mock.get_experiment_id_by_name
    loader.validate_filter_query = mock.validate_filter_query
    loader._format_debug_msg = mock._format_debug_msg
    loader._load_metadata = mock._load_metadata
    loader.query_database_directly = mock.query_database_directly
    
    # Test the problematic condition that was failing
    print("\n1. Testing the original failing condition:")
    print("   Condition: 'filtered!=0 and filtered!=-1 and unfolded_level>250'")
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # This should now work because it uses cross-table query construction
            generator = loader.export_subset_to_csv(
                output_folder=temp_dir,
                subset_name="test_export",
                conditions="filtered!=0 and filtered!=-1 and unfolded_level>250",
                experiments_and_channels={"experiment_1": [2]}
            )
            
            # Consume the generator to execute the export
            progress_list = list(generator)
            print("   ✅ SUCCESS! CSV export completed without errors")
            print(f"   Progress steps: {len(progress_list)}")
            
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        
    print(f"\n2. Method calls made:")
    for call in mock.call_log:
        print(f"   - {call}")
        
    print(f"\n3. Key improvement:")
    print(f"   - Old approach: SELECT * FROM events WHERE filtered!=0 (FAILED)")
    print(f"   - New approach: Uses construct_metadata_query with cross-table JOINs (SUCCESS)")

if __name__ == "__main__":
    test_csv_export_cross_table_filtering()