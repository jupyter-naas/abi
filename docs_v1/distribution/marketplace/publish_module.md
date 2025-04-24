# Publishing to the Marketplace (Alpha)

To publish your custom module to the Marketplace:

1. **Prepare your module**:
   - Ensure it follows the standard directory structure
   - Include a detailed README.md file in your module directory
   - Add appropriate tests
   - Make sure all dependencies are documented

2. **Move to Marketplace**:
   ```bash
   # From your ABI project root
   cp -r src/custom/modules/your_module_name/ marketplace/
   ```

3. **Open a PR on ABI and ask for review**:
   - We will review your module by reading the README.md file and testing the module.
   - Once approved, your module will be added to the Marketplace.