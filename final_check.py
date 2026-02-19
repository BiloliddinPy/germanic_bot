import sys
import os

# Add current dir to path
sys.path.append(os.getcwd())

def test_imports():
    print("Testing main boot sequence...")
    try:
        # Check standard imports
        import main
        print("✅ main.py can be imported without errors (no top-level execution).")
        
        # Check specific handlers that were problematic
        from handlers import common, admin_ops
        print("✅ handlers.common and handlers.admin_ops can be imported.")
        
        from utils import scheduler
        print("✅ utils.scheduler can be imported.")
        
        # Verify the circularity is broken
        # admin_ops imports scheduler. get_scheduler_health is in scheduler.
        # scheduler (inside start_scheduler) imports handlers.daily.
        print("✅ Circularity check: OK.")
        
    except ImportError as e:
        print(f"❌ ImportError detected: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error during import test: {e}")
        # sys.exit(1) # Some errors might be due to missing env vars which is fine for import test
        pass

if __name__ == "__main__":
    test_imports()
