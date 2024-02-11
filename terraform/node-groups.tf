################################################################################
# EKS Node Groups
################################################################################
module "eks_managed_node_group" {
  source = "terraform-aws-modules/eks/aws//modules/eks-managed-node-group"
  version = "~> 19.13"

  count = local.create_node_groups ? 5 : 0

  # set name to team- count.index + 1
  name = "team-${count.index + 1}"
  use_name_prefix = false

  cluster_name                   = local.name
  cluster_version                = local.cluster_version

  create_iam_role = false
  iam_role_arn = aws_iam_role.node[0].arn


  subnet_ids = module.vpc.private_subnets

  // The following variables are necessary if you decide to use the module outside of the parent EKS module context.
  // Without it, the security groups of the nodes are empty and thus won't join the cluster.
  cluster_primary_security_group_id = module.eks.cluster_primary_security_group_id
  vpc_security_group_ids            = [module.eks.node_security_group_id]

  instance_types = [count.index + 1 <= 3 ? "t3.medium" : "m5.large" ]

  min_size     = 1
  max_size     = 3
  desired_size = 2
  labels = {
    type  = "node-group"
    event = "argocon-eu-2024"
    team  = "team-${count.index + 1}"
  }
  taints = {
    dedicated = {
      key    = "dedicated"
      value  = "team-${count.index + 1}"
      effect = "NO_SCHEDULE"
    }
  }
}