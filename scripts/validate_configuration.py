#!/usr/bin/env python3
"""
Configuration Validation Script
This script validates all configuration settings for the PS Ticket Process Bot.
"""

import os
import sys
import yaml
from pathlib import Path
from typing import Dict, List, Any
from pydantic import ValidationError

# Add app to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import Settings


class ConfigurationValidator:
    """Validates configuration settings and files."""
    
    def __init__(self):
        """Initialize the validator."""
        self.errors = []
        self.warnings = []
        
    def validate_environment_variables(self) -> bool:
        """Validate required environment variables."""
        print("🔍 Validating environment variables...")
        
        required_vars = [
            "JIRA_BASE_URL",
            "JIRA_USERNAME", 
            "JIRA_API_TOKEN",
            "GEMINI_API_KEY",
            "SECRET_KEY",
            "JIRA_WEBHOOK_SECRET"
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
                
        if missing_vars:
            self.errors.append(f"Missing required environment variables: {', '.join(missing_vars)}")
            print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
            return False
        else:
            print("✅ All required environment variables are set")
            return True
    
    def validate_configuration_files(self) -> bool:
        """Validate configuration files exist and are valid YAML."""
        print("\n🔍 Validating configuration files...")
        
        config_files = [
            "config/jira-config.yaml",
            "config/gemini-config.yaml",
            "config/environments/development.yaml",
            "config/environments/staging.yaml", 
            "config/environments/production.yaml"
        ]
        
        success = True
        
        for config_file in config_files:
            if not Path(config_file).exists():
                self.errors.append(f"Configuration file not found: {config_file}")
                print(f"❌ Configuration file not found: {config_file}")
                success = False
                continue
                
            try:
                with open(config_file, 'r') as f:
                    yaml.safe_load(f)
                print(f"✅ {config_file}: Valid YAML")
            except yaml.YAMLError as e:
                self.errors.append(f"Invalid YAML in {config_file}: {e}")
                print(f"❌ {config_file}: Invalid YAML - {e}")
                success = False
                
        return success
    
    def validate_pydantic_settings(self) -> bool:
        """Validate Pydantic settings can be loaded."""
        print("\n🔍 Validating Pydantic settings...")
        
        try:
            settings = Settings()
            print("✅ All Pydantic settings loaded successfully")
            
            # Validate specific settings
            self._validate_jira_settings(settings)
            self._validate_gemini_settings(settings)
            self._validate_quality_rules(settings)
            
            return True
            
        except ValidationError as e:
            self.errors.append(f"Pydantic validation error: {e}")
            print(f"❌ Pydantic validation error: {e}")
            return False
        except Exception as e:
            self.errors.append(f"Error loading settings: {e}")
            print(f"❌ Error loading settings: {e}")
            return False
    
    def _validate_jira_settings(self, settings: Settings):
        """Validate JIRA-specific settings."""
        print("   🔍 Validating JIRA settings...")
        
        # Check URL format
        if not settings.jira.base_url.startswith(('http://', 'https://')):
            self.errors.append("JIRA base URL must start with http:// or https://")
            print("   ❌ Invalid JIRA base URL format")
            return
            
        # Check timeout values
        if settings.jira.timeout <= 0:
            self.warnings.append("JIRA timeout should be positive")
            print("   ⚠️  JIRA timeout should be positive")
            
        print("   ✅ JIRA settings valid")
    
    def _validate_gemini_settings(self, settings: Settings):
        """Validate Gemini-specific settings."""
        print("   🔍 Validating Gemini settings...")
        
        # Check API key format
        if not settings.gemini.api_key.startswith('AI'):
            self.warnings.append("Gemini API key should start with 'AI'")
            print("   ⚠️  Gemini API key format might be incorrect")
            
        # Check generation parameters
        if not 0.0 <= settings.gemini.temperature <= 1.0:
            self.errors.append("Gemini temperature must be between 0.0 and 1.0")
            print("   ❌ Invalid Gemini temperature")
            return
            
        if not 0.0 <= settings.gemini.top_p <= 1.0:
            self.errors.append("Gemini top_p must be between 0.0 and 1.0")
            print("   ❌ Invalid Gemini top_p")
            return
            
        print("   ✅ Gemini settings valid")
    
    def _validate_quality_rules(self, settings: Settings):
        """Validate quality rules settings."""
        print("   🔍 Validating quality rules...")
        
        # Check length constraints
        if settings.quality_rules.summary_min_length <= 0:
            self.errors.append("Summary minimum length must be positive")
            print("   ❌ Invalid summary minimum length")
            return
            
        if settings.quality_rules.description_min_length <= 0:
            self.errors.append("Description minimum length must be positive")
            print("   ❌ Invalid description minimum length")
            return
            
        # Check quality scoring thresholds
        if settings.quality_rules.high_quality_max_issues < 0:
            self.errors.append("High quality max issues must be non-negative")
            print("   ❌ Invalid high quality threshold")
            return
            
        print("   ✅ Quality rules valid")
    
    def validate_field_mappings(self) -> bool:
        """Validate JIRA field mappings."""
        print("\n🔍 Validating JIRA field mappings...")
        
        try:
            settings = Settings()
            mappings = settings.get_jira_field_mappings()
            
            required_fields = [
                "summary",
                "description", 
                "issue_type",
                "priority",
                "attachments"
            ]
            
            missing_fields = []
            for field in required_fields:
                if field not in mappings or not mappings[field]:
                    missing_fields.append(field)
                    
            if missing_fields:
                self.warnings.append(f"Missing field mappings: {', '.join(missing_fields)}")
                print(f"   ⚠️  Missing field mappings: {', '.join(missing_fields)}")
            else:
                print("   ✅ All required field mappings present")
                
            return True
            
        except Exception as e:
            self.errors.append(f"Error validating field mappings: {e}")
            print(f"❌ Error validating field mappings: {e}")
            return False
    
    def validate_transitions(self) -> bool:
        """Validate JIRA transition mappings."""
        print("\n🔍 Validating JIRA transitions...")
        
        try:
            settings = Settings()
            transitions = settings.get_jira_transitions()
            
            required_quality_levels = ["high_quality", "medium_quality", "low_quality"]
            
            missing_transitions = []
            for quality_level in required_quality_levels:
                if quality_level not in transitions:
                    missing_transitions.append(quality_level)
                    
            if missing_transitions:
                self.warnings.append(f"Missing transition mappings: {', '.join(missing_transitions)}")
                print(f"   ⚠️  Missing transition mappings: {', '.join(missing_transitions)}")
            else:
                print("   ✅ All required transition mappings present")
                
            return True
            
        except Exception as e:
            self.errors.append(f"Error validating transitions: {e}")
            print(f"❌ Error validating transitions: {e}")
            return False
    
    def validate_feature_flags(self) -> bool:
        """Validate feature flag settings."""
        print("\n🔍 Validating feature flags...")
        
        try:
            settings = Settings()
            
            # Check for conflicting feature flags
            if settings.features.enable_webhooks and settings.features.enable_polling:
                self.warnings.append("Both webhooks and polling are enabled - this might cause duplicate processing")
                print("   ⚠️  Both webhooks and polling enabled")
                
            if settings.features.enable_ai_comments and not settings.gemini.api_key:
                self.errors.append("AI comments enabled but no Gemini API key provided")
                print("   ❌ AI comments enabled without API key")
                return False
                
            print("   ✅ Feature flags configuration valid")
            return True
            
        except Exception as e:
            self.errors.append(f"Error validating feature flags: {e}")
            print(f"❌ Error validating feature flags: {e}")
            return False
    
    def generate_config_summary(self) -> Dict[str, Any]:
        """Generate a summary of current configuration."""
        print("\n📋 Configuration Summary:")
        
        try:
            settings = Settings()
            
            summary = {
                "environment": settings.app.environment,
                "app_name": settings.app.name,
                "app_version": settings.app.version,
                "debug_mode": settings.app.debug,
                "jira_base_url": settings.jira.base_url,
                "gemini_model": settings.gemini.model,
                "features_enabled": {
                    "webhooks": settings.features.enable_webhooks,
                    "polling": settings.features.enable_polling,
                    "ai_comments": settings.features.enable_ai_comments,
                    "status_transitions": settings.features.enable_status_transitions,
                    "notifications": settings.features.enable_notifications,
                    "metrics": settings.features.enable_metrics
                },
                "quality_thresholds": {
                    "high_quality_max_issues": settings.quality_rules.high_quality_max_issues,
                    "medium_quality_max_issues": settings.quality_rules.medium_quality_max_issues,
                    "low_quality_min_issues": settings.quality_rules.low_quality_min_issues
                }
            }
            
            for key, value in summary.items():
                if isinstance(value, dict):
                    print(f"   {key}:")
                    for sub_key, sub_value in value.items():
                        print(f"     {sub_key}: {sub_value}")
                else:
                    print(f"   {key}: {value}")
                    
            return summary
            
        except Exception as e:
            self.errors.append(f"Error generating config summary: {e}")
            print(f"❌ Error generating config summary: {e}")
            return {}
    
    def run_validation(self) -> bool:
        """Run complete configuration validation."""
        print("🚀 Starting configuration validation...\n")
        
        results = []
        results.append(self.validate_environment_variables())
        results.append(self.validate_configuration_files())
        results.append(self.validate_pydantic_settings())
        results.append(self.validate_field_mappings())
        results.append(self.validate_transitions())
        results.append(self.validate_feature_flags())
        
        # Generate summary
        self.generate_config_summary()
        
        success_count = sum(results)
        total_count = len(results)
        
        print(f"\n📊 Validation Results: {success_count}/{total_count} checks passed")
        
        if self.warnings:
            print(f"\n⚠️  Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   - {warning}")
                
        if self.errors:
            print(f"\n❌ Errors ({len(self.errors)}):")
            for error in self.errors:
                print(f"   - {error}")
                
        if success_count == total_count and not self.errors:
            print("\n🎉 Configuration validation completed successfully!")
            if self.warnings:
                print("   Note: There are warnings that should be reviewed.")
            return True
        else:
            print("\n❌ Configuration validation failed. Please fix the errors above.")
            return False


def main():
    """Main function."""
    try:
        validator = ConfigurationValidator()
        success = validator.run_validation()
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"❌ Configuration validation failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
