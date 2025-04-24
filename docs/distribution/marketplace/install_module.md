# Installing from the Marketplace (Alpha)

To use a module from the Marketplace:

1. **Copy the module to your custom modules directory**:
   ```bash
   cp -r marketplace/module_name/ src/custom/modules/
   ```

2. **Install dependencies**:
   ```bash
   # Check the module's README.md for dependency requirements
   make add dep="required_package1 required_package2"
   ```

3. **Configure if needed**:
   - Update your `config.yaml` file with any required settings
   - Set any environment variables needed by the module

4. **Use the module**:
   - The module will be automatically discovered and loaded
   - Access its agents, workflows, pipelines, and integrations as you would any custom module
