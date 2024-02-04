import sys
import boto3
from botocore.exceptions import ClientError
import time
import json
from datetime import datetime


def get_security_group_from_nodegroup(client, cluster, nodegroup, ec2):
  """
  Get the security group associated with the nodegroup
  """
  try:
      response = client.describe_nodegroup(
          clusterName=cluster,
          nodegroupName=nodegroup
      )
      launch_template_id = response['nodegroup']['launchTemplate']['id']
      # Describe the Launch Template to get its details
      launch_template = ec2.describe_launch_templates(LaunchTemplateIds=[launch_template_id])
      # Extract the security group IDs from the Launch Template
      return launch_template['LaunchTemplates'][0]['LaunchTemplateData']['SecurityGroupIds']
  except ClientError as e:
    print(e)
    return None
  return None


  return security_group_id


def get_karpenter_node_class(client, cluster, nodegroup):
  """
  Generate the Karpenter NodeClass
  """
  subnets = get_node_group_subnets(client, cluster, nodegroup)
  # iterate over the array of the subnets each element is a string
  # create a new array of map id: subnet
  subnets_map = [{"id": subnet} for subnet in subnets]
  karpenter_tags = {
                "karpenter.sh/discovery": cluster
            }
  node_group_tags = get_node_group_tags(client, cluster, nodegroup)
  tags = {**karpenter_tags, **node_group_tags}
  karpenter_ami_family = get_node_group_ami_family(client, cluster, nodegroup)
  iam_role_arn = get_node_group_iam_node_role(client, cluster, nodegroup)
  iam_role_name = iam_role_arn.split("/")[-1]

  return {
            "apiVersion": "karpenter.k8s.aws/v1beta1",
            "kind": "EC2NodeClass",
            "metadata": {
                "name": nodegroup
            },
            "spec": {
                "amiFamily": get_karpenter_ami_type(karpenter_ami_family),
                "role": iam_role_name,
                "subnetSelectorTerms": subnets_map,
                "securityGroupSelectorTerms":[
                    { "tags": { "karpenter.sh/discovery": cluster } }
                ],
                "tags": tags
            }
  }

def get_karpenter_node_pool(client, cluster, nodegroup):
  """
  Generate the Karpenter NodePool
  """

  capacity_type = get_node_group_capacity_type(client, cluster, nodegroup)
  # if capacity_type is SPOT set karpenter_capacity_type to "spot"
  # if capacity_type is ON_DEMAND set karpenter_capacity_type to "on-demand"
  karpenter_capacity_type = "on-demand" if capacity_type == "ON_DEMAND" else "spot"
  ami_family = get_node_group_ami_family(client, cluster, nodegroup)
  # if ami_family string contains ARM_64 set karpenter_arch to "arm64" else "amd64"
  # examples of ami_family string: "AL2_x86_64", "AL2_ARM_64", "BOTTLEROCKET_x86_64", "BOTTLEROCKET_ARM_64"
  karpenter_arch = "arm64" if "ARM_64" in ami_family else "amd64"
  instance_types = get_node_group_instance_types(client, cluster, nodegroup)
  new_labels = {
     "karpenter.io/nodegroup": nodegroup
     }
  nodegroup_labels = get_node_group_labels(client, cluster, nodegroup)
  labels = {**nodegroup_labels, **new_labels}
  return {
    "apiVersion": "karpenter.sh/v1beta1",
    "kind": "NodePool",
    "metadata": {
      "name": nodegroup
    },
    "spec": {
      "template":{
        "metadata": {
          "labels": labels
        },
        "spec": {
          "nodeClassRef": {
            "name": nodegroup
          },
          "requirements": [
            { "key": "karpenter.sh/capacity-type"             , "operator": "In", "values": [karpenter_capacity_type] },
            { "key": "karpenter.io/arch"                      , "operator": "In", "values": [karpenter_arch] },
            { "key": "karpenter.k8s.aws/instance-hypervisor"  , "operator": "In", "values": ["nitro"] },
            { "key": "node.kubernetes.io/instance-type"       , "operator": "In", "values": instance_types },
          ]
        }
      },
      "limits": {
          "cpu": 1000
      },
      "disruption":{
        "consolidationPolicy": "WhenEmpty",
        "consolidateAfter": "30s"
      }
    }
}










