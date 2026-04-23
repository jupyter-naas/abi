---
sidebar_position: 1
---

# Add secrets to production

## About secrets

The API will used the secrets stored in your github repository secrets.
If you want to add new secrets, you need to do the following:
1. **Navigate to your repository's Settings > Secrets and variables > Actions and add the new secrets**
2. **Open `.github/workflows/deploy_api.yml**
3. **Add your github secrets in the env section of the**: "Push latest abi container"
4. **Pass the secrets to space environment in `ENV_CONFIG`**
5. **Commit and push your changes**