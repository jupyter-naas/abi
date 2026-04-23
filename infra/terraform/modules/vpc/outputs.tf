output "vpc_id" { value = module.vpc.vpc_id }
output "private_subnets" { value = module.vpc.private_subnets }
output "public_subnets" { value = module.vpc.public_subnets }
output "database_subnets" { value = module.vpc.database_subnets }
output "database_subnet_group" { value = module.vpc.database_subnet_group_name }
output "azs" { value = local.azs }
output "vpc_cidr" { value = module.vpc.vpc_cidr_block }
