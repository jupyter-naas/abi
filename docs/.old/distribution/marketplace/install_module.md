# Installing from the Marketplace

To use a module from the Marketplace:

## Method 1: Enable Marketplace Module Directly (Recommended)

1. **Enable the module by removing .disabled suffix**:
   ```bash
   # Navigate to marketplace modules
   cd src/marketplace/modules
   
   # Enable a module (e.g., arxiv)
   mv arxiv.disabled arxiv
   ```

2. **Install dependencies**:
   ```bash
   # Check the module's README.md for dependency requirements
   make add dep="required_package1 required_package2"
   ```

3. **Configure if needed**:
   - Set any environment variables needed by the module
   - Module-specific configuration via .env or module config files

4. **Use the module**:
   - The module will be automatically discovered and loaded on next system startup
   - Access its agents, workflows, pipelines, and integrations

## Method 2: Copy to Custom Modules

If you want to customize a marketplace module:

1. **Copy the module to your custom modules directory**:
   ```bash
   cp -r src/marketplace/module_name.disabled/ src/custom/modules/module_name/
   ```

2. **Follow steps 2-4 from Method 1**

## Disabling a Module

To disable any module temporarily:

```bash
# Add .disabled suffix
mv src/marketplace/module_name src/marketplace/module_name.disabled
```
