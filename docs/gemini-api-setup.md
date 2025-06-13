# Google Gemini API Setup Guide

This guide walks you through setting up Google Gemini API access for the PS Ticket Process Bot.

## Prerequisites

- Google Cloud Platform account
- Access to Google AI Studio or Google Cloud Console
- Valid payment method (for API usage beyond free tier)

## Step 1: Enable Gemini API

### Option A: Using Google AI Studio (Recommended for Development)

1. **Visit Google AI Studio:**
   - Go to [https://makersuite.google.com/](https://makersuite.google.com/)
   - Sign in with your Google account

2. **Get API Key:**
   - Click "Get API Key" in the top navigation
   - Click "Create API Key in new project" or select existing project
   - Copy the generated API key
   - Store it securely (you'll add it to `.env` file)

### Option B: Using Google Cloud Console (Recommended for Production)

1. **Create or Select Project:**
   ```bash
   # Using gcloud CLI
   gcloud projects create ps-ticket-bot-project
   gcloud config set project ps-ticket-bot-project
   ```

2. **Enable Generative AI API:**
   ```bash
   gcloud services enable generativelanguage.googleapis.com
   ```

3. **Create API Key:**
   ```bash
   gcloud alpha services api-keys create --display-name="PS Ticket Bot API Key"
   ```

## Step 2: Configure API Key

1. **Add to Environment File:**
   Edit your `.env` file:
   ```bash
   GEMINI_API_KEY=your_api_key_here
   GEMINI_MODEL=gemini-pro
   ```

2. **Verify API Key Format:**
   - API keys should start with `AI`
   - Example: `AIzaSyD...`

## Step 3: Understand Rate Limits and Quotas

### Free Tier Limits (as of 2024)
- **Requests per minute:** 60
- **Requests per day:** 1,500
- **Tokens per minute:** 32,000
- **Tokens per day:** 50,000

### Paid Tier Limits
- Higher limits based on your billing account
- Contact Google Cloud support for enterprise limits

### Rate Limit Handling
The bot implements automatic rate limiting:
- Exponential backoff for rate limit errors
- Request queuing to stay within limits
- Monitoring and alerting for quota usage

## Step 4: Test API Access

1. **Run Validation Script:**
   ```bash
   source venv/bin/activate
   python scripts/validate_gemini_access.py
   ```

2. **Expected Output:**
   ```
   🚀 Starting Gemini API validation...

   🔍 Validating Gemini API key...
   ✅ API key is valid. Found X available models.

   🔍 Validating access to model: gemini-pro...
   ✅ Model 'gemini-pro' is accessible

   🔍 Testing content generation...
   ✅ Content generation successful!

   📊 Validation Results: 5/5 checks passed
   🎉 All validations passed! Gemini API is properly configured.
   ```

## Step 5: Configure Safety Settings

The bot includes safety settings to ensure appropriate content generation:

```yaml
safety_settings:
  - category: "HARM_CATEGORY_HARASSMENT"
    threshold: "BLOCK_MEDIUM_AND_ABOVE"
  - category: "HARM_CATEGORY_HATE_SPEECH"
    threshold: "BLOCK_MEDIUM_AND_ABOVE"
  - category: "HARM_CATEGORY_SEXUALLY_EXPLICIT"
    threshold: "BLOCK_MEDIUM_AND_ABOVE"
  - category: "HARM_CATEGORY_DANGEROUS_CONTENT"
    threshold: "BLOCK_MEDIUM_AND_ABOVE"
```

## Step 6: Optimize Generation Parameters

### Temperature Settings
- **0.0-0.3:** More deterministic, consistent responses (recommended for support tickets)
- **0.4-0.7:** Balanced creativity and consistency
- **0.8-1.0:** More creative, varied responses

### Token Limits
- **max_output_tokens:** 1024 (suitable for JIRA comments)
- Adjust based on your comment length requirements

## Troubleshooting

### Common Issues

**1. API Key Invalid**
```
❌ API key is invalid or doesn't have required permissions
```
**Solution:**
- Verify API key is copied correctly
- Ensure no extra spaces or characters
- Check that the API key hasn't expired

**2. Model Not Found**
```
❌ Model 'gemini-pro' not found
```
**Solution:**
- Check available models in Google AI Studio
- Verify model name spelling
- Ensure your project has access to the model

**3. Rate Limit Exceeded**
```
❌ Rate limit exceeded
```
**Solution:**
- Wait for rate limit reset
- Implement request queuing
- Consider upgrading to paid tier

**4. Quota Exceeded**
```
❌ Quota exceeded for requests per day
```
**Solution:**
- Wait for daily quota reset
- Upgrade to paid tier
- Optimize prompt efficiency

### API Error Codes

| Error Code | Meaning | Solution |
|------------|---------|----------|
| 400 | Bad Request | Check request format and parameters |
| 401 | Unauthorized | Verify API key |
| 403 | Forbidden | Check API permissions and quotas |
| 429 | Too Many Requests | Implement rate limiting |
| 500 | Internal Server Error | Retry with exponential backoff |

## Security Best Practices

### API Key Security
1. **Never commit API keys to version control**
2. **Use environment variables or secrets manager**
3. **Rotate API keys regularly**
4. **Restrict API key permissions to minimum required**

### Request Security
1. **Always use HTTPS**
2. **Validate input data**
3. **Sanitize generated content**
4. **Log security events**

## Monitoring and Alerting

### Key Metrics to Monitor
- API request success rate
- Response time
- Token usage
- Rate limit hits
- Error rates by type

### Recommended Alerts
- API error rate > 5%
- Daily quota usage > 80%
- Response time > 10 seconds
- Authentication failures

## Cost Optimization

### Tips to Reduce Costs
1. **Optimize prompts** - Be concise and specific
2. **Cache responses** - For similar tickets
3. **Use appropriate models** - Don't use more powerful models than needed
4. **Monitor usage** - Set up billing alerts
5. **Implement fallbacks** - Use templates when API is unavailable

### Estimated Costs (as of 2024)
- **Free tier:** 0-1,500 requests/day = $0
- **Paid tier:** ~$0.001-0.002 per request (varies by model and tokens)
- **Monthly estimate:** For 10,000 tickets/month ≈ $10-20

## Next Steps

After successful Gemini API setup:

1. ✅ **Validate API access** - Run validation script
2. ⏭️ **Proceed to Phase 0.4** - Environment Setup
3. ⏭️ **Begin Phase 1.4** - AI Comment Generation Module
4. 🔄 **Monitor usage** - Set up monitoring and alerts

## Support Resources

- **Google AI Studio:** [https://makersuite.google.com/](https://makersuite.google.com/)
- **API Documentation:** [https://ai.google.dev/docs](https://ai.google.dev/docs)
- **Google Cloud Support:** [https://cloud.google.com/support](https://cloud.google.com/support)
- **Community Forum:** [https://discuss.ai.google.dev/](https://discuss.ai.google.dev/)