def get_karpenter_ami_type(ami_type):
  """
  Converts an input ami_type to karpenter_ami_type
  Input ami_type is one of this possible string values: AL2_x86_64,AL2_x86_64_GPU,AL2_ARM_64,CUSTOM,BOTTLEROCKET_ARM_64,BOTTLEROCKET_x86_64,BOTTLEROCKET_ARM_64_NVIDIA,BOTTLEROCKET_x86_64_NVIDIA,WINDOWS_CORE_2019_x86_64,WINDOWS_FULL_2019_x86_64,WINDOWS_CORE_2022_x86_64,WINDOWS_FULL_2022_x86_64
  Output karpenter_ami_type is one of this possible string values: AL2, Bottlerocket, Ubuntu, Windows2019, Windows2022 or Custom is there is no match
  """
  if ami_type == 'AL2_x86_64':
    return 'AL2'
  elif ami_type == 'AL2_x86_64_GPU':
    return 'AL2'
  elif ami_type == 'AL2_ARM_64':
    return 'AL2'
  elif ami_type == 'CUSTOM':
    return 'Custom'
  elif ami_type == 'BOTTLEROCKET_ARM_64':
    return 'Bottlerocket'
  elif ami_type == 'BOTTLEROCKET_x86_64':
    return 'Bottlerocket'
  elif ami_type == 'BOTTLEROCKET_ARM_64_NVIDIA':
    return 'Bottlerocket'
  elif ami_type == 'BOTTLEROCKET_x86_64_NVIDIA':
    return 'Bottlerocket'
  elif ami_type == 'WINDOWS_CORE_2019_x86_64':
    return 'Windows2019'
  elif ami_type == 'WINDOWS_FULL_2019_x86_64':
    return 'Windows2019'
  elif ami_type == 'WINDOWS_CORE_2022_x86_64':
    return 'Windows2022'
  elif ami_type == 'WINDOWS_FULL_2022_x86_64':
    return 'Windows2022'
  else:
    return 'Custom'

def get_node_group_iam_node_role(client, cluster, nodegroup):
    """
    Get the node group IAM node role
    """
    try:
        response = client.describe_nodegroup(
            clusterName=cluster,
            nodegroupName=nodegroup
        )
        return response['nodegroup']['nodeRole']
    except ClientError as e:
        print(e)
        return None
    return None

def get_node_group_subnets(client, cluster, nodegroup):
    """
    Get the node group subnets
    """
    try:
        response = client.describe_nodegroup(
            clusterName=cluster,
            nodegroupName=nodegroup
        )
        return response['nodegroup']['subnets']
    except ClientError as e:
        print(e)
        return None
    return None

def get_node_group_capacity_type(client, cluster, nodegroup):
    """
    Get the node group capacity type
    """
    try:
        response = client.describe_nodegroup(
            clusterName=cluster,
            nodegroupName=nodegroup
        )
        return response['nodegroup']['capacityType']
    except ClientError as e:
        print(e)
        return None
    return None


def get_node_group_scaling(client, cluster, nodegroup):
    """
    Get the node group scaling
    """
    try:
        response = client.describe_nodegroup(
            clusterName=cluster,
            nodegroupName=nodegroup
        )
        return response['nodegroup']['scalingConfig']
    except ClientError as e:
        print(e)
        return None
    return None

def get_node_group_labels(client, cluster, nodegroup):
    """
    Get the node group labels
    'labels': {
            'string': 'string'
        },
    """
    try:
        response = client.describe_nodegroup(
            clusterName=cluster,
            nodegroupName=nodegroup
        )
        return response['nodegroup']['labels']
    except ClientError as e:
        print(e)
        return None
    return None

def get_node_group_taints(client, cluster, nodegroup):
    """
    Get the node group taints
    'taints': [
            {
                'key': 'string',
                'value': 'string',
                'effect': 'NO_SCHEDULE'|'NO_EXECUTE'|'PREFER_NO_SCHEDULE'
            },
    ]
    """
    try:
        response = client.describe_nodegroup(
            clusterName=cluster,
            nodegroupName=nodegroup
        )
        # check if dict response['nodegroup'] contains key taints, if present return it if not present return empty array
        if 'taints' in response['nodegroup']:
            return response['nodegroup']['taints']
        else:
            return []
    except ClientError as e:
        print(e)
        return None
    return None

def get_node_group_instance_types(client, cluster, nodegroup):
    """
    Get the node group instance types
    """
    try:
        response = client.describe_nodegroup(
            clusterName=cluster,
            nodegroupName=nodegroup
        )
        return response['nodegroup']['instanceTypes']
    except ClientError as e:
        print(e)
        return None
    return None

def get_node_group_tags(client, cluster, nodegroup):
    """
    Get the node group tags
    """
    try:
        response = client.describe_nodegroup(
            clusterName=cluster,
            nodegroupName=nodegroup
        )
        return response['nodegroup']['tags']
    except ClientError as e:
        print(e)
        return None
    return None

def get_node_group_status(client, cluster, nodegroup):
    """
    Get the node group status
    'status': 'CREATING'|'ACTIVE'|'UPDATING'|'DELETING'|'CREATE_FAILED'|'DELETE_FAILED'|'DEGRADED',
    """
    try:
        response = client.describe_nodegroup(
            clusterName=cluster,
            nodegroupName=nodegroup
        )
        return response['nodegroup']['status']
    except ClientError as e:
        print(e)
        return None
    return None

def get_node_group_creation_time(client, cluster, nodegroup):
    """
    Get the node group creation time
    """
    try:
        response = client.describe_nodegroup(
            clusterName=cluster,
            nodegroupName=nodegroup
        )
        return response['nodegroup']['createdAt']
    except ClientError as e:
        print(e)
        return None
    return None

