# 🚀 Slim Headful Mode Test Guide

Test your Google search script in **headful mode** with **minimal dependencies** in Docker!

---

## 📦 What's Different?

### **Slim Version:**
```
✅ Package only (pip install seleniumbase)
✅ Minimal dependencies (Chrome + Xvfb + Python)
✅ Small image (~400-500MB vs 800MB)
✅ Headful mode with Xvfb
✅ Just runs your script, no API
```

### **vs Full Version:**
```
❌ Cloned entire repo
❌ 50+ dependencies
❌ 800MB+ image
✅ Same stealthiness (no difference!)
```

---

## 🧪 Quick Test

### **Option 1: Docker Compose (Easiest)**

```bash
cd /Users/priyesh/Desktop/selenium-base/examples/cdp_mode

# Build and run
docker-compose -f docker-compose.slim.yml up --build

# View output
docker logs google-search-test-headful

# Cleanup
docker-compose -f docker-compose.slim.yml down
```

### **Option 2: Docker Build & Run**

```bash
# Build slim image
docker build -f Dockerfile.slim -t google-search-slim:latest .

# Run it
docker run \
  --name test-headful \
  --shm-size=2g \
  google-search-slim:latest

# View logs
docker logs test-headful

# Cleanup
docker rm test-headful
```

---

## 📋 What to Look For

### **Expected Output:**

```
========================================
Starting Xvfb virtual display...
========================================
Waiting for Xvfb to initialize...
========================================
Running Google Search Script (HEADFUL MODE)
========================================
[*] Opening Google with Pure CDP Mode...
[*] Headless: False, Incognito: True
[*] Checking for CAPTCHA on homepage...
[+] No CAPTCHA on homepage
[*] Typing search query: hotels near me
[*] Submitting search using submit() method...
[*] Checking for CAPTCHA...

# If successful:
[+] No CAPTCHA detected, proceeding...
[*] Page Title: hotels near me - Google Search
[+] Successfully loaded search results!
[*] All search results:
  1. Result title 1
  2. Result title 2
  ...
[*] Bot evasion test complete!

# If CAPTCHA appears:
[!] CAPTCHA detected - cannot auto-solve
[!] Options:
    1. Use proxies to avoid CAPTCHAs
    2. Use CAPTCHA solving service (2Captcha, Anti-Captcha)
    3. Reduce request frequency

========================================
Script completed!
========================================
```

---

## 🔍 Verify Headful Mode is Working

```bash
# Check if script ran in headful mode
docker logs test-headful | grep "Headless"

# Should show:
# [*] Headless: False, Incognito: True

# Check if Xvfb started
docker logs test-headful | grep "Xvfb"

# Should show:
# Starting Xvfb virtual display...
```

---

## ⚙️ Customize Before Testing

Edit `raw_cdp_google_submit.py`:

```python
# Change search query
search_query = "your search here"

# Test with proxy
proxy = "user:pass@proxy.com:8080"

# Force headful mode
headless = False  # Already set
```

---

## 📊 Compare Image Sizes

```bash
# Check slim image size
docker images google-search-slim

# Should be ~400-500MB

# vs full image (if you built it)
docker images google-search-api

# Would be ~800MB+
```

---

## 🐛 Troubleshooting

### Issue: "Cannot open display"

```bash
# Xvfb might not be starting
# Check logs:
docker logs test-headful

# Increase sleep time in Dockerfile:
sleep 3  # to: sleep 5
```

### Issue: Still getting CAPTCHAs

```
This is normal! Headful mode helps but doesn't eliminate CAPTCHAs.

Solutions:
1. Add residential proxies
2. Increase delays between searches
3. Use 2Captcha API
```

### Issue: Chrome crashes

```bash
# Increase shared memory
docker run --shm-size=2g ...

# Already set in docker-compose.slim.yml
```

---

## 🎯 Next Steps

### **If Test Succeeds:**

1. **Compare with headless:**
   - Change `headless = True` in script
   - Rebuild and run
   - Compare CAPTCHA rates

2. **Deploy for real:**
   - Use this Dockerfile for production
   - Add API wrapper if needed
   - Add proxies for better results

### **If Test Fails:**

1. Check logs for errors
2. Verify Xvfb is running
3. Confirm Chrome is installed
4. Check shared memory size

---

## 💡 Benefits of Slim Version

```
✅ 50% smaller image size
✅ Faster builds (less to install)
✅ Fewer dependencies = fewer vulnerabilities
✅ Cleaner, more maintainable
✅ SAME stealthiness as full version
✅ Headful mode works perfectly
```

---

## 🔄 Switching Back to Headless

If you want to test headless vs headful:

```python
# In raw_cdp_google_submit.py
headless = True  # Change to True

# Rebuild
docker build -f Dockerfile.slim -t google-search-slim:headless .

# Run
docker run google-search-slim:headless
```

---

## 📝 Files Created

```
cdp_mode/
├── Dockerfile.slim              # Minimal Docker image
├── docker-compose.slim.yml      # Easy deployment
├── SLIM_TEST.md                 # This guide
└── raw_cdp_google_submit.py     # Your script (already exists)
```

---

## ✅ Quick Checklist

Before testing:

- [ ] Edited search query in `raw_cdp_google_submit.py`
- [ ] Set `headless = False` in script
- [ ] Have Docker running
- [ ] Have 2GB+ RAM available

Run test:

- [ ] `docker-compose -f docker-compose.slim.yml up --build`
- [ ] Check logs for "Headless: False"
- [ ] See if CAPTCHA appears
- [ ] Note success rate

---

**Ready to test!** 🎯

Run: `docker-compose -f docker-compose.slim.yml up --build`
