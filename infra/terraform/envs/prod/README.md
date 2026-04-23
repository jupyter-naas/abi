# prod

Placeholder for the `prod` environment (issue milestone M9).

Same starting point as `staging`, with:

- `one_nat_gateway_per_az = true`
- Stricter backup retention (30 days), cross-region snapshot copy
- `deletion_protection = true` everywhere
- Dedicated VPC CIDR (`10.30.0.0/16`)
- Apply gated on manual `workflow_dispatch` only
