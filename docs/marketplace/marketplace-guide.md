# Marketplace Guide

## Overview

The Marketplace is a space for sharing and discovering custom modules that extend the functionality of the ABI system. It enables users to publish their own creations and utilize modules developed by others, fostering a collaborative ecosystem around the ABI framework.

## Purpose and Benefits

The Marketplace serves as a central repository for reusable components that:

- Accelerates development by providing ready-to-use modules
- Encourages sharing of domain-specific expertise
- Reduces duplication of effort across projects
- Creates a collaborative community around ABI extension
- Standardizes module development practices

## How It Works

The Marketplace is structured as a directory (`src/marketplace/`) containing self-contained modules that follow the standard ABI module architecture. Each module in the Marketplace is like an "atom" - a fundamental, independent building block that:

1. Is entirely self-contained and doesn't rely on other custom components
2. Has clear documentation and example usage
3. Follows standard ABI module structure
4. Can be easily installed in any ABI project

## Publishing to the Marketplace

To publish your custom module to the Marketplace:

1. **Prepare your module**:
   - Ensure it follows the standard directory structure
   - Include comprehensive documentation in README.md
   - Add appropriate tests
   - Make sure all dependencies are documented

2. **Move to Marketplace**:
   ```bash
   # From your ABI project root
   cp -r src/custom/modules/your_module_name/ src/marketplace/
   ```

3. **Document your module**:
   - Add a detailed README.md file in your module directory
   - Include configuration examples, usage instructions, and API documentation
   - Document any required environment variables or configuration

## Installing from the Marketplace

To use a module from the Marketplace:

1. **Copy the module to your custom modules directory**:
   ```bash
   cp -r src/marketplace/module_name/ src/custom/modules/
   ```

2. **Install dependencies**:
   ```bash
   # Check the module's README.md for dependency requirements
   make add dep="required_package1 required_package2"
   ```

3. **Configure as needed**:
   - Update your `config.yaml` file with any required settings
   - Set any environment variables needed by the module

4. **Use the module**:
   - The module will be automatically discovered and loaded
   - Access its assistants, workflows, pipelines, and integrations as you would any custom module

## Best Practices

When creating modules for the Marketplace:

1. **Self-contained design**: Minimize dependencies on other custom modules
2. **Clear documentation**: Include detailed README, examples, and configuration instructions
3. **Comprehensive testing**: Include tests to validate functionality
4. **Version control**: Include version information in your module documentation
5. **Standard structure**: Follow the ABI module structure conventions
6. **License information**: Include license details for your module (freemium, open source, closed source, service-based implementation)

## Current Limitations

The Marketplace is currently in alpha stage, which means:

- There is no automated publishing process yet
- Dependency management is manual
- Version control is limited to documentation
- No centralized web interface for browsing modules 
- Limited validation of module quality or security

Despite these limitations, the Marketplace can already be leveraged to share and reuse functionality across projects.

## Future Plans

Future enhancements to the Marketplace may include:

- Web interface for browsing available modules in naas.ai/search
- Automated publishing and installation process
- Versioning and dependency management
- Rating and review system
- Security validation
- Community contribution guidelines

## Contributing to the Marketplace

We encourage all users to consider contributing their custom modules to the Marketplace. By sharing your work, you help grow the ABI ecosystem and benefit from community feedback and improvements.

For questions or support with the Marketplace, please reach out via [support@naas.ai](mailto:support@naas.ai) or on our [community forum](https://join.slack.com/t/naas-club/shared_invite/zt-2xmz8c3j8-OH3UAqvwsYkTR3BLRHGXeQ) on Slack.
