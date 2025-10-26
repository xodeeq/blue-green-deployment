# Blue/Green Deployment with Nginx Auto-Failover

Complete implementation of Blue/Green deployment with automatic failover and zero-downtime switching.

## Quick Start

### 1. Start the system
```bash
docker-compose up -d
```

### 2. Wait for services to be healthy
```bash
docker-compose ps
```

### 3. Test the deployment
```bash
# Test through Nginx (should hit Blue)
curl -i http://localhost:8080/version

# Run automated tests
./test-failover.sh
```

## Testing Failover Manually

### Step 1: Verify Blue is active
```bash
curl -i http://localhost:8080/version
# Should show: X-App-Pool: blue
```

### Step 2: Trigger chaos on Blue
```bash
curl -X POST http://localhost:8081/chaos/start?mode=error
```

### Step 3: Watch automatic failover
```bash
for i in {1..10}; do
  curl -s http://localhost:8080/version | grep X-App-Pool
  sleep 0.5
done
# Should show: X-App-Pool: green (all requests succeed!)
```

### Step 4: Stop chaos
```bash
curl -X POST http://localhost:8081/chaos/stop
```

## Manual Toggle (Blue ↔ Green)

### Switch to Green
```bash
sed -i 's/ACTIVE_POOL=blue/ACTIVE_POOL=green/' .env
docker-compose up -d --force-recreate nginx
```

### Verify
```bash
curl -i http://localhost:8080/version
# Should show: X-App-Pool: green
```

## Useful Commands

```bash
# View logs
docker-compose logs -f nginx

# Check service status
docker-compose ps

# Restart everything
docker-compose restart

# Stop and clean up
docker-compose down
```

## Architecture

```
Client → Nginx:8080 → Blue:3000 (primary)
                    → Green:3000 (backup, used on Blue failure)
```

## Key Features

✅ Zero failed requests during failover  
✅ Automatic failover in <5 seconds  
✅ Headers preserved (X-App-Pool, X-Release-Id)  
✅ Manual toggle support  
✅ Comprehensive test suite  

## Troubleshooting

**Problem**: Containers won't start
```bash
docker-compose down
docker-compose up -d --force-recreate
```

**Problem**: Health checks failing
```bash
# Check app logs
docker-compose logs app_blue
docker-compose logs app_green
```

**Problem**: Failover not working
```bash
# Verify chaos is active
curl http://localhost:8081/version  # Should return 500

# Check Nginx logs
docker-compose logs nginx
```
