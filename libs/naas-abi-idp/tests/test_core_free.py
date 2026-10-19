"""The provider is a module over NATS: it never imports the engine, or Nexus."""

import subprocess
import sys


def test_importing_the_provider_loads_neither_core_nor_nexus():
    code = (
        "import naas_abi_idp.__main__, naas_abi_idp.module, naas_abi_idp.web, "
        "naas_abi_idp.admin, sys; "
        "bad = sorted(m for m in sys.modules if m.split('.')[0] in "
        "('naas_abi_core', 'naas_abi', 'naas_abi_cli', 'naas_abi_marketplace')); "
        "sys.exit('imported: ' + ', '.join(bad) if bad else 0)"
    )
    done = subprocess.run(
        [sys.executable, "-I", "-c", code], check=False, capture_output=True, text=True
    )
    assert done.returncode == 0, done.stderr or done.stdout
