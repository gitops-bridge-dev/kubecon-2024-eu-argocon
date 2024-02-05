"""

Generate Karpenter from Node Groups

"""
from __future__ import print_function
import sys
import boto3
from botocore.exceptions import ClientError
from lib import *
import json
import yaml


def karpenter_mode(cluster, eks):
  """
  Do the work..

  Order of operation:

  1.) Get Node Groups of EKS Cluster
  2.) Generate Karpenter NodeClass and NodePool for each Node Group
  """

  # Get the node groups
  for nodegroup_name in get_eks_cluster_nodegroups(eks, cluster):
    # print all the information about the node group
    nodegroup = get_node_group(eks, cluster, nodegroup_name)
    #print(json.dumps(nodegroup, indent=2, cls=DateTimeEncoder))
    karpenter_node_class = get_karpenter_node_class(nodegroup)
    # print karpenter_node_class in yaml
    print("---")
    print(yaml.dump(karpenter_node_class, default_flow_style=False))
    karpenter_node_pool = get_karpenter_node_pool(nodegroup)
    print("---")
    print(yaml.dump(karpenter_node_pool, default_flow_style=False))
    # create custom object with the node class
    k8s_karpenter_node_class = apply_or_create_custom_object(karpenter_node_class, "EC2NodeClass")
    # pprint(k8s_karpenter_node_class)
    k8s_karpenter_node_pool = apply_or_create_custom_object(karpenter_node_pool, "NodePool")
    # pprint(k8s_karpenter_node_pool)

  return None



def parse_command_line_option(argv):

  ## DEBUG
  #main("default", "us-east-2")
  #return None

  if len(argv) < 4:
    print("Usage: python karpenter-migrator.py <karpenter | nodegroup> <clusterName> <region>")
    sys.exit(2)

   # AWS Credentials
  # https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html
  session = boto3.Session()

  mode = argv[1]
  cluster_name = argv[2]
  region = argv[3]
  #print("Cluster="+cluster_name+", Region="+region)
  eks = session.client('eks',region_name=region)
  if mode == "karpenter":
    karpenter_mode(cluster_name, eks)
    return None
  else:
    print("Mode nodegroup not implemented yet")

if __name__ == "__main__":
  parse_command_line_option(sys.argv)
