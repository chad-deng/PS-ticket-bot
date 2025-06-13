#!/usr/bin/env python3
"""
JIRA Webhook Setup Script
This script sets up JIRA webhooks for the PS Ticket Process Bot.
"""

import os
import sys
import json
import requests
from requests.auth import HTTPBasicAuth
from typing import Dict, List


class JiraWebhookSetup:
    """Sets up JIRA webhooks for the bot."""
    
    def __init__(self):
        """Initialize the webhook setup."""
        self.base_url = os.getenv('JIRA_BASE_URL')
        self.username = os.getenv('JIRA_USERNAME')
        self.api_token = os.getenv('JIRA_API_TOKEN')
        self.webhook_url = os.getenv('BOT_WEBHOOK_URL')
        self.webhook_secret = os.getenv('JIRA_WEBHOOK_SECRET')
        
        if not all([self.base_url, self.username, self.api_token, self.webhook_url]):
            raise ValueError("Missing required environment variables")
            
        self.auth = HTTPBasicAuth(self.username, self.api_token)
        self.session = requests.Session()
        self.session.auth = self.auth
        
    def list_existing_webhooks(self) -> List[Dict]:
        """List existing webhooks."""
        print("🔍 Listing existing webhooks...")
        
        try:
            url = f"{self.base_url}/rest/webhooks/1.0/webhook"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                webhooks = response.json()
                print(f"   Found {len(webhooks)} existing webhooks")
                
                for webhook in webhooks:
                    print(f"   - {webhook.get('name', 'Unnamed')}: {webhook.get('url', 'No URL')}")
                    
                return webhooks
            else:
                print(f"❌ Failed to list webhooks: {response.status_code}")
                return []
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Error listing webhooks: {e}")
            return []
    
    def create_webhook(self) -> bool:
        """Create a new webhook for the bot."""
        print("🔧 Creating webhook for PS Ticket Process Bot...")
        
        webhook_config = {
            "name": "PS Ticket Process Bot Webhook",
            "url": f"{self.webhook_url}/webhook/jira",
            "events": [
                "jira:issue_created",
                "jira:issue_updated"
            ],
            "filters": {
                "issue-related-events-section": {
                    "project": {
                        "key": "SUPPORT"  # Primary project
                    }
                }
            },
            "excludeBody": False
        }
        
        # Add webhook secret if provided
        if self.webhook_secret:
            webhook_config["secret"] = self.webhook_secret
            
        try:
            url = f"{self.base_url}/rest/webhooks/1.0/webhook"
            response = self.session.post(
                url,
                json=webhook_config,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 201:
                webhook_data = response.json()
                print(f"✅ Webhook created successfully!")
                print(f"   Webhook ID: {webhook_data.get('self', 'Unknown')}")
                print(f"   Name: {webhook_data.get('name', 'Unknown')}")
                print(f"   URL: {webhook_data.get('url', 'Unknown')}")
                return True
            else:
                print(f"❌ Failed to create webhook: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Error creating webhook: {e}")
            return False
    
    def test_webhook_connectivity(self) -> bool:
        """Test if the webhook endpoint is accessible."""
        print("🔍 Testing webhook endpoint connectivity...")
        
        try:
            # Test if the webhook URL is accessible
            test_url = f"{self.webhook_url}/health"  # Assuming a health endpoint
            response = requests.get(test_url, timeout=10)
            
            if response.status_code == 200:
                print("✅ Webhook endpoint is accessible")
                return True
            else:
                print(f"⚠️  Webhook endpoint returned: {response.status_code}")
                print("   This might be expected if the bot is not running yet")
                return True  # Don't fail setup for this
                
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Cannot reach webhook endpoint: {e}")
            print("   This is expected if the bot is not deployed yet")
            return True  # Don't fail setup for this
    
    def validate_webhook_permissions(self) -> bool:
        """Validate that the user has permissions to manage webhooks."""
        print("🔍 Validating webhook permissions...")
        
        try:
            # Try to list webhooks to check permissions
            url = f"{self.base_url}/rest/webhooks/1.0/webhook"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                print("✅ User has webhook management permissions")
                return True
            elif response.status_code == 403:
                print("❌ User does not have webhook management permissions")
                print("   Please ensure the bot user has 'Administer Projects' permission")
                return False
            else:
                print(f"⚠️  Unexpected response: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Error checking webhook permissions: {e}")
            return False
    
    def setup_webhooks(self) -> bool:
        """Run complete webhook setup."""
        print("🚀 Starting JIRA webhook setup...\n")
        
        # Validate permissions first
        if not self.validate_webhook_permissions():
            return False
            
        # List existing webhooks
        existing_webhooks = self.list_existing_webhooks()
        
        # Check if our webhook already exists
        bot_webhook_exists = any(
            "PS Ticket Process Bot" in webhook.get('name', '')
            for webhook in existing_webhooks
        )
        
        if bot_webhook_exists:
            print("⚠️  PS Ticket Process Bot webhook already exists")
            print("   Please remove the existing webhook if you want to recreate it")
            return True
            
        # Test webhook endpoint connectivity
        self.test_webhook_connectivity()
        
        # Create the webhook
        success = self.create_webhook()
        
        if success:
            print("\n🎉 Webhook setup completed successfully!")
            print("\nNext steps:")
            print("1. Deploy the bot application to make the webhook endpoint available")
            print("2. Test the webhook by creating a test issue in JIRA")
            print("3. Monitor the bot logs to ensure webhook events are received")
        else:
            print("\n❌ Webhook setup failed. Please check the errors above.")
            
        return success


def main():
    """Main function."""
    try:
        setup = JiraWebhookSetup()
        success = setup.setup_webhooks()
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"❌ Webhook setup failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
