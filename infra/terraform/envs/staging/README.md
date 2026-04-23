# staging

Placeholder for the `staging` environment (issue milestone M9).

Copy `envs/dev/` as a starting point and tune:

- `multi_az = true` for RDS, Neptune reader replica, Redis `num_cache_clusters = 2`, Amazon MQ `CLUSTER_MULTI_AZ`
- `deletion_protection = true` on stateful resources
- Larger instance types across the board
- Dedicated VPC CIDR (`10.20.0.0/16`)
