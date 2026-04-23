project         = "{{ project }}"
env             = "{{ env }}"
region          = "{{ region }}"
synapse_enabled = {{ "true" if synapse_enabled else "false" }}
multi_tenant    = {{ "true" if multi_tenant else "false" }}
