from botocore.exceptions import ClientError
import json
from datetime import datetime
import kubernetes.client
import kubernetes.config as config

# Configs can be set in Configuration class directly or using helper utility
config.load_kube_config()
api = kubernetes.client.CustomObjectsApi()


def generate_karpenter_node_class(nodegroup):
    """
    Generate the Karpenter NodeClass
    """
    cluster = nodegroup['clusterName']
    nodegroup_name = nodegroup['nodegroupName']
    subnets = nodegroup['subnets']
    subnets_map = [{"id": subnet} for subnet in subnets]
    karpenter_tags = {"karpenter.sh/discovery": cluster}
    node_group_tags = nodegroup['tags']
    tags = {**karpenter_tags, **node_group_tags}
    karpenter_ami_family = nodegroup['amiType']
    iam_role_arn = nodegroup['nodeRole']
    iam_role_name = iam_role_arn.split("/")[-1]
    ami_type = get_karpenter_ami_type(karpenter_ami_family)

    return {
        "apiVersion": "karpenter.k8s.aws/v1beta1",
        "kind": "EC2NodeClass",
        "metadata": {
            "name": nodegroup_name
        },
        "spec": {
            "amiFamily": ami_type,
            "role": iam_role_name,
            "subnetSelectorTerms": subnets_map,
            "securityGroupSelectorTerms": [
                {"tags": {"karpenter.sh/discovery": cluster}}
            ],
            "tags": tags
        }
    }


def generate_karpenter_node_pool(nodegroup):
    """
    Generate the Karpenter NodePool
    """
    nodegroup_name = nodegroup['nodegroupName']
    capacity_type = nodegroup['capacityType']
    # if capacity_type is SPOT set karpenter_capacity_type to "spot"
    # if capacity_type is ON_DEMAND set karpenter_capacity_type to "on-demand"
    karpenter_capacity_type = "on-demand" if capacity_type == "ON_DEMAND" else "spot"
    ami_family = nodegroup['amiType']
    # if ami_family string contains ARM_64 set karpenter_arch to "arm64" else "amd64"
    # examples of ami_family string: "AL2_x86_64", "AL2_ARM_64", "BOTTLEROCKET_x86_64", "BOTTLEROCKET_ARM_64"
    karpenter_arch = "arm64" if "ARM_64" in ami_family else "amd64"
    instance_types = nodegroup['instanceTypes']
    new_labels = {"karpenter.io/nodegroup": nodegroup_name}
    nodegroup_labels = nodegroup.get('labels') or []
    labels = {**nodegroup_labels, **new_labels}
    min = str(nodegroup['scalingConfig']['minSize'])
    max = str(nodegroup['scalingConfig']['maxSize'])
    desired_size = str(nodegroup['scalingConfig']['desiredSize'])
    instance_hypervisor = "nitro"
    return {
        "apiVersion": "karpenter.sh/v1beta1",
        "kind": "NodePool",
        "metadata": {
            "name": nodegroup_name,
            "annotations": {
                "migrate.karpenter.io/min": min,
                "migrate.karpenter.io/max": max,
                "migrate.karpenter.io/desired": desired_size
            }
        },
        "spec": {
            "template": {
                "metadata": {
                    "labels": labels
                },
                "spec": {
                    "nodeClassRef": {
                        "name": nodegroup_name
                    },
                    "requirements": [
                        {"key": "karpenter.sh/capacity-type", "operator": "In",
                         "values": [karpenter_capacity_type]},
                        {"key": "karpenter.io/arch", "operator": "In",
                         "values": [karpenter_arch]},
                        {"key": "karpenter.k8s.aws/instance-hypervisor",
                         "operator": "In", "values": [instance_hypervisor]},
                        {"key": "node.kubernetes.io/instance-type",
                         "operator": "In", "values": instance_types},
                    ]
                }
            },
            "limits": {
                "cpu": 1000
            },
            "disruption": {
                "consolidationPolicy": "WhenEmpty",
                "consolidateAfter": "30s"
            }
        }
    }


def apply_or_create_custom_object(object, kind):
    """
    Apply or Create Custom Object

    """
    # if kind is EC2NodeClass, plural is ec2nodeclasses
    # if kind is NodePool, plural is nodepools
    # else return None
    if kind not in ["EC2NodeClass", "NodePool"]:
        print("Kind %s not supported.", kind)
        return None
    plural = "ec2nodeclasses" if kind == "EC2NodeClass" else "nodepools"
    try:
        api_response = api.patch_cluster_custom_object(
            group=object['apiVersion'].split('/')[0],
            version=object['apiVersion'].split('/')[1],
            plural=plural,
            name=object['metadata']['name'],
            body=object,
            field_manager="karpenter-migrator"
        )
        print("%s %s updated." %
              (kind, object['kind']+object['metadata']['name']))
        return api_response
    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 404:
            # Custom object doesn't exist, create it
            api_response = api.create_cluster_custom_object(
                group=object['apiVersion'].split('/')[0],
                version=object['apiVersion'].split('/')[1],
                plural=plural,
                body=object,
                pretty='true',
                field_manager="karpenter-migrator"
            )
            print("%s %s created." %
                  (kind, object['kind']+object['metadata']['name']))
            return api_response
        else:
            print(
                "Exception when calling CustomObjectsApi->patch_cluster_custom_object: %s\n" % e)


