# Box Platform Setup Guide

Complete guide to setting up Box integration for GeoBox.

---

## Step 1: Create Box JWT Application

1. Go to [Box Developer Console](https://app.box.com/developers/console)
2. Click **Create New App**
3. Choose **Custom App**
4. Choose **Server Authentication (with JWT)**
5. Name: `GeoBox Intelligence`
6. Click **Create App**

---

## Step 2: Configure App Permissions

In the app configuration:

### **Application Scopes**
Enable these scopes:
- ✅ Read all files and folders
- ✅ Write all files and folders
- ✅ Manage webhooks

### **Application Access**
- Select: **App Access Only**

### **Advanced Features**
- ✅ Generate user access tokens

---

## Step 3: Generate Key Pair

1. In **Configuration** tab
2. Scroll to **Add and Manage Public Keys**
3. Click **Generate a Public/Private Keypair**
4. **Download JSON config file**
5. Save as `config/box_config.json` in your project

Example `box_config.json`:
```json
{
  "boxAppSettings": {
    "clientID": "your_client_id",
    "clientSecret": "your_client_secret",
    "appAuth": {
      "publicKeyID": "your_key_id",
      "privateKey": "-----BEGIN ENCRYPTED PRIVATE KEY-----\n...\n-----END ENCRYPTED PRIVATE KEY-----\n",
      "passphrase": "your_passphrase"
    }
  },
  "enterpriseID": "your_enterprise_id"
}
```

---

## Step 4: Authorize App in Box Admin Console

⚠️ **Important:** You need Box Admin access for this step.

1. Go to [Box Admin Console](https://app.box.com/master/settings/apps)
2. Navigate to **Apps** tab
3. Find your app in **Custom Apps Manager**
4. Click **Authorize**

If you don't have admin access:
- Contact your Box admin
- Provide them with your App Client ID
- They can authorize it for you

---

## Step 5: Create Metadata Template

1. Go to Box Admin Console
2. Navigate to **Content** → **Metadata**
3. Click **Create New Template**

**Template Settings:**
- **Template Name**: `GeoBox Intelligence`
- **Template Key**: `geoBoxIntelligence`
- **Scope**: `Enterprise`

**Fields:**

| Field Key | Display Name | Type | Options |
|-----------|-------------|------|---------|
| `latitude` | Latitude | Float | - |
| `longitude` | Longitude | Float | - |
| `altitude` | Altitude | Float | - |
| `gps_timestamp` | GPS Timestamp | String | - |
| `validation_status` | Status | Enum | `valid`, `flagged`, `no_gps`, `error` |
| `confidence` | Confidence | Float | - |
| `ai_notes` | AI Notes | String | - |
| `processing_date` | Processed | String | - |

---

## Step 6: Create Webhook

### Option A: Using Box Admin Console

1. Go to folder where you want to monitor uploads
2. Click **⋯** (more options)
3. Select **Manage Webhooks**
4. Click **Create Webhook**
5. Configure:
   - **Target URL**: `https://your-geobox-app.azurecontainerapps.io/webhook/box`
   - **Triggers**: Select `FILE.UPLOADED`
6. Click **Create**

### Option B: Using Box CLI

```bash
box webhooks:create folder 123456789 \
  --address https://your-geobox-app.azurecontainerapps.io/webhook/box \
  --triggers FILE.UPLOADED
```

### Option C: Using API (with code)

```python
from boxsdk import Client, JWTAuth

auth = JWTAuth.from_settings_file('config/box_config.json')
client = Client(auth)

# Create webhook on folder
folder_id = '123456789'
webhook = client.create_webhook(
    target_type='folder',
    target_id=folder_id,
    triggers=['FILE.UPLOADED'],
    address='https://your-geobox-app.azurecontainerapps.io/webhook/box'
)

print(f"Webhook created: {webhook.id}")
```

---

## Step 7: Test Webhook

1. Upload a geotagged photo to the monitored Box folder
2. Check GeoBox logs:
   ```powershell
   az containerapp logs show \
     --name geobox-app-dev \
     --resource-group geobox-rg \
     --follow
   ```
3. Refresh the file in Box
4. Click on the file → Check metadata panel for GPS data

---

## Troubleshooting

### **App Not Authorized**
- Error: `Access denied - please contact your administrator`
- Solution: Box admin needs to authorize the app (Step 4)

### **Metadata Template Not Found**
- Error: `Template 'geoBoxIntelligence' not found`
- Solution: Create metadata template in Admin Console (Step 5)

### **Webhook Not Triggering**
- Check webhook is active: Box Admin → Folder → Manage Webhooks
- Verify URL is publicly accessible
- Check GeoBox app is running: `curl https://your-app/health`
- View webhook delivery logs in Box Admin Console

### **Box SDK Authentication Errors**
- Verify `box_config.json` is correctly formatted
- Ensure private key has proper newlines (`\n`)
- Check enterprise ID is correct

---

## Webhook Signature Validation (Optional - Production)

For production deployment, validate Box webhook signatures:

```python
import hmac
import hashlib

def validate_box_signature(body: bytes, headers: dict, primary_key: str, secondary_key: str) -> bool:
    """Validate Box webhook signature"""

    signature = headers.get('box-signature-primary')
    timestamp = headers.get('box-delivery-timestamp')

    # Construct message
    message = body + timestamp.encode()

    # Calculate HMAC
    expected_signature = hmac.new(
        primary_key.encode(),
        message,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)
```

Add this to your webhook handler for security.

---

## Next Steps

✅ Box app created and authorized
✅ Metadata template created
✅ Webhook configured

**Now you're ready to:**
- Upload geotagged photos to Box
- Watch GeoBox automatically enrich them with GPS metadata
- Search Box files by location using Box AI

**Happy geocoding! 🌍**
