"""

Generate Karpenter from Node Groups

"""
import sys
import boto3
import yaml
from sharedlib import infra



def karpenter_mode(cluster, eks, ec2):
    """
    Migrate from Node Groups to Karpenter

    Order of operation:

    1.) Get Node Groups of EKS Cluster
    2.) Generate Karpenter NodeClass and NodePool for each Node Group
    """

    # Get the node groups
    for nodegroup_name in infra.get_eks_cluster_nodegroups(eks, cluster):
        # print all the information about the node group
        nodegroup = infra.get_node_group(eks, cluster, nodegroup_name)
        k8s_karpenter_node_pool = infra.get_custom_object(nodegroup_name, "NodePool")
        # skip if there is already a corresponding karpenter node pool
        if k8s_karpenter_node_pool is not None:
            continue
        karpenter_node_class = infra.generate_karpenter_node_class(
            eks, ec2, nodegroup)
        # print karpenter_node_class in yaml
        print("---")
        print(yaml.dump(karpenter_node_class, default_flow_style=False))
        karpenter_node_pool = infra.generate_karpenter_node_pool(nodegroup)
        print("---")
        print(yaml.dump(karpenter_node_pool, default_flow_style=False))
        # create custom object with the node class
        infra.apply_or_create_custom_object(karpenter_node_class, "EC2NodeClass")
        infra.apply_or_create_custom_object(karpenter_node_pool, "NodePool")

        # scale cluster-autoscaler to zero
        infra.scale_deployment(
            "aws-cluster-autoscaler", "kube-system", 0)
        # evict all pods by placing a NO_EXECUTE taint on the nodes
        # scale down to zero by updating scalingConfig, and set max to 1
        print("Scale down nodegroup "+nodegroup_name)
        infra.update_nodegroup(
            eks,
            clusterName=cluster,
            nodegroupName=nodegroup_name,
            scalingConfig={
                'desiredSize': 0,
                'minSize': 0,
                'maxSize': 1
            }
        )

    return None


def nodegroup_mode(cluster, eks):
    """
    Migrate from Karpenter to Node Groups

    Order of operation:

    1.) Get Node Groups of EKS Cluster
    2.) Restore Scaling Config from corresponding NodePool
    3.) Delete NodePool and NodeClass
    """

    # Get the node groups
    for nodegroup_name in infra.get_eks_cluster_nodegroups(eks, cluster):
        # Get the corresponding karpenter node pool
        print("Restoring Node Group "+nodegroup_name +
              " from corresponding NodePool")
        k8s_karpenter_node_pool = infra.get_custom_object(nodegroup_name, "NodePool")
        # if k8s_karpenter_node_pool is None then continue
        if k8s_karpenter_node_pool is None:
            continue
        # Get the scaling config from annotations
        min_size = int(
            k8s_karpenter_node_pool['metadata']['annotations']['migrate.karpenter.io/min'])
        max_size = int(
            k8s_karpenter_node_pool['metadata']['annotations']['migrate.karpenter.io/max'])
        desired_size = int(
            k8s_karpenter_node_pool['metadata']['annotations']['migrate.karpenter.io/desired'])
        # restore scalingConfig
        print("Restoring scaling config for nodegroup "+nodegroup_name)
        infra.update_nodegroup(
            eks,
            clusterName=cluster,
            nodegroupName=nodegroup_name,
            scalingConfig={
                'desiredSize': desired_size,
                'minSize': min_size,
                'maxSize': max_size
            }
        )
        # scale cluster-autoscaler from zero
        infra.scale_deployment(
            "aws-cluster-autoscaler", "kube-system", 1)

        # Delete nodepool and nodeclass
        print("Deleting NodePool"+nodegroup_name)
        infra.delete_custom_object(nodegroup_name, "NodePool")
        print("Deleting NodeClass for nodegroup "+nodegroup_name)
        infra.delete_custom_object(nodegroup_name, "EC2NodeClass")

    return None


def parse_command_line_option(argv):
    if len(argv) < 4:
        print("Usage: python karpenter-migrator.py <karpenter | nodegroup> <clusterName> <region>")
        sys.exit(2)

    mode = argv[1]
    cluster_name = argv[2]
    region = argv[3]
    # print("Cluster="+cluster_name+", Region="+region)
    # AWS Credentials https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html
    session = boto3.Session()
    eks = session.client('eks', region_name=region)
    ec2 = session.client('ec2', region_name=region)
    if mode == "karpenter":
        karpenter_mode(cluster_name, eks, ec2)
        return None
    elif mode == "nodegroup":
        nodegroup_mode(cluster_name, eks)
        return None
    else:
        print("Mode %s is not supported. Please use karpenter or nodegroup" % mode)


if __name__ == "__main__":
    parse_command_line_option(sys.argv)
