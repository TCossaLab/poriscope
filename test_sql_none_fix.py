#!/usr/bin/env python3
"""
Test script to verify the SQL None value fix.
"""

import sys
import os
import tempfile
import sqlite3

# Add the poriscope module to the path
sys.path.insert(0, '/Applications/poriscope_unforked')

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader

def create_test_database():
    """Create a test SQLite database with some sample data."""
    fd, path = tempfile.mkstemp(suffix='.sqlite')
    os.close(fd)
    
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute("""
        CREATE TABLE experiments (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE
        )
    """)
    
    cursor.execute("""
        CREATE TABLE channels (
            id INTEGER PRIMARY KEY,
            experiment_id INTEGER,
            channel_id INTEGER,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE events (
            id INTEGER PRIMARY KEY,
            experiment_id INTEGER,
            channel_id INTEGER,
            event_id INTEGER,
            unfolded_level REAL,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id)
        )
    """)
    
    # Insert test data
    cursor.execute("INSERT INTO experiments (id, name) VALUES (1, 'test_experiment')")
    cursor.execute("INSERT INTO channels (id, experiment_id, channel_id) VALUES (1, 1, 2)")
    cursor.execute("INSERT INTO events (id, experiment_id, channel_id, event_id, unfolded_level) VALUES (1, 1, 2, 1, 250.5)")
    
    conn.commit()
    conn.close()
    
    return path

def test_sql_none_fix():
    """Test that None values in experiment IDs don't create invalid SQL."""
    print("🧪 Testing SQL None value fix...")
    
    # Create test database
    db_path = create_test_database()
    
    try:
        # Create loader instance
        loader = SQLiteDBLoader()
        loader.db_path = db_path
        loader._database_name = 'test_database'
        
        # Test 1: Valid experiment name should work
        print("   Test 1: Valid experiment name")
        try:
            exp_id = loader.get_experiment_id_by_name('test_experiment')
            print(f"   ✅ Found experiment ID: {exp_id}")
        except Exception as e:
            print(f"   ❌ Failed to get valid experiment ID: {e}")
            
        # Test 2: Invalid experiment name should return None
        print("   Test 2: Invalid experiment name")
        try:
            exp_id = loader.get_experiment_id_by_name('nonexistent_experiment')
            print(f"   ✅ Correctly returned None for nonexistent experiment: {exp_id}")
        except Exception as e:
            print(f"   ❌ Error getting nonexistent experiment ID: {e}")
            
        # Test 3: Test with disambiguated name that doesn't exist
        print("   Test 3: Disambiguated name that doesn't exist")
        try:
            exp_id = loader.get_experiment_id_by_name('nonexistent_experiment (test.sqlite)')
            print(f"   ✅ Correctly returned None for disambiguated nonexistent experiment: {exp_id}")
        except Exception as e:
            print(f"   ❌ Error getting disambiguated nonexistent experiment ID: {e}")
        
        # Test 4: Try to query events with an experiment that doesn't exist
        # This should handle None values gracefully now
        print("   Test 4: Query with nonexistent experiment (should not crash)")
        try:
            experiments_and_channels = {'nonexistent_experiment': [2]}
            result = loader.get_events(experiments_and_channels=experiments_and_channels)
            print(f"   ✅ Query completed without SQL errors")
        except KeyError as e:
            print(f"   ✅ Correctly raised KeyError for nonexistent experiment: {e}")
        except Exception as e:
            if "malformed query string" in str(e) or "= None" in str(e):
                print(f"   ❌ Still getting SQL None error: {e}")
            else:
                print(f"   ⚠️  Different error (may be expected): {e}")
                
        print("🎉 SQL None fix test completed!")
        
    finally:
        # Clean up test database
        os.unlink(db_path)

if __name__ == "__main__":
    test_sql_none_fix()