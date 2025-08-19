# Agent Memory

Your ABI agent remembers conversations across restarts. No more repeating yourself every time you start a new session.

## Quick Setup

```bash
# 1. Add to your .env file
POSTGRES_URL="postgresql://abi_user:abi_password@localhost:5432/abi_memory"

# 2. Start services
make dev-up

# 3. Run agent (now with memory!)
make
```

## See It Work

**Session 1:**
```
You: what am i fan of?
Abi: Based on what you've shared, you're a basketball fan! Do you have a favorite 
     team or player that you're especially excited about?

You: the warriors
Abi: You're a fan of the Warriors! The Golden State Warriors are known for their 
     fast, high-scoring gameplay...
```

*Agent restarts*

**Session 2:**
```
You: what am i fan of?
Abi: Based on what you've shared, you're a basketball fan! Do you have a favorite 
     team or player that you're especially excited about?
```

**It remembered!** No `POSTGRES_URL`? Agent uses in-memory storage (forgets on restart).

## Troubleshooting

**Memory not working?**
```bash
# Check if PostgreSQL is running
make dev-up

# Verify environment variable
echo $POSTGRES_URL

# Check agent logs for memory messages
make
```

**Common fixes:**
- `Connection refused` → Run `make dev-up`
- `Database not found` → Check database name in `POSTGRES_URL`
- `Permission denied` → Check username/password in `POSTGRES_URL`

That's it. Your agent now builds relationships instead of starting from scratch every time.
