# Fly.io Deployment Guide

## 🚀 Quick Deploy Steps

### Step 1: Install Fly CLI

```bash
# On your Mac
curl -L https://fly.io/install.sh | sh

# Add to PATH (if needed)
export FLYCTL_INSTALL="/Users/$(whoami)/.fly"
export PATH="$FLYCTL_INSTALL/bin:$PATH"
```

### Step 2: Login to Fly.io

```bash
fly auth login
# Opens browser - sign up/login (NO payment method needed!)
```

### Step 3: Navigate to Your Project

```bash
cd /Users/priyesh/Desktop/selenium-base/examples/cdp_mode
```

### Step 4: Create Fly.io App

```bash
# Initialize Fly.io app
fly launch --name google-search-api --region bom

# When prompted:
# - App name: google-search-api (or choose your own)
# - Region: bom (Mumbai - closest to India) or choose closest
# - Postgres: No
# - Redis: No
```

### Step 5: Scale Resources (IMPORTANT!)

**Free tier is NOT enough - you MUST scale:**

```bash
# Scale to 2 vCPU and 2GB RAM (minimum for headful)
fly scale vm shared-cpu-2x --memory 2048

# Or scale to 4GB RAM (recommended for smooth operation)
fly scale vm shared-cpu-2x --memory 4096
```

### Step 6: Deploy

```bash
fly deploy
```

### Step 7: Check Your API

```bash
# Get your app URL
fly status

# Test it
curl https://google-search-api.fly.dev/health
```

---

## 📊 When to Upgrade Resources

### Free Tier (256MB RAM) - ❌ NOT ENOUGH
- **Won't work** for headful browser
- Chrome needs at least 1GB RAM
- Xvfb needs ~100MB
- Flask needs ~100MB
- **Total needed: ~2GB minimum**

### Minimum (2 vCPU, 2GB RAM) - ⚠️ Works but tight
**Cost: ~$10-11/month**

**When to use:**
- ✅ Testing/development
- ✅ Low traffic (< 10 requests/hour)
- ✅ Single user
- ⚠️ May be slow under load
- ⚠️ May crash if multiple requests

**Upgrade when:**
- Getting "out of memory" errors
- Requests timing out
- Multiple users
- Production use

### Recommended (2 vCPU, 4GB RAM) - ✅ Smooth
**Cost: ~$20-25/month**

**When to use:**
- ✅ Production use
- ✅ Multiple users
- ✅ Moderate traffic (10-100 requests/hour)
- ✅ Smooth operation
- ✅ No crashes

**Upgrade when:**
- High traffic (> 100 requests/hour)
- Multiple concurrent requests
- Need faster response times

### Optimal (4 vCPU, 8GB RAM) - 🚀 Best
**Cost: ~$42-43/month**

**When to use:**
- ✅ High traffic
- ✅ Multiple concurrent users
- ✅ Production at scale
- ✅ Fastest performance

---

## 🔧 Resource Scaling Commands

### Check Current Resources

```bash
fly scale show
```

### Scale Up (When Needed)

```bash
# Scale to 2GB RAM (minimum)
fly scale vm shared-cpu-2x --memory 2048

# Scale to 4GB RAM (recommended)
fly scale vm shared-cpu-2x --memory 4096

# Scale to 8GB RAM (optimal)
fly scale vm shared-cpu-2x --memory 8192
```

### Scale Down (To Save Money)

```bash
# Scale back to 2GB if 4GB is too much
fly scale vm shared-cpu-2x --memory 2048
```

---

## 💰 Cost Breakdown

| Resources | Monthly Cost | When to Use |
|-----------|--------------|-------------|
| **Free (256MB)** | $0 | ❌ Won't work |
| **2GB RAM** | ~$10-11 | Testing, low traffic |
| **4GB RAM** | ~$20-25 | Production, moderate traffic |
| **8GB RAM** | ~$42-43 | High traffic, scale |

---

## 🎯 Recommended Plan

### Start Here:
1. **Deploy with 2GB RAM** (~$10/month)
2. **Test your API**
3. **Monitor usage**

### Upgrade When:
- ✅ Getting memory errors → Scale to 4GB
- ✅ High traffic → Scale to 4GB or 8GB
- ✅ Production use → Start with 4GB

### Downgrade When:
- ✅ Low usage → Can scale back to 2GB
- ✅ Testing only → 2GB is fine

---

## 📝 Complete Deployment Script

Save this as `deploy-fly.sh`:

```bash
#!/bin/bash

cd /Users/priyesh/Desktop/selenium-base/examples/cdp_mode

# Install flyctl if not installed
if ! command -v fly &> /dev/null; then
    curl -L https://fly.io/install.sh | sh
    export FLYCTL_INSTALL="/Users/$(whoami)/.fly"
    export PATH="$FLYCTL_INSTALL/bin:$PATH"
fi

# Login
fly auth login

# Launch app (first time only)
# fly launch --name google-search-api --region bom

# Scale to minimum required (2GB RAM)
fly scale vm shared-cpu-2x --memory 2048

# Deploy
fly deploy

echo "✅ Deployed! API at: https://google-search-api.fly.dev"
echo "💰 Current cost: ~$10-11/month"
echo ""
echo "To upgrade to 4GB RAM (recommended):"
echo "  fly scale vm shared-cpu-2x --memory 4096"
```

Make it executable:
```bash
chmod +x deploy-fly.sh
./deploy-fly.sh
```

---

## 🔍 Monitoring

### Check App Status

```bash
# View app info
fly status

# View logs
fly logs

# View metrics
fly metrics
```

### Check Resource Usage

```bash
# See current resources
fly scale show

# Monitor in dashboard
fly dashboard
```

---

## ⚠️ Important Notes

1. **Free tier won't work** - Must scale to at least 2GB RAM
2. **Start with 2GB** - Test first, upgrade if needed
3. **4GB recommended** - For production use
4. **Monitor usage** - Scale up/down as needed
5. **No payment method needed** - For free tier, but you'll pay when scaling

---

## 🎯 Quick Start (Copy-Paste)

```bash
# 1. Install
curl -L https://fly.io/install.sh | sh

# 2. Login
fly auth login

# 3. Go to project
cd /Users/priyesh/Desktop/selenium-base/examples/cdp_mode

# 4. Launch (first time)
fly launch --name google-search-api --region bom

# 5. Scale to 2GB (minimum)
fly scale vm shared-cpu-2x --memory 2048

# 6. Deploy
fly deploy

# 7. Test
curl https://google-search-api.fly.dev/health
```

---

## 💡 Pro Tips

1. **Start small** - Deploy with 2GB, test, then upgrade
2. **Monitor costs** - Use `fly dashboard` to track usage
3. **Scale down** - If not using much, scale back to save money
4. **Use Mumbai region** - `bom` for lowest latency in India
5. **Set up alerts** - Monitor memory usage

---

## 🆘 Troubleshooting

### Out of Memory Errors
```bash
# Scale up
fly scale vm shared-cpu-2x --memory 4096
```

### App Won't Start
```bash
# Check logs
fly logs

# Check resources
fly scale show
```

### High Costs
```bash
# Scale down
fly scale vm shared-cpu-2x --memory 2048
```

---

## ✅ Summary

**Minimum to deploy:**
- 2 vCPU, 2GB RAM (~$10/month)

**Recommended:**
- 2 vCPU, 4GB RAM (~$20/month)

**Upgrade when:**
- Production use
- High traffic
- Memory errors

**Start with 2GB, upgrade to 4GB when needed!** 🚀
