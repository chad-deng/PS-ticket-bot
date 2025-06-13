#!/usr/bin/env python3
"""
JIRA API Access Validation Script
This script validates JIRA API connectivity, permissions, and configuration.
"""

import os
import sys
import json
import requests
from requests.auth import HTTPBasicAuth
from typing import Dict, List, Optional
import yaml


class JiraValidator:
    """Validates JIRA API access and configuration."""
    
    def __init__(self, config_path: str = "config/jira-config.yaml"):
        """Initialize the validator with configuration."""
        self.config = self._load_config(config_path)
        self.base_url = os.getenv('JIRA_BASE_URL')
        self.username = os.getenv('JIRA_USERNAME')
        self.api_token = os.getenv('JIRA_API_TOKEN')
        
        if not all([self.base_url, self.username, self.api_token]):
            raise ValueError("Missing required environment variables: JIRA_BASE_URL, JIRA_USERNAME, JIRA_API_TOKEN")
            
        self.auth = HTTPBasicAuth(self.username, self.api_token)
        self.session = requests.Session()
        self.session.auth = self.auth
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"❌ Configuration file not found: {config_path}")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"❌ Error parsing configuration file: {e}")
            sys.exit(1)
    
    def validate_connectivity(self) -> bool:
        """Test basic connectivity to JIRA API."""
        print("🔍 Testing JIRA API connectivity...")
        
        try:
            url = f"{self.base_url}/rest/api/2/myself"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                user_info = response.json()
                print(f"✅ Connected successfully as: {user_info.get('displayName', 'Unknown')}")
                print(f"   Account ID: {user_info.get('accountId', 'Unknown')}")
                print(f"   Email: {user_info.get('emailAddress', 'Unknown')}")
                return True
            else:
                print(f"❌ Connection failed: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def validate_projects(self) -> bool:
        """Validate access to target projects."""
        print("\n🔍 Validating project access...")
        
        projects_config = self.config.get('jira', {}).get('projects', {})
        success = True
        
        for project_type, project_info in projects_config.items():
            project_key = project_info.get('key')
            if not project_key:
                continue
                
            print(f"   Checking project: {project_key}")
            
            try:
                url = f"{self.base_url}/rest/api/2/project/{project_key}"
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    project_data = response.json()
                    print(f"   ✅ {project_key}: {project_data.get('name', 'Unknown')}")
                    
                    # Update config with project ID
                    project_info['id'] = project_data.get('id')
                    
                elif response.status_code == 404:
                    print(f"   ❌ {project_key}: Project not found")
                    success = False
                elif response.status_code == 403:
                    print(f"   ❌ {project_key}: Access denied")
                    success = False
                else:
                    print(f"   ❌ {project_key}: Error {response.status_code}")
                    success = False
                    
            except requests.exceptions.RequestException as e:
                print(f"   ❌ {project_key}: Connection error - {e}")
                success = False
                
        return success
    
    def validate_issue_types(self) -> bool:
        """Validate and discover issue type IDs."""
        print("\n🔍 Discovering issue types...")
        
        try:
            url = f"{self.base_url}/rest/api/2/issuetype"
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                print(f"❌ Failed to fetch issue types: {response.status_code}")
                return False
                
            issue_types = response.json()
            issue_type_map = {it['name']: it['id'] for it in issue_types}
            
            config_issue_types = self.config.get('jira', {}).get('issue_types', [])
            success = True
            
            for issue_type_config in config_issue_types:
                name = issue_type_config.get('name')
                if name in issue_type_map:
                    issue_type_config['id'] = issue_type_map[name]
                    status = "✅" if issue_type_config.get('process', False) else "⚪"
                    print(f"   {status} {name}: ID {issue_type_map[name]}")
                else:
                    print(f"   ❌ {name}: Not found")
                    success = False
                    
            return success
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching issue types: {e}")
            return False
    
    def validate_permissions(self) -> bool:
        """Validate required permissions."""
        print("\n🔍 Validating permissions...")
        
        # Test permissions by attempting to access a project
        projects_config = self.config.get('jira', {}).get('projects', {})
        primary_project = projects_config.get('primary', {}).get('key')
        
        if not primary_project:
            print("❌ No primary project configured")
            return False
            
        try:
            # Test browse project permission
            url = f"{self.base_url}/rest/api/2/project/{primary_project}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                print("   ✅ Browse Projects: OK")
            else:
                print("   ❌ Browse Projects: Failed")
                return False
                
            # Test view issues permission by searching
            url = f"{self.base_url}/rest/api/2/search"
            params = {
                'jql': f'project = {primary_project}',
                'maxResults': 1
            }
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                print("   ✅ View Issues: OK")
            else:
                print("   ❌ View Issues: Failed")
                return False
                
            print("   ⚠️  Add Comments: Cannot test without creating a comment")
            print("   ⚠️  Transition Issues: Cannot test without modifying an issue")
            
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error testing permissions: {e}")
            return False
    
    def discover_custom_fields(self) -> bool:
        """Discover custom field IDs."""
        print("\n🔍 Discovering custom fields...")
        
        try:
            url = f"{self.base_url}/rest/api/2/field"
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                print(f"❌ Failed to fetch fields: {response.status_code}")
                return False
                
            fields = response.json()
            custom_fields = [f for f in fields if f['id'].startswith('customfield_')]
            
            print(f"   Found {len(custom_fields)} custom fields:")
            
            # Look for fields that might match our requirements
            target_fields = {
                'steps to reproduce': 'steps_to_reproduce',
                'affected version': 'affected_version',
                'environment': 'affected_version',
                'customer impact': 'customer_impact',
                'urgency': 'urgency'
            }
            
            for field in custom_fields:
                field_name = field['name'].lower()
                field_id = field['id']
                
                for target_name, config_key in target_fields.items():
                    if target_name in field_name:
                        print(f"   ✅ Found potential match: {field['name']} ({field_id})")
                        print(f"      → Suggested mapping: {config_key} = {field_id}")
                        
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error discovering custom fields: {e}")
            return False
    
    def save_updated_config(self, output_path: str = "config/jira-config-updated.yaml"):
        """Save updated configuration with discovered IDs."""
        print(f"\n💾 Saving updated configuration to {output_path}...")
        
        try:
            with open(output_path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False, indent=2)
            print(f"✅ Configuration saved to {output_path}")
            print("   Please review and update the main config file with discovered values.")
            
        except Exception as e:
            print(f"❌ Error saving configuration: {e}")
    
    def run_validation(self) -> bool:
        """Run complete validation suite."""
        print("🚀 Starting JIRA API validation...\n")
        
        results = []
        results.append(self.validate_connectivity())
        results.append(self.validate_projects())
        results.append(self.validate_issue_types())
        results.append(self.validate_permissions())
        results.append(self.discover_custom_fields())
        
        # Save updated configuration
        self.save_updated_config()
        
        success_count = sum(results)
        total_count = len(results)
        
        print(f"\n📊 Validation Results: {success_count}/{total_count} checks passed")
        
        if success_count == total_count:
            print("🎉 All validations passed! JIRA API access is properly configured.")
            return True
        else:
            print("⚠️  Some validations failed. Please review the issues above.")
            return False


def main():
    """Main function."""
    try:
        validator = JiraValidator()
        success = validator.run_validation()
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"❌ Validation failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