def get_custom_object(object_name, kind):
    """
    Apply or Create Custom Object

    """
    # if kind is EC2NodeClass, plural is ec2nodeclasses
    # if kind is NodePool, plural is nodepools
    # else return None
    if kind not in ["ECs2NodeClass", "NodePool"]:
        print("Kind %s not supported.", kind)
        return None
    plural = "ec2nodeclasses" if kind == "EC2NodeClass" else "nodepools"
    # if plural is ec2nodeclasses then set group to 'karpenter.k8s.aws' other wise karpenter.sh
    group = "karpenter.k8s.aws" if plural == "ec2nodeclasses" else "karpenter.sh"
    try:
        api_response = api.get_cluster_custom_object(
            group=group,
            version='v1beta1',
            plural=plural,
            name=object_name,
        )
        return api_response
    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 404:
            # Custom object doesn't exist
            print("%s %s not found" % (kind, object_name))
            return None
        else:
            print(
                "Exception when calling CustomObjectsApi->patch_cluster_custom_object: %s\n" % e)


def delete_custom_object(object_name, kind):
    """
    Apply or Create Custom Object

    """
    # if kind is EC2NodeClass, plural is ec2nodeclasses
    # if kind is NodePool, plural is nodepools
    # else return None
    if kind not in ["EC2NodeClass", "NodePool"]:
        print("Kind %s not supported.", kind)
        return None
    plural = "ec2nodeclasses" if kind == "EC2NodeClass" else "nodepools"
    # if plural is ec2nodeclasses then set group to 'karpenter.k8s.aws' other wise karpenter.sh
    group = "karpenter.k8s.aws" if plural == "ec2nodeclasses" else "karpenter.sh"
    try:
        api_response = api.delete_cluster_custom_object(
            group=group,
            version='v1beta1',
            plural=plural,
            name=object_name,
        )
        print("Deleted %s %s " % (kind, object_name))
        return api_response
    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 404:
            # Custom object doesn't exist
            print("%s %s not found" % (kind, object_name))
            return None
        else:
            print(
                "Exception when calling CustomObjectsApi->patch_cluster_custom_object: %s\n" % e)


"""
EKS Managed Node Group Functions
"""


def get_node_group(client, cluster, nodegroup):
    try:
        response = client.describe_nodegroup(
            clusterName=cluster,
            nodegroupName=nodegroup
        )
        return response['nodegroup']
    except ClientError as e:
        print(e)
        return None


def get_karpenter_ami_type(ami_type):
    ami_type_map = {
        "AL2_x86_64": "AL2",
        "AL2_x86_64_GPU": "AL2",
        "AL2_ARM_64": "AL2",
        "CUSTOM": "Custom",
        "BOTTLEROCKET_ARM_64": "Bottlerocket",
        "BOTTLEROCKET_x86_64": "Bottlerocket",
        "BOTTLEROCKET_ARM_64_NVIDIA": "Bottlerocket",
        "BOTTLEROCKET_x86_64_NVIDIA": "Bottlerocket",
        "WINDOWS_CORE_2019_x86_64": "Windows2019",
        "WINDOWS_FULL_2019_x86_64": "Windows2019",
        "WINDOWS_CORE_2022_x86_64": "Windows2022",
        "WINDOWS_FULL_2022_x86_64": "Windows2022"
    }
    karpenter_ami_type = ami_type_map.get(ami_type, "Custom")
    return karpenter_ami_type


def update_nodegroup(client, **kargs):
    """
    Method to set the scaling config for the node group
    https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/eks/client/update_nodegroup_config.html
    """
    try:
        response = client.update_nodegroup_config(
            clusterName=kargs['clusterName'],
            nodegroupName=kargs['nodegroupName'],
            taints=kargs['taints'],
            scalingConfig=kargs['scalingConfig']
        )
        # wait for the node group to update
        waiter = client.get_waiter('nodegroup_active')
        waiter.wait(clusterName=kargs['clusterName'],
                    nodegroupName=kargs['nodegroupName'])
        return response
    except ClientError as e:
        print(e)
        return None


def set_scaling_config_for_nodegroup(client, cluster, nodegroup, scaling_config):
    """
    Method to set the scaling config for the node group
    """
    try:
        response = client.update_nodegroup_config(
            clusterName=cluster,
            nodegroupName=nodegroup,
            scalingConfig=scaling_config
        )
        # wait for the node group to update
        waiter = client.get_waiter('nodegroup_active')
        waiter.wait(clusterName=cluster, nodegroupName=nodegroup)
        print("Scaling config set for node group %s" % nodegroup)

        return response
    except ClientError as e:
        print(e)
        return None


def add_taint_to_nodegroup(client, cluster, nodegroup, taints):
    """
    Method to add the taint to the node group
    """
    try:
        response = client.update_nodegroup_config(
            clusterName=cluster,
            nodegroupName=nodegroup,
            taints=taints
        )
        # wait for the node group to update
        waiter = client.get_waiter('nodegroup_active')
        waiter.wait(clusterName=cluster, nodegroupName=nodegroup)
        print("Taint added to node group %s" % nodegroup)

        return response
    except ClientError as e:
        print(e)
        return None


def remove_taint_to_nodegroup(client, cluster, nodegroup, taints):
    """
    Method to remove the taint to the node group
    """
    try:
        response = client.update_nodegroup_config(
            clusterName=cluster,
            nodegroupName=nodegroup,
            taints=taints
        )
        # wait for the node group to update
        waiter = client.get_waiter('nodegroup_active')
        waiter.wait(clusterName=cluster, nodegroupName=nodegroup)
        print("Taint removed to node group %s" % nodegroup)

        return response
    except ClientError as e:
        print(e)
        return None


def get_eks_cluster_nodegroups(client, cluster):
    """
    Return all EKS Cluster NodeGroups
    """
    try:
        response = client.list_nodegroups(clusterName=cluster)['nodegroups']
    except ClientError as e:
        print(e.response['Error']['Message'])

    return response


"""
Utils Functions
"""
# Custom JSON encoder to serialize datetime objects


class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)