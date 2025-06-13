# JIRA Configuration Specification
## PS Ticket Process Bot

### Overview
This document defines the specific JIRA configuration requirements for the PS Ticket Process Bot, including projects, issue types, custom fields, and status transitions.

### JIRA Instance Details
**JIRA URL:** [To be provided by JIRA Administrator]  
**JIRA Version:** [To be confirmed]  
**Authentication Method:** API Token (recommended) or OAuth  

### Target Projects and Issue Types

#### Primary Project
**Project Key:** `SUPPORT`  
**Project Name:** Product Support  
**Project ID:** [To be determined]  

#### Supported Issue Types
| Issue Type | Issue Type ID | Bot Processing |
|------------|---------------|----------------|
| Bug | [TBD] | ✅ Full processing |
| Support Request | [TBD] | ✅ Full processing |
| Feature Request | [TBD] | ✅ Full processing |
| Improvement | [TBD] | ✅ Full processing |
| Epic | [TBD] | ❌ Excluded |
| Sub-task | [TBD] | ❌ Excluded |

### Required JIRA Fields

#### Standard Fields
| Field Name | Field ID | Required | Bot Usage |
|------------|----------|----------|-----------|
| Summary | summary | ✅ | Quality assessment |
| Description | description | ✅ | Quality assessment |
| Issue Type | issuetype | ✅ | Processing logic |
| Priority | priority | ✅ | Quality validation |
| Attachments | attachment | ❌ | Quality assessment |
| Reporter | reporter | ✅ | Logging/tracking |
| Created | created | ✅ | Processing order |
| Status | status | ✅ | Transition logic |

#### Custom Fields (To be mapped)
| Field Purpose | Expected Field Name | Field ID | Field Type | Required |
|---------------|-------------------|----------|------------|----------|
| Steps to Reproduce | Steps to Reproduce | customfield_XXXXX | Text Area | For Bugs |
| Affected Version | Affected Version/Environment | customfield_XXXXX | Text/Select | ✅ |
| Customer Impact | Customer Impact | customfield_XXXXX | Select | ❌ |
| Urgency | Urgency | customfield_XXXXX | Select | ❌ |

### Status Workflow Configuration

#### Current Status Workflow
```
[Open] → [In Progress] → [Resolved] → [Closed]
       ↓
[Awaiting Customer Info] → [In Progress]
       ↓
[Needs More Info (Reporter)] → [Open]
       ↓
[Needs Clarification] → [In Progress]
```

#### Bot Transition Rules
| Ticket Quality | Source Status | Target Status | Transition Name | Transition ID |
|----------------|---------------|---------------|-----------------|---------------|
| High | Open | In Progress | Start Progress | [TBD] |
| High | Open | Ready for Development | Ready for Dev | [TBD] |
| Medium | Open | Awaiting Customer Info | Request Info | [TBD] |
| Medium | Open | Needs Clarification | Need Clarification | [TBD] |
| Low | Open | Needs More Info (Reporter) | More Info Needed | [TBD] |

#### Status Mapping Discovery
**API Endpoint:** `GET /rest/api/2/issue/{issueKey}/transitions`  
**Required Information:**
- Available transitions for each status
- Transition IDs for automation
- Required fields for each transition
- Permissions for each transition

### Webhook Configuration

#### Webhook Events to Subscribe
| Event Type | Event Name | Purpose |
|------------|------------|---------|
| Issue Created | jira:issue_created | Trigger bot processing |
| Issue Updated | jira:issue_updated | Re-process if needed |

#### Webhook Payload Fields
**Required Fields in Webhook:**
- Issue key
- Issue ID  
- Project key
- Issue type
- Status
- Timestamp

#### Webhook Endpoint
**URL:** `https://[bot-domain]/webhook/jira`  
**Method:** POST  
**Authentication:** Webhook secret (to be configured)  

### Bot User Configuration

#### JIRA User Account
**Username:** `ps-ticket-bot` (suggested)  
**Display Name:** PS Ticket Process Bot  
**Email:** [To be provided]  
**Account Type:** Service Account (recommended)  

#### Required Permissions
**Project Permissions:**
- Browse Projects
- View Issues
- Add Comments
- Transition Issues
- View Voters and Watchers

**Global Permissions:**
- None required beyond project access

#### API Token Configuration
**Token Name:** PS-Ticket-Bot-API-Token  
**Scope:** Project-specific access to SUPPORT project  
**Expiration:** 1 year (with renewal reminder)  
**Storage:** Environment variable or secrets manager  

### Field Mapping Configuration

#### Quality Assessment Field Mapping
```yaml
field_mappings:
  summary: "summary"
  description: "description"
  steps_to_reproduce: "customfield_XXXXX"  # To be determined
  affected_version: "customfield_XXXXX"    # To be determined
  issue_type: "issuetype.name"
  priority: "priority.name"
  attachments: "attachment"
  reporter: "reporter.displayName"
```

#### Priority Mapping
| JIRA Priority | Bot Priority Level | Special Handling |
|---------------|-------------------|------------------|
| Highest | Critical | All quality rules enforced |
| High | High | All quality rules enforced |
| Medium | Medium | Standard processing |
| Low | Low | Standard processing |
| Lowest | Lowest | Standard processing |

### Testing Configuration

#### Test Project
**Project Key:** `SUPPORT-TEST`  
**Purpose:** Bot development and testing  
**Access:** Development team only  

#### Test Issue Types
- All production issue types
- Test-specific issue types for edge cases

#### Test Data Requirements
- Sample tickets with various quality levels
- Tickets with missing required fields
- Tickets with different priorities
- Tickets with and without attachments

### Security Configuration

#### API Access Security
- HTTPS only for all API calls
- API token rotation every 6 months
- IP restrictions if possible
- Rate limiting compliance

#### Data Handling
- No persistent storage of ticket content
- Logging limited to metadata only
- Compliance with data retention policies
- No sensitive data in logs

### Monitoring and Alerting

#### JIRA API Monitoring
- API response times
- API error rates
- Rate limit usage
- Authentication failures

#### Bot Performance Monitoring
- Processing time per ticket
- Queue depth
- Success/failure rates
- Comment generation quality

---

### Action Items for JIRA Administrator
1. [ ] Provide JIRA instance URL and version
2. [ ] Create bot service account with specified permissions
3. [ ] Generate API token for bot account
4. [ ] Map custom field IDs for required fields
5. [ ] Provide transition IDs for status changes
6. [ ] Configure webhook endpoints
7. [ ] Set up test project environment
8. [ ] Validate bot permissions in test environment

### Next Steps
1. Complete JIRA API access setup (Task 0.2)
2. Test API connectivity and permissions
3. Validate field mappings and transitions
4. Configure webhook endpoints
5. Begin development environment setup (Task 0.4)
