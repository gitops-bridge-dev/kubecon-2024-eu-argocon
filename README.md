# kubecon-2024-eu-argocon
Using Argo Workflows for live migration from [CNCF Cluster AutoScaler](https://github.com/kubernetes/autoscaler) to [CNCF Karpenter](https://github.com/kubernetes-sigs/karpenter)

# Workflows

## Migrate workloads from nodegroup to karpenter (mode=karpenter)
1. Take as input the nodegroup name `team-a-12345`
1. Check if nodepool is present with nodegroup name if it is then stop
1. Generate karpenter nodeclass and nodepool, otherwise skip
1. Apply karpenter resources via apply or gitops (ie. ArgoCD)
1. Add taint `NoExecute:migratedto:karpenter` to nodegroup. This will evict all pods, and not allow pods into it unless can tolerate the taints.
1. Set Desired size and Minimum size to 0 (zero) for the nodegroup, then cluster-autoscaler will scale to zero the nodegroup. you can scale to zero cluster-autoscaler or uninstall

## Migrate workloads from karpenter to nodegroups (mode=nodegroup)
1. Take as input the nodegroup name `team-a-12345`
1. Check if there is a karpenter nodepool with nodegroup name, otherwise stop
1. Update nodegroup taints and asg values:
    - Remove taint `NoExecute:migratedfrom:karpenter` from nodegroup
    - Scale from zero, set Desired size and Minimum size original values use the annotations from karpenter pool
1. Wait for nodegroup status active, and desire of nodes running
1. Remove nodepool with nodegroup name to cordon, drain, and delete all pods
1. Remove nodeclass with nodegroup name


### Listing Node from Node Group
To get all the nodes created by a node group
```shell
watch kubectl get nodes -l eks.amazonaws.com/nodegroup
```
To get all the nodes created by a node group and used by `team-a`
```shell
watch kubectl get nodes -l eks.amazonaws.com/nodegroup,team=team-a
```
To get all the nodes created by a node group and used by `team-b`
```shell
watch kubectl get nodes -l eks.amazonaws.com/nodegroup,team=team-b
```
To get all the nodes created by a node group and used by `team-a` and `team-b`
```shell
watch kubectl get nodes -l eks.amazonaws.com/nodegroup,team=team-a -l eks.amazonaws.com/nodegroup,team=team-b
```
### Listing Node from Node Group
To get all the nodes created by a node group
```shell
watch kubectl get nodes -l karpenter.sh/nodepool
```
To get all the nodes created by a node group and used by `team-a`
```shell
watch kubectl get nodes -l karpenter.sh/nodepool,team=team-a
```
To get all the nodes created by a node group and used by `team-b`
```shell
watch kubectl get nodes -l karpenter.sh/nodepool,team=team-b
```
To get all the nodes created by a node group and used by `team-a` and `team-b`
```shell
watch kubectl get nodes -l karpenter.sh/nodepool,team=team-a -l karpenter.sh/nodepool,team=team-b
```




### TODOs:
- Race condition between auto-scaler and karpenter both want to handle the Pending pod, auto-scaler scales up the asg, and karpenter deploys a node.

**GitOps:**
- Rename appset relase name to `aws-cluster-autoscaler`

**Terraform:**
- rename appset cluster-addons to bootstrap
- argocd load balancer using classic and it doesn't work. This is because svc LoadBalancer is created before loadbalancer controller is running.
    To fix delete `svc` and recreate with argocd sync
    ```shell
    kubectl delete svc -n argocd argo-cd-argocd-server
    argocd app sync addon-in-cluster-argo-cd
    ```
    For now use port-forward
    ```shell
    kubectl port-forward -n argocd deployments/argo-cd-argocd-server 8080:8080
    ```




### Argo Workflows
- Write workflow template
- White argo events listener
- Design CRD
```yaml
apiVersion: migrator.karpenter.io/v1alpha1
Kind: KarpenterMigrator
metadata:
  name: team-a
spec:
  # karpenter or noderoup mode
  mode: karpenter
  # tags to find eks cluster
  clusterSelector:
    Blueprint: karpenter
  # tags to find node groups
  groupSelector:
    team: team-a
  # region to target
  region: us-east-2
```

