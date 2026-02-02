# DigitalOcean Droplet Deployment Guide

## 🚀 Deploy to DigitalOcean Droplet (VPS)

A Droplet is a virtual server where you have full control - perfect for running Docker containers!

---

## Step 1: Create a Droplet

1. Go to [DigitalOcean Dashboard](https://cloud.digitalocean.com/droplets)
2. Click **"Create"** → **"Droplets"**
3. **Choose an image:**
   - Select **"Ubuntu 22.04 (LTS)"** (recommended)
4. **Choose a plan:**
   - **Minimum for headful mode:** 
     - **Regular:** 2 vCPU, 4GB RAM ($24/month)
     - **Or Basic:** 2 vCPU, 4GB RAM ($24/month)
   - **For testing:** 1 vCPU, 2GB RAM ($12/month) - might be tight for headful
5. **Choose a datacenter region:**
   - Pick closest to you
6. **Authentication:**
   - Add SSH key (recommended) or use password
7. **Finalize:**
   - Give it a hostname: `seleniumbase-api`
   - Click **"Create Droplet"**

---

## Step 2: Connect to Your Droplet

### Get Your Droplet IP

After creation, you'll see the IP address (e.g., `123.45.67.89`)

### Connect via SSH

```bash
# If you used SSH key
ssh root@YOUR_DROPLET_IP

# If you used password
ssh root@YOUR_DROPLET_IP
# Enter password when prompted
```

---

## Step 3: Set Up the Server

### Update System

```bash
# Update packages
apt-get update
apt-get upgrade -y
```

### Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Start Docker
systemctl start docker
systemctl enable docker

# Verify Docker
docker --version
```

### Install Docker Compose (Optional)

```bash
# Install Docker Compose
apt-get install docker-compose -y

# Or use newer version
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

---

## Step 4: Transfer Your Files

### Option A: Using SCP (from your Mac)

```bash
# From your Mac terminal
cd /Users/priyesh/Desktop/selenium-base/examples/cdp_mode

# Copy files to droplet
scp -r * root@YOUR_DROPLET_IP:/root/seleniumbase-api/
```

### Option B: Using Git (Recommended)

```bash
# On the Droplet
cd /root
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO/examples/cdp_mode
```

### Option C: Using wget/curl

```bash
# If you have files on a server or GitHub
cd /root
wget YOUR_FILE_URL
# Or use curl
```

---

## Step 5: Build and Run Docker Container

### On Your Droplet

```bash
cd /root/seleniumbase-api  # or wherever you put the files

# Build the Docker image
docker build -f Dockerfile.slim -t google-search-api:latest .

# Run the container
docker run -d \
  --name google-search-api \
  --restart unless-stopped \
  -p 5000:5000 \
  --security-opt seccomp=unconfined \
  --shm-size=2gb \
  -e DISPLAY=:100 \
  -e PYTHONUNBUFFERED=1 \
  google-search-api:latest \
  python3 /app/scripts/api_google_search.py
```

### Or Use Docker Compose

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  google-search-api:
    build:
      context: .
      dockerfile: Dockerfile.slim
    container_name: google-search-api
    ports:
      - "5000:5000"
    environment:
      - PYTHONUNBUFFERED=1
      - DISPLAY=:100
      - TZ=UTC
    security_opt:
      - seccomp:unconfined
    shm_size: '2gb'
    restart: unless-stopped
    command: python3 /app/scripts/api_google_search.py
```

Then run:

```bash
docker-compose -f docker-compose.prod.yml up -d
```

---

## Step 6: Set Up Firewall

### Allow Port 5000

```bash
# Install UFW (if not installed)
apt-get install ufw -y

# Allow SSH (important!)
ufw allow 22/tcp

# Allow your API port
ufw allow 5000/tcp

# Enable firewall
ufw enable

# Check status
ufw status
```

---

## Step 7: Access Your API

### Test Locally on Droplet

```bash
# Check if container is running
docker ps

# Check logs
docker logs google-search-api

# Test API
curl http://localhost:5000/health
```

### Access from Outside

Your API will be available at:
```
http://YOUR_DROPLET_IP:5000
```

Test from your Mac:
```bash
curl http://YOUR_DROPLET_IP:5000/health
```

---

## Step 8: Set Up Domain (Optional)

### Point Domain to Droplet

1. Go to your domain registrar
2. Add A record:
   - **Host:** `@` or `api`
   - **Value:** `YOUR_DROPLET_IP`
   - **TTL:** 3600

### Install Nginx (Reverse Proxy)

```bash
# Install Nginx
apt-get install nginx -y

# Create config
nano /etc/nginx/sites-available/api
```

Add this config:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable and restart:

```bash
ln -s /etc/nginx/sites-available/api /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

---

## Step 9: Set Up SSL (HTTPS) - Optional but Recommended

### Using Let's Encrypt (Free)

```bash
# Install Certbot
apt-get install certbot python3-certbot-nginx -y

# Get SSL certificate
certbot --nginx -d your-domain.com

# Auto-renewal is set up automatically
```

---

## 🔧 Useful Commands

### Docker Management

```bash
# View running containers
docker ps

# View logs
docker logs google-search-api
docker logs -f google-search-api  # Follow logs

# Restart container
docker restart google-search-api

# Stop container
docker stop google-search-api

# Start container
docker start google-search-api

# Remove container
docker rm google-search-api

# Rebuild and restart
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
```

### System Monitoring

```bash
# Check disk space
df -h

# Check memory
free -h

# Check CPU
top

# Check Docker resources
docker stats
```

---

## 🎯 Quick Start Script

Create a setup script on your Droplet:

```bash
nano setup.sh
```

Paste this:

```bash
#!/bin/bash

# Update system
apt-get update
apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
systemctl start docker
systemctl enable docker

# Install Docker Compose
apt-get install docker-compose -y

# Install firewall
apt-get install ufw -y
ufw allow 22/tcp
ufw allow 5000/tcp
ufw enable

# Build and run
cd /root/seleniumbase-api
docker build -f Dockerfile.slim -t google-search-api:latest .
docker run -d \
  --name google-search-api \
  --restart unless-stopped \
  -p 5000:5000 \
  --security-opt seccomp=unconfined \
  --shm-size=2gb \
  -e DISPLAY=:100 \
  google-search-api:latest \
  python3 /app/scripts/api_google_search.py

echo "Setup complete! API running on http://$(curl -s ifconfig.me):5000"
```

Make it executable:

```bash
chmod +x setup.sh
./setup.sh
```

---

## 💰 Cost Estimate

- **2 vCPU, 4GB RAM:** $24/month
- **1 vCPU, 2GB RAM:** $12/month (might be tight for headful)

**With $200 free credit:** You get ~8 months free on 2 vCPU plan!

---

## ✅ Checklist

- [ ] Created Droplet (2 vCPU, 4GB RAM)
- [ ] Connected via SSH
- [ ] Installed Docker
- [ ] Transferred files
- [ ] Built Docker image
- [ ] Started container
- [ ] Opened firewall port 5000
- [ ] Tested API: `curl http://YOUR_IP:5000/health`
- [ ] (Optional) Set up domain
- [ ] (Optional) Set up SSL

---

## 🆘 Troubleshooting

### Container won't start
```bash
# Check logs
docker logs google-search-api

# Check if port is in use
netstat -tulpn | grep 5000
```

### Can't access from outside
```bash
# Check firewall
ufw status

# Check if container is running
docker ps

# Test locally first
curl http://localhost:5000/health
```

### Out of memory
```bash
# Check memory usage
free -h
docker stats

# Consider upgrading Droplet
```

---

## 🎉 You're Done!

Your API is now live at:
```
http://YOUR_DROPLET_IP:5000
```

Test it:
```bash
curl -X POST http://YOUR_DROPLET_IP:5000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "best hotels"}'
```
