#!/usr/bin/env python3
"""
Clear local bot memory - removes all user data except users table
Useful for testing fresh
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import db

def clear_memory():
    """Clear all user data from database"""
    print("Clearing bot memory...")
    
    with db.get_db() as conn:
        with conn.cursor() as cur:
            # Clear all user data tables
            tables = [
                'conversations',
                'tasks',
                'reminders',
                'contacts',
                'facts',
                'user_credentials',
                'heartbeat_state',
                'context',
            ]
            
            for table in tables:
                try:
                    # Use TRUNCATE which is faster and resets sequences
                    cur.execute(f"TRUNCATE TABLE {table} CASCADE")
                    print(f"  ✓ Cleared {table}")
                except Exception as e:
                    error_str = str(e)
                    # If table doesn't exist, that's fine
                    if "does not exist" in error_str.lower():
                        print(f"  ⊘ Table {table} doesn't exist yet (skipping)")
                    else:
                        # Rollback and try DELETE as fallback
                        conn.rollback()
                        try:
                            cur.execute(f"DELETE FROM {table}")
                            print(f"  ✓ Cleared {table} (via DELETE)")
                        except Exception as e2:
                            print(f"  ⊘ Could not clear {table}: {str(e2)[:50]}")
                            conn.rollback()
            
            # Reset users onboarding state
            try:
                cur.execute("UPDATE users SET onboarding_state = 'new'")
                print(f"  ✓ Reset onboarding state for {cur.rowcount} users")
            except Exception as e:
                print(f"  ✗ Error resetting onboarding: {e}")
                conn.rollback()
            
            conn.commit()
    
    print("\n✅ Bot memory cleared! Users can start fresh.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--yes":
        clear_memory()
    else:
        print("This will clear ALL user data (tasks, reminders, contacts, facts, etc.).")
        print("Run with --yes flag to confirm: python3 scripts/clear_memory.py --yes")
        sys.exit(1)