def get_node_group_ami_family(client, cluster, nodegroup):
    """
    Get the node group AMI type
    'amiType': 'AL2_x86_64'|'AL2_x86_64_GPU'|'AL2_ARM_64'|'CUSTOM'|'BOTTLEROCKET_ARM_64'|'BOTTLEROCKET_x86_64'|'BOTTLEROCKET_ARM_64_NVIDIA'|'BOTTLEROCKET_x86_64_NVIDIA'|'WINDOWS_CORE_2019_x86_64'|'WINDOWS_FULL_2019_x86_64'|'WINDOWS_CORE_2022_x86_64'|'WINDOWS_FULL_2022_x86_64',
    """
    try:
        response = client.describe_nodegroup(
            clusterName=cluster,
            nodegroupName=nodegroup
        )
        return response['nodegroup']['amiType']
    except ClientError as e:
        print(e)
        return None
    return None

def get_node_group(client, cluster, nodegroup):
    """
    Get the node group print
    """
    try:
        response = client.describe_nodegroup(
            clusterName=cluster,
            nodegroupName=nodegroup
        )
        return response['nodegroup']
    except ClientError as e:
        print(e)
        return None
    return None



def get_node_group_pretty_print(client, cluster, nodegroup):
    """
    Get the node group pretty print
    """
    print("---")
    print("Cluster: "+cluster)
    print("Node Group: "+nodegroup)
    print("Node Group AMI Type: "+get_node_group_ami_family(client, cluster, nodegroup))
    print("Node Group IAM Node Role: "+get_node_group_iam_node_role(client, cluster, nodegroup))
    subnets = get_node_group_subnets(client, cluster, nodegroup)
    print("Node Group Subnets: " + json.dumps(subnets))
    scaling = get_node_group_scaling(client, cluster, nodegroup)
    print("Node Group Scaling: " + json.dumps(scaling))
    labels = get_node_group_labels(client, cluster, nodegroup)
    print("Node Group Labels: " + json.dumps(labels))
    tainst = get_node_group_taints(client, cluster, nodegroup)
    print("Node Group Taints: "+ json.dumps(tainst))
    instance_types = get_node_group_instance_types(client, cluster, nodegroup)
    print("Node Group Instance Types: "+ json.dumps(instance_types))
    tags = get_node_group_tags(client, cluster, nodegroup)
    print("Node Group Tags: "+ json.dumps(tags))
    print("Node Group Status: "+get_node_group_status(client, cluster, nodegroup))

    return None



def get_eks_clusters(client):
  """
  Return all EKS Clusters
  """
  try:
    response = client.list_clusters()['clusters']
  except ClientError as e:
    print(e.response['Error']['Message'])

  return response

def get_eks_cluster_nodegroups(client, cluster):
  """
  Return all EKS Cluster NodeGroups
  """
  try:
    response = client.list_nodegroups(clusterName=cluster)['nodegroups']
  except ClientError as e:
    print(e.response['Error']['Message'])

  return response

def delete_eks_cluster_nodegroups(client, cluster):
  """
  Delete EKS Cluster NodeGroups
  """

  try:
    response = client.list_nodegroups(clusterName=cluster)['nodegroups']
  except ClientError as e:
    print(e.response['Error']['Message'])

  for node_group in response:
    delete_eks_cluster_nodegroup(client, cluster, node_group)

  return

def delete_eks_cluster_nodegroup(client, cluster, node_group):
  """
  Delete EKS Cluster NodeGroups
  """

  try:
    print("Deleting nodegroup="+node_group+", In cluster="+cluster)
    result = client.delete_nodegroup(clusterName=cluster, nodegroupName=node_group)
  except ClientError as e:
    print(e.response['Error']['Message'])

  return

def wait_node_group_deleted(client, cluster, node_group):
  """
  Wait for node group to be deleted
  """
  while (True):
    try:
      response = client.describe_nodegroup(clusterName=cluster,nodegroupName=node_group)['nodegroup']
    except ClientError as e:
      print("Node group deleted")
      break
    else:
      print("Node group still exists")
      time.sleep( 30 )

  return

# Delete all eks cluster for specific region
def delete_eks_clusters(client):
  """
  Delete all EKS Clusters
  """
  # get all clusters to delete
  clusters = client.list_clusters()['clusters']
  for c in clusters:
    delete_eks_cluster(client, c)

  return

def delete_eks_cluster(client, cluster):
    """
    Delete EKS Cluster
    """
    try:
      print("Deleting cluster="+cluster)
      result = client.delete_cluster(name=cluster)
    except ClientError as e:
      print(e.response['Error']['Message'])

    return


def wait_cluster_deleted(client, cluster):
    """
    Wait for cluster to be deleted
    """
    while (True):
      try:
        response = client.describe_cluster(name=cluster)['cluster']
      except ClientError as e:
        print("Cluster deleted")
        break
      else:
        print("Cluster still exists")
        time.sleep( 30 )

    return


# Custom JSON encoder to serialize datetime objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)

