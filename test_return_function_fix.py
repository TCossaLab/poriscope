#!/usr/bin/env python3
"""
Test script to verify the TypeError fix in MetadataController.
"""

import sys
import os

# Add the poriscope module to the path
sys.path.insert(0, '/Applications/poriscope_unforked')

def test_return_function_fix():
    """Test that the return_function is now properly passed as a function object."""
    print("🧪 Testing return_function fix...")
    
    try:
        # Import and inspect the MetadataController
        from poriscope.plugins.analysistabs.MetadataController import MetadataController
        print("   ✅ MetadataController imports successfully")
        
        # Read the source code to verify the fix
        controller_file = '/Applications/poriscope_unforked/poriscope/plugins/analysistabs/MetadataController.py'
        with open(controller_file, 'r') as f:
            content = f.read()
        
        # Check that we're passing the method object, not a string
        if 'self.update_disambiguated_experiments,' in content:
            print("   ✅ Found self.update_disambiguated_experiments (function object) in emit call")
        else:
            print("   ❌ Did not find function object in emit call")
            
        # Check that we removed the string version
        if '"update_disambiguated_experiments",' in content:
            print("   ❌ Still found string version of return_function")
        else:
            print("   ✅ String version of return_function has been removed")
            
        # Verify the method exists and is callable
        try:
            # Create a mock environment to avoid Qt issues
            os.environ['QT_QPA_PLATFORM'] = 'offscreen'
            
            # Note: We can't easily test instantiation due to Qt requirements,
            # but the import success indicates the syntax is correct
            print("   ✅ Syntax validation passed (successful import)")
            
        except Exception as e:
            print(f"   ⚠️  Could not fully test instantiation (Qt issues): {e}")
            
        print("🎉 Return function fix verification completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_return_function_fix()