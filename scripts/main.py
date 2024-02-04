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


def main(profile, region):
  """
  Do the work..

  Order of operation:

  1.) Get Node Groups of EKS Cluster
  2.) Generate Karpenter NodeClass and NodePool for each Node Group
  """

  # AWS Credentials
  # https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html

  session = boto3.Session(profile_name=profile)
  eks = session.client('eks', region_name=region)
  ec2  = session.client('ec2', region_name=region)

  # Get the node groups
  for cluster in get_eks_clusters(eks):
    for nodegroup in get_eks_cluster_nodegroups(eks, cluster):
      # print all the information about the node group
      #print(json.dumps(get_node_group(client, cluster, nodegroup), indent=2, cls=DateTimeEncoder))
      #print(json.dumps(get_security_group_from_nodegroup(client, cluster, nodegroup, ec2), indent=2))
      karpenter_node_class = get_karpenter_node_class(eks, cluster, nodegroup)
      #print(json.dumps(karpenter_node_class, indent=2))
      # print karpenter_node_class in yaml
      print("---")
      print(yaml.dump(karpenter_node_class, default_flow_style=False))
      karpenter_node_pool = get_karpenter_node_pool(eks, cluster, nodegroup)
      print("---")
      print(yaml.dump(karpenter_node_pool, default_flow_style=False))
      # create custom object with the node class
      apply_or_create_custom_object(karpenter_node_class, "ec2nodeclasses")
      apply_or_create_custom_object(karpenter_node_pool, "nodepools")


  # v1 = client.CoreV1Api()
  # print("Listing pods with their IPs:")
  # ret = v1.list_pod_for_all_namespaces(watch=False)
  # for i in ret.items:
  #     print("%s\t%s\t%s" % (i.status.pod_ip, i.metadata.namespace, i.metadata.name))



  return



def parse_command_line_option(argv):

  ## DEBUG
  main("default", "us-east-2")
  return None

  if len(argv) != 3:
    print("Usage: python remove_eks.py <profile> <region>")
    sys.exit(2)

  profile = argv[1]
  region = argv[2]

  print("Profile="+profile+", Region="+region)

  main(profile, region)

if __name__ == "__main__":
  parse_command_line_option(sys.argv)
