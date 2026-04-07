#!/usr/bin/env python3
"""openHarness configuration restore module.

Used to restore overwritten configuration files before creating a PR.
"""

import os
import sys
import shutil

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from utils.config import get_project_config_file

project_dir = os.getcwd()
openharness_dir = os.path.join(project_dir, ".openharness")


def restore_config_files():
    """Restore overwritten configuration files from backup."""
    backup_dir = os.path.join(openharness_dir, "backup")
    
    if not os.path.exists(backup_dir):
        print("[openHarness] No backup found")
        return False
    
    restored_count = 0
    for root, dirs, files in os.walk(backup_dir):
        for f in files:
            backup_file = os.path.join(root, f)
            rel_path = os.path.relpath(backup_file, backup_dir)
            target_file = os.path.join(project_dir, rel_path)
            
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            shutil.copy2(backup_file, target_file)
            print(f"[openHarness] Restored: {rel_path}")
            restored_count += 1
    
    if restored_count > 0:
        print(f"[openHarness] Restored {restored_count} config file(s)")
    else:
        print("[openHarness] No config files to restore")
    
    return True


def main():
    print("[openHarness] Restoring config files from backup...")
    restore_config_files()


if __name__ == "__main__":
    main()
