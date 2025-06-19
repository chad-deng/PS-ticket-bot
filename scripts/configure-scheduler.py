#!/usr/bin/env python3
"""
Interactive scheduler configuration tool for PS Ticket Process Bot.
"""

import yaml
import sys
from pathlib import Path
from typing import Dict, Any


def load_search_profiles() -> Dict[str, Any]:
    """Load search profiles from YAML file."""
    config_file = Path("config/search-profiles.yaml")
    if not config_file.exists():
        print(f"❌ Configuration file not found: {config_file}")
        sys.exit(1)
    
    with open(config_file, 'r') as f:
        return yaml.safe_load(f) or {}


def save_search_profiles(profiles: Dict[str, Any]) -> None:
    """Save search profiles to YAML file."""
    config_file = Path("config/search-profiles.yaml")
    
    # Create backup
    backup_file = config_file.with_suffix('.yaml.backup')
    if config_file.exists():
        config_file.rename(backup_file)
        print(f"📁 Backup created: {backup_file}")
    
    with open(config_file, 'w') as f:
        yaml.dump(profiles, f, default_flow_style=False, sort_keys=False)
    
    print(f"✅ Configuration saved: {config_file}")


def display_profiles(profiles: Dict[str, Any]) -> None:
    """Display current search profiles."""
    print("\n📋 Current Search Profiles:")
    print("=" * 50)
    
    for name, config in profiles.items():
        enabled = "✅" if config.get('enabled', False) else "❌"
        schedule = config.get('schedule', 'manual')
        priority = config.get('priority', 'normal')
        description = config.get('description', 'No description')
        
        print(f"\n{enabled} {name}")
        print(f"   Description: {description}")
        print(f"   Schedule: {schedule}")
        print(f"   Priority: {priority}")
        print(f"   Enabled: {config.get('enabled', False)}")


def toggle_profile(profiles: Dict[str, Any], profile_name: str) -> bool:
    """Toggle a profile's enabled status."""
    if profile_name not in profiles:
        print(f"❌ Profile '{profile_name}' not found")
        return False
    
    current_status = profiles[profile_name].get('enabled', False)
    new_status = not current_status
    profiles[profile_name]['enabled'] = new_status
    
    status_text = "enabled" if new_status else "disabled"
    print(f"✅ Profile '{profile_name}' {status_text}")
    return True


def update_schedule(profiles: Dict[str, Any], profile_name: str, new_schedule: str) -> bool:
    """Update a profile's schedule."""
    if profile_name not in profiles:
        print(f"❌ Profile '{profile_name}' not found")
        return False
    
    profiles[profile_name]['schedule'] = new_schedule
    print(f"✅ Profile '{profile_name}' schedule updated to: {new_schedule}")
    return True


def validate_cron(cron_string: str) -> bool:
    """Basic cron validation."""
    parts = cron_string.strip().split()
    if len(parts) != 5:
        print(f"❌ Invalid cron format. Expected 5 fields, got {len(parts)}")
        return False
    
    print(f"✅ Cron format looks valid: {cron_string}")
    return True


def interactive_menu():
    """Interactive configuration menu."""
    print("🕐 PS Ticket Process Bot - Scheduler Configuration")
    print("=" * 55)
    
    profiles = load_search_profiles()
    
    while True:
        print("\n📋 Options:")
        print("1. View current profiles")
        print("2. Enable/disable profile")
        print("3. Update profile schedule")
        print("4. Validate cron schedule")
        print("5. Save and exit")
        print("6. Exit without saving")
        
        choice = input("\nSelect option (1-6): ").strip()
        
        if choice == '1':
            display_profiles(profiles)
        
        elif choice == '2':
            display_profiles(profiles)
            profile_name = input("\nEnter profile name to toggle: ").strip()
            if toggle_profile(profiles, profile_name):
                print("💾 Changes made (not saved yet)")
        
        elif choice == '3':
            display_profiles(profiles)
            profile_name = input("\nEnter profile name: ").strip()
            if profile_name in profiles:
                current_schedule = profiles[profile_name].get('schedule', 'manual')
                print(f"Current schedule: {current_schedule}")
                print("\nCommon schedules:")
                print("  */5 * * * *   - Every 5 minutes")
                print("  */15 * * * *  - Every 15 minutes")
                print("  */30 * * * *  - Every 30 minutes")
                print("  0 * * * *     - Every hour")
                print("  0 */4 * * *   - Every 4 hours")
                print("  manual        - Manual trigger only")
                
                new_schedule = input("\nEnter new schedule: ").strip()
                if new_schedule and (new_schedule == 'manual' or validate_cron(new_schedule)):
                    update_schedule(profiles, profile_name, new_schedule)
                    print("💾 Changes made (not saved yet)")
            else:
                print(f"❌ Profile '{profile_name}' not found")
        
        elif choice == '4':
            cron_string = input("\nEnter cron schedule to validate: ").strip()
            validate_cron(cron_string)
        
        elif choice == '5':
            save_search_profiles(profiles)
            print("\n🎉 Configuration saved successfully!")
            print("\n📝 Next steps:")
            print("1. Restart Celery Beat: ./scripts/start-celery-beat.sh")
            print("2. Or reload via API: curl -X POST http://localhost:8000/scheduler/reload")
            break
        
        elif choice == '6':
            print("\n👋 Exiting without saving changes")
            break
        
        else:
            print("❌ Invalid option. Please select 1-6.")


def main():
    """Main function."""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'list':
            profiles = load_search_profiles()
            display_profiles(profiles)
        
        elif command == 'enable' and len(sys.argv) > 2:
            profiles = load_search_profiles()
            profile_name = sys.argv[2]
            if toggle_profile(profiles, profile_name):
                save_search_profiles(profiles)
        
        elif command == 'disable' and len(sys.argv) > 2:
            profiles = load_search_profiles()
            profile_name = sys.argv[2]
            profiles[profile_name]['enabled'] = False
            save_search_profiles(profiles)
            print(f"✅ Profile '{profile_name}' disabled")
        
        elif command == 'validate' and len(sys.argv) > 2:
            cron_string = ' '.join(sys.argv[2:])
            validate_cron(cron_string)
        
        else:
            print("Usage:")
            print("  python scripts/configure-scheduler.py                    # Interactive mode")
            print("  python scripts/configure-scheduler.py list               # List profiles")
            print("  python scripts/configure-scheduler.py enable <profile>   # Enable profile")
            print("  python scripts/configure-scheduler.py disable <profile>  # Disable profile")
            print("  python scripts/configure-scheduler.py validate <cron>    # Validate cron")
    
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
