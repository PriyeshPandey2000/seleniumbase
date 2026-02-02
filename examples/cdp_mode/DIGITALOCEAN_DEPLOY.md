# DigitalOcean Deployment Guide

## 🚀 Two Ways to Deploy

### Option 1: Deploy from GitHub (Easiest - Recommended)

**Yes, you need to push to GitHub first.**

#### Step 1: Push to GitHub

```bash
cd /Users/priyesh/Desktop/selenium-base

# Check if you have a git repo
git status

# If not initialized, initialize it
git init
git add .
git commit -m "Add SeleniumBase CDP API"

# Create a new GitHub repository
# Go to github.com → New Repository → Create

# Add remote and push
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git branch -M main
git push -u origin main
```

**Or if you already have a repo:**
```bash
git add examples/cdp_mode/
git commit -m "Add CDP API for DigitalOcean"
git push
```

#### Step 2: Deploy on DigitalOcean

1. Go to [digitalocean.com](https://www.digitalocean.com)
2. Sign up/Login
3. Click **"Create"** → **"App Platform"**
4. Click **"GitHub"** → Authorize DigitalOcean
5. Select your repository
6. Select branch: `main`
7. **Root Directory:** `examples/cdp_mode`
8. **Build Command:** (leave empty - Docker will handle it)
9. **Run Command:** `python3 /app/scripts/api_google_search.py`
10. **Resources:**
    - **CPU:** 2 vCPU
    - **RAM:** 4GB
    - **Storage:** 1GB
11. Click **"Deploy"**

---

### Option 2: Deploy from Docker Hub (No GitHub Needed!)

**You can skip GitHub and use Docker Hub instead.**

#### Step 1: Build and Push to Docker Hub

```bash
cd /Users/priyesh/Desktop/selenium-base/examples/cdp_mode

# Login to Docker Hub
docker login

# Build the image
docker build -f Dockerfile.slim -t YOUR_DOCKERHUB_USERNAME/google-search-api:latest .

# Push to Docker Hub
docker push YOUR_DOCKERHUB_USERNAME/google-search-api:latest
```

#### Step 2: Deploy on DigitalOcean

1. Go to [digitalocean.com](https://www.digitalocean.com)
2. Click **"Create"** → **"App Platform"**
3. Click **"Docker Hub"** (or "Container Registry")
4. Enter image: `YOUR_DOCKERHUB_USERNAME/google-search-api:latest`
5. **Run Command:** `python3 /app/scripts/api_google_search.py`
6. **Resources:**
    - **CPU:** 2 vCPU
    - **RAM:** 4GB
7. Click **"Deploy"**

---

## 🎯 Which Option to Choose?

### Use GitHub if:
- ✅ You want automatic deployments on git push
- ✅ You want version control
- ✅ You want to track changes
- ✅ You're comfortable with git

### Use Docker Hub if:
- ✅ You don't want to use GitHub
- ✅ You just want to deploy once
- ✅ You prefer Docker workflow
- ✅ You already have Docker Hub account

---

## 📝 Quick GitHub Setup (If You Choose Option 1)

### Create .gitignore (if needed)

```bash
cd /Users/priyesh/Desktop/selenium-base
cat > .gitignore << EOF
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/

# Screenshots (optional - you might want to keep them)
*.png
*.jpg

# Docker
.dockerignore

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
EOF
```

### Push to GitHub

```bash
# Initialize if needed
git init

# Add files
git add .

# Commit
git commit -m "Initial commit: SeleniumBase CDP API"

# Create repo on GitHub first, then:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

---

## 🔧 DigitalOcean Configuration

### Important Settings:

1. **Root Directory:** `examples/cdp_mode`
2. **Build Command:** (empty - Docker handles it)
3. **Run Command:** `python3 /app/scripts/api_google_search.py`
4. **Port:** `5000`
5. **Environment Variables:** (optional)
   - `PYTHONUNBUFFERED=1`
   - `DISPLAY=:100`
   - `TZ=UTC`

### Resources:
- **CPU:** 2 vCPU (minimum for headful)
- **RAM:** 4GB (minimum for headful)
- **Storage:** 1GB

---

## ✅ After Deployment

Your API will be available at:
```
https://your-app-name.ondigitalocean.app
```

### Test It:

```bash
# Health check
curl https://your-app-name.ondigitalocean.app/health

# Search
curl -X POST https://your-app-name.ondigitalocean.app/search \
  -H "Content-Type: application/json" \
  -d '{"query": "best hotels"}'
```

---

## 💡 Pro Tips

1. **Start with Docker Hub** if you want to test quickly
2. **Switch to GitHub** later for auto-deployments
3. **Monitor usage** in DigitalOcean dashboard
4. **Set up alerts** for resource usage
5. **Use $200 free credit** for new users!

---

## 🆘 Troubleshooting

### If deployment fails:
1. Check logs in DigitalOcean dashboard
2. Verify Dockerfile is correct
3. Ensure port 5000 is exposed
4. Check resource limits (need 2 vCPU, 4GB RAM)

### If API doesn't respond:
1. Check if Flask is installed (it is in Dockerfile)
2. Verify run command is correct
3. Check environment variables

---

## 🎯 Recommendation

**For first-time deployment: Use Docker Hub (Option 2)**
- Faster setup
- No GitHub needed
- Test quickly

**For production: Use GitHub (Option 1)**
- Auto-deployments
- Version control
- Better workflow
