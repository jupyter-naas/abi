# Publishing to the Marketplace

To publish your custom module to the Marketplace:

1. **Prepare your module**:
   - Ensure it follows the standard directory structure
   - Include a detailed README.md file in your module directory
   - Add appropriate tests
   - Make sure all dependencies are documented
   - Test thoroughly in your custom modules directory

2. **Add to Marketplace with .disabled suffix**:
   ```bash
   # From your ABI project root
   cp -r src/custom/modules/your_module_name/ src/marketplace/modules/your_module_name.disabled/
   ```

3. **Open a PR on ABI and ask for review**:
   - Submit a pull request with your new marketplace module
   - Include clear documentation and usage examples
   - We will review your module by reading the README.md file and testing the module
   - Once approved, your module will be available in the marketplace

## Publishing Guidelines

- **Self-contained**: Minimize dependencies on other custom modules
- **Well-documented**: Include comprehensive README with setup and usage instructions
- **Tested**: Include unit tests and integration tests
- **Versioned**: Include version information in your module documentation
- **Licensed**: Clearly state the license for your module