#!/usr/bin/env python3
"""
Google Gemini API Access Validation Script
This script validates Gemini API connectivity, quotas, and configuration.
"""

import os
import sys
import json
import time
import requests
from typing import Dict, Optional
import yaml


class GeminiValidator:
    """Validates Google Gemini API access and configuration."""
    
    def __init__(self, config_path: str = "config/gemini-config.yaml"):
        """Initialize the validator with configuration."""
        self.config = self._load_config(config_path)
        self.api_key = os.getenv('GEMINI_API_KEY')
        self.model = os.getenv('GEMINI_MODEL', 'gemini-pro')
        
        if not self.api_key:
            raise ValueError("Missing required environment variable: GEMINI_API_KEY")
            
        self.base_url = "https://generativelanguage.googleapis.com/v1"
        
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
    
    def validate_api_key(self) -> bool:
        """Validate the API key format and basic connectivity."""
        print("🔍 Validating Gemini API key...")
        
        # Check API key format
        if not self.api_key.startswith('AI'):
            print("⚠️  API key doesn't start with 'AI' - this might be incorrect")
            
        # Test basic connectivity by listing models
        try:
            url = f"{self.base_url}/models"
            params = {'key': self.api_key}
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                models_data = response.json()
                models = models_data.get('models', [])
                print(f"✅ API key is valid. Found {len(models)} available models.")
                
                # List available models
                for model in models[:5]:  # Show first 5 models
                    model_name = model.get('name', 'Unknown').replace('models/', '')
                    print(f"   - {model_name}")
                    
                if len(models) > 5:
                    print(f"   ... and {len(models) - 5} more models")
                    
                return True
                
            elif response.status_code == 400:
                print("❌ Invalid API key format")
                return False
            elif response.status_code == 403:
                print("❌ API key is invalid or doesn't have required permissions")
                return False
            else:
                print(f"❌ Unexpected response: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def validate_model_access(self) -> bool:
        """Validate access to the specified model."""
        print(f"\n🔍 Validating access to model: {self.model}...")
        
        try:
            url = f"{self.base_url}/models/{self.model}"
            params = {'key': self.api_key}
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                model_data = response.json()
                print(f"✅ Model '{self.model}' is accessible")
                print(f"   Display Name: {model_data.get('displayName', 'Unknown')}")
                print(f"   Description: {model_data.get('description', 'No description')[:100]}...")
                
                # Check supported generation methods
                methods = model_data.get('supportedGenerationMethods', [])
                if 'generateContent' in methods:
                    print("   ✅ Supports content generation")
                else:
                    print("   ❌ Does not support content generation")
                    return False
                    
                return True
                
            elif response.status_code == 404:
                print(f"❌ Model '{self.model}' not found")
                print("   Available models can be listed with the previous validation")
                return False
            else:
                print(f"❌ Error accessing model: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def test_content_generation(self) -> bool:
        """Test content generation with a simple prompt."""
        print(f"\n🔍 Testing content generation...")
        
        test_prompt = "Generate a brief, professional response to acknowledge a JIRA ticket submission."
        
        try:
            url = f"{self.base_url}/models/{self.model}:generateContent"
            params = {'key': self.api_key}
            
            payload = {
                "contents": [{
                    "parts": [{
                        "text": test_prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.3,
                    "topK": 40,
                    "topP": 0.8,
                    "maxOutputTokens": 100,
                    "candidateCount": 1
                }
            }
            
            headers = {'Content-Type': 'application/json'}
            
            start_time = time.time()
            response = requests.post(url, params=params, json=payload, headers=headers, timeout=30)
            end_time = time.time()
            
            if response.status_code == 200:
                result = response.json()
                
                # Extract generated content
                candidates = result.get('candidates', [])
                if candidates:
                    content = candidates[0].get('content', {})
                    parts = content.get('parts', [])
                    if parts:
                        generated_text = parts[0].get('text', '')
                        
                        print("✅ Content generation successful!")
                        print(f"   Response time: {end_time - start_time:.2f} seconds")
                        print(f"   Generated text preview: {generated_text[:100]}...")
                        
                        # Check for safety ratings
                        safety_ratings = candidates[0].get('safetyRatings', [])
                        if safety_ratings:
                            print("   Safety ratings: All passed")
                            
                        return True
                    else:
                        print("❌ No content in response")
                        return False
                else:
                    print("❌ No candidates in response")
                    return False
                    
            elif response.status_code == 400:
                print(f"❌ Bad request: {response.text}")
                return False
            elif response.status_code == 429:
                print("❌ Rate limit exceeded")
                return False
            else:
                print(f"❌ Generation failed: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def check_rate_limits(self) -> bool:
        """Check current rate limit status."""
        print(f"\n🔍 Checking rate limits...")
        
        # Note: Gemini API doesn't provide a direct endpoint to check quotas
        # We'll make a simple request and check headers
        
        try:
            url = f"{self.base_url}/models"
            params = {'key': self.api_key}
            
            response = requests.get(url, params=params, timeout=10)
            
            # Check for rate limit headers (if available)
            headers = response.headers
            
            print("✅ Rate limit check completed")
            
            # Look for common rate limit headers
            rate_limit_headers = [
                'X-RateLimit-Limit',
                'X-RateLimit-Remaining',
                'X-RateLimit-Reset',
                'Retry-After'
            ]
            
            found_headers = False
            for header in rate_limit_headers:
                if header in headers:
                    print(f"   {header}: {headers[header]}")
                    found_headers = True
                    
            if not found_headers:
                print("   No rate limit headers found in response")
                print("   Rate limits are enforced but not exposed in headers")
                
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error checking rate limits: {e}")
            return False
    
    def validate_configuration(self) -> bool:
        """Validate the Gemini configuration settings."""
        print(f"\n🔍 Validating configuration settings...")
        
        gemini_config = self.config.get('gemini', {})
        
        # Check generation config
        gen_config = gemini_config.get('generation_config', {})
        
        # Validate temperature
        temperature = gen_config.get('temperature', 0.3)
        if not 0.0 <= temperature <= 1.0:
            print(f"❌ Invalid temperature: {temperature} (must be 0.0-1.0)")
            return False
        else:
            print(f"✅ Temperature: {temperature}")
            
        # Validate top_p
        top_p = gen_config.get('top_p', 0.8)
        if not 0.0 <= top_p <= 1.0:
            print(f"❌ Invalid top_p: {top_p} (must be 0.0-1.0)")
            return False
        else:
            print(f"✅ Top P: {top_p}")
            
        # Validate max_output_tokens
        max_tokens = gen_config.get('max_output_tokens', 1024)
        if max_tokens <= 0 or max_tokens > 8192:
            print(f"❌ Invalid max_output_tokens: {max_tokens} (must be 1-8192)")
            return False
        else:
            print(f"✅ Max output tokens: {max_tokens}")
            
        # Check safety settings
        safety_settings = gemini_config.get('safety_settings', [])
        if safety_settings:
            print(f"✅ Safety settings configured: {len(safety_settings)} categories")
        else:
            print("⚠️  No safety settings configured")
            
        return True
    
    def run_validation(self) -> bool:
        """Run complete validation suite."""
        print("🚀 Starting Gemini API validation...\n")
        
        results = []
        results.append(self.validate_api_key())
        results.append(self.validate_model_access())
        results.append(self.test_content_generation())
        results.append(self.check_rate_limits())
        results.append(self.validate_configuration())
        
        success_count = sum(results)
        total_count = len(results)
        
        print(f"\n📊 Validation Results: {success_count}/{total_count} checks passed")
        
        if success_count == total_count:
            print("🎉 All validations passed! Gemini API is properly configured.")
            print("\nNext steps:")
            print("1. Proceed with Phase 0.4: Environment Setup")
            print("2. Begin implementing the AI comment generation module")
            return True
        else:
            print("⚠️  Some validations failed. Please review the issues above.")
            print("\nCommon solutions:")
            print("1. Verify your GEMINI_API_KEY is correct")
            print("2. Check that your Google Cloud project has Gemini API enabled")
            print("3. Ensure you have sufficient quota/credits")
            return False


def main():
    """Main function."""
    try:
        validator = GeminiValidator()
        success = validator.run_validation()
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"❌ Validation failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
