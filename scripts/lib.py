from botocore.exceptions import ClientError
import json
import time
from datetime import datetime
import kubernetes.client
import kubernetes.config as config


# Configs can be set in Configuration class directly or using helper utility
config.load_kube_config()
api = kubernetes.client.CustomObjectsApi()


def generate_karpenter_node_class(eks, ec2, nodegroup):
    """
    Generate the Karpenter NodeClass
    """
    cluster = nodegroup['clusterName']
    nodegroup_name = nodegroup['nodegroupName']
    security_groups = get_nodegroup_sg(eks, ec2, nodegroup)
    security_groups_map = [{"id": security_group}
                           for security_group in security_groups]
    subnets = nodegroup['subnets']
    subnets_map = [{"id": subnet} for subnet in subnets]
    karpenter_tags = {
        "karpenter.sh/discovery": cluster,
        "migrate.karpenter.io/nodegroup": nodegroup_name
    }
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
            "securityGroupSelectorTerms": security_groups_map,
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
    new_labels = {"migrate.karpenter.io/nodegroup": nodegroup_name}
    nodegroup_labels = nodegroup.get('labels') or []
    labels = {**nodegroup_labels, **new_labels}
    taints = translate_nodegroup_taints(nodegroup['taints'])
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
                    ],
                    "taints": taints
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


def translate_nodegroup_taints(taints):
    """
    taints is an array with the following structure for each item dict
    [
        {
            'key': 'string',
            'value': 'string',
            'effect': 'NO_SCHEDULE'|'NO_EXECUTE'|'PREFER_NO_SCHEDULE'
        }
    ]
    return the taints with the effect changed to match the following return
    [
        {
            'key': 'string',
            'value': 'string',
            'effect': 'NoSchedule'|'NoExecute'|'PreferNoSchedule'
        }
    ]
    """
    taints_translated = []
    for taint in taints:
        if taint['effect'] == 'NO_SCHEDULE':
            taint['effect'] = 'NoSchedule'
        elif taint['effect'] == 'NO_EXECUTE':
            taint['effect'] = 'NoExecute'
        elif taint['effect'] == 'PREFER_NO_SCHEDULE':
            taint['effect'] = 'PreferNoSchedule'
        taints_translated.append(taint)
    return taints_translated


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

# scale deployment cluster-autoscaler-aws-cluster-autoscaler in namespace kube-system to 2 replicas


def scale_deployment(deployment_name, namespace, replicas):
    apps_api = kubernetes.client.AppsV1Api()
    try:
        api_response = apps_api.patch_namespaced_deployment_scale(
            name=deployment_name,
            namespace=namespace,
            body={
                "spec": {
                    "replicas": replicas
                }
            }
        )
    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 404:
            # Custom object doesn't exist
            print("deployment %s in %s not found" %
                  (deployment_name, namespace))
            return None
        else:
            print(
                "Exception when calling CustomObjectsApi->patch_cluster_custom_object: %s\n" % e)
    return None


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


def get_nodegroup_sg(eks, ec2, nodegroup):
    """
    Return Security Group for node group
    """
    template_name = nodegroup['launchTemplate']['name']
    template_version = nodegroup['launchTemplate']['version']
    try:
        template = ec2.describe_launch_template_versions(
            LaunchTemplateName=template_name, Versions=[template_version])
        # check if template[0]['LaunchTemplateData']['NetworkInterfaces'][0]['Groups']
        # if template[0]['LaunchTemplateData']['NetworkInterfaces'][0]['Groups'] is not None, return it
        # else check template[0]['LaunchTemplateData']['SecurityGroupIds']]
        # if template[0]['LaunchTemplateData']['SecurityGroupIds'] is not None, return it
        launch_template = template.get('LaunchTemplateVersions')
        if launch_template:
            launch_data = launch_template[0].get('LaunchTemplateData')
        if launch_data:
            sg_top = launch_data.get('SecurityGroupIds')
            network_interfaces = launch_data.get('NetworkInterfaces')
            if network_interfaces:
                sg_net = network_interfaces[0].get('Groups')
                if sg_net is not None:
                    return sg_net
                if sg_top is not None:
                    return sg_top

        # return eks security group
        cluster = eks.describe_cluster(name=nodegroup['clusterName'])
        return [cluster['cluster']['resourcesVpcConfig']['clusterSecurityGroupId']]

    except ClientError as e:
        print(e.response['Error']['Message'])

    return None


"""
Utils Functions
"""
# Custom JSON encoder to serialize datetime objects


class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)
