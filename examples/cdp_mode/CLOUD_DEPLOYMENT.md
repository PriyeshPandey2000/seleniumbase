# Cloud Deployment Guide for Google Search CDP API

## 🚀 Google Cloud Run (Recommended - Most Generous Free Tier)

### Why Google Cloud Run?
- ✅ **2 million requests/month FREE**
- ✅ **360,000 GB-seconds FREE**
- ✅ **180,000 vCPU-seconds FREE**
- ✅ Pay only for what you use after free tier
- ✅ Auto-scaling
- ✅ HTTPS included
- ✅ Perfect for Docker containers

### Prerequisites
1. Google Cloud account (free $300 credit for new users)
2. Google Cloud SDK installed
3. Docker installed locally

### Deployment Steps

#### 1. Set up Google Cloud

```bash
# Install Google Cloud SDK (if not installed)
# macOS:
brew install google-cloud-sdk

# Login to Google Cloud
gcloud auth login

# Create a new project (or use existing)
gcloud projects create seleniumbase-api --name="SeleniumBase API"

# Set the project
gcloud config set project seleniumbase-api

# Enable required APIs
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
```

#### 2. Build and Push Docker Image

```bash
cd /Users/priyesh/Desktop/selenium-base/examples/cdp_mode

# Build the Docker image
docker build -f Dockerfile.slim -t gcr.io/$(gcloud config get-value project)/google-search-api:latest .

# Configure Docker to use gcloud as credential helper
gcloud auth configure-docker

# Push the image to Google Container Registry
docker push gcr.io/$(gcloud config get-value project)/google-search-api:latest
```

#### 3. Deploy to Cloud Run

```bash
# Deploy the container
gcloud run deploy google-search-api \
  --image gcr.io/$(gcloud config get-value project)/google-search-api:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --port 5000 \
  --set-env-vars "PYTHONUNBUFFERED=1" \
  --command "python3" \
  --args "/app/scripts/api_google_search.py"
```

#### 4. Access Your API

After deployment, you'll get a URL like:
```
https://google-search-api-xxxxx-uc.a.run.app
```

### Alternative: Deploy via Cloud Build (One Command)

```bash
# Build and deploy in one step
gcloud builds submit --tag gcr.io/$(gcloud config get-value project)/google-search-api

gcloud run deploy google-search-api \
  --image gcr.io/$(gcloud config get-value project)/google-search-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300
```

---

## 🚀 Fly.io (Alternative - Also Generous)

### Why Fly.io?
- ✅ 3 shared VMs free
- ✅ 160GB outbound data/month free
- ✅ Global edge network
- ✅ Simple deployment

### Deployment Steps

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login
fly auth login

# Create app
fly launch --name google-search-api

# Deploy
fly deploy
```

---

## 🚀 Railway (Simple & Fast)

### Why Railway?
- ✅ $5 free credit monthly
- ✅ Simple deployment
- ✅ Auto-deploy from GitHub

### Deployment Steps

1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub
3. New Project → Deploy from GitHub
4. Select your repository
5. Add Dockerfile path: `examples/cdp_mode/Dockerfile.slim`
6. Set start command: `python3 /app/scripts/api_google_search.py`
7. Deploy!

---

## 📝 Dockerfile for Cloud Deployment

Make sure your Dockerfile exposes port 5000:

```dockerfile
# Add this to Dockerfile.slim
EXPOSE 5000
```

---

## 🔧 Environment Variables

You can set environment variables in Cloud Run:

```bash
gcloud run services update google-search-api \
  --update-env-vars "ENV_VAR_NAME=value"
```

---

## 📊 Monitoring

### Google Cloud Run
- View logs: `gcloud run services logs read google-search-api`
- View metrics in Google Cloud Console

### Cost Estimation
- **Free tier covers**: ~2 million requests/month
- **After free tier**: ~$0.40 per million requests
- **Very affordable!**

---

## 🧪 Test Your Deployed API

```bash
# Health check
curl https://your-api-url.run.app/health

# Search
curl -X POST https://your-api-url.run.app/search \
  -H "Content-Type: application/json" \
  -d '{"query": "best hotels"}'

# Get screenshot
curl https://your-api-url.run.app/screenshot -o screenshot.png
```

---

## 💡 Tips

1. **Start with Google Cloud Run** - Most generous free tier
2. **Use Cloud Build** - Automates build and deploy
3. **Set up CI/CD** - Auto-deploy on git push
4. **Monitor usage** - Stay within free tier limits
5. **Use regions close to you** - Lower latency

---

## 🆓 Free Tier Comparison

| Provider | Free Tier | Best For |
|----------|-----------|----------|
| **Google Cloud Run** | 2M requests/month | **Most generous** |
| Fly.io | 3 VMs, 160GB data | Global edge |
| Railway | $5/month credit | Simple setup |
| Render | Limited free tier | Easy deployment |

**Recommendation: Start with Google Cloud Run!** 🎯
