# kubecon-2024-eu-argocon
Using Argo Workflows for live migration from [CNCF Cluster AutoScaler](https://github.com/kubernetes/autoscaler) to [CNCF Karpenter](https://github.com/kubernetes-sigs/karpenter)

# Running the Demo

Tools:
- terraform
- kubectl
- https://github.com/awslabs/eks-node-viewer

Terminal: Terraform
```shell
cd terraform/
terraform apply
export KUBECONFIG="/tmp/argocon-1"
aws eks --region us-east-2 update-kubeconfig --name argocon-1
kubectl get pods -A
```

Terminal: Any new terminal run this command to setup `kubectl` config
```
export KUBECONFIG="/tmp/argocon-1"
```

Terminal: Port forward argocd
```shell
export KUBECONFIG="/tmp/argocon-1"
echo "http://locahost:8080"
kubectl port-forward -n argocd svc/argo-cd-argocd-server 8080:80
```

Terminal: Port forward argo-workflows
New shell
```shell
export KUBECONFIG="/tmp/argocon-1"
echo "http://localhost:8081"
kubectl port-forward -n argo-workflows svc/argo-workflows-server 8081:2746
```

Terminal: List Node Group nodes
New shell
```shell
export KUBECONFIG="/tmp/argocon-1"
eks-node-viewer --kubeconfig /tmp/argocon-1 --nodeSelector eks.amazonaws.com/nodegroup  -disable-pricing
```

Terminal: List Karpenter nodes
New shell
```shell
export KUBECONFIG="/tmp/argocon-1"
eks-node-viewer -kubeconfig /tmp/argocon-1 -nodeSelector karpenter.sh/nodepool -disable-pricing
```

# Deleting Demo
```shell
cd terraform
./destroy.sh
```

# Workflows

## Migrate workloads from nodegroup to karpenter (mode=karpenter)
1. Take as input the nodegroup name `team-a-12345`
1. Check if nodepool is present with nodegroup name if it is then stop
1. Generate karpenter nodeclass and nodepool, otherwise skip
1. Apply karpenter resources via apply or gitops (ie. ArgoCD)
1. Scale down nodegroup

## Migrate workloads from karpenter to nodegroups (mode=nodegroup)
1. Take as input the nodegroup name `team-a-12345`
1. Check if there is a karpenter nodepool with nodegroup name, otherwise stop
1. Scale up nodgroup
1. Remove nodepool with nodegroup name to cordon, drain, and delete all pods
1. Remove nodeclass with nodegroup name


### Listing Node from Node Group
To get all the nodes created by a node group
```shell
watch kubectl get nodes -l eks.amazonaws.com/nodegroup
```
To get all the nodes created by a node group and used by `team-1`
```shell
watch kubectl get nodes -l eks.amazonaws.com/nodegroup,team=team-1
```
Use eks-node-viewer for nodegroups
```shell
eks-node-viewer --kubeconfig /tmp/argocon-1 --nodeSelector eks.amazonaws.com/nodegroup  -disable-pricing
```
### Listing Node from Karpenter Node Pool
To get all the nodes created by a node group
```shell
watch kubectl get nodes -l karpenter.sh/nodepool
```
To get all the nodes created by a node group and used by `team-1`
```shell
watch kubectl get nodes -l karpenter.sh/nodepool,team=team-1
```
Use eks-node-viewer for nodegroups
```shell
eks-node-viewer -kubeconfig /tmp/argocon-1 -nodeSelector migrate.karpenter.io/nodegroup -disable-pricing
```

ArgoCD Port Forward:
```shell
kubectl port-forward -n argocd deployments/argo-cd-argocd-server 8080:8080
```

Use the Argo Workflow UI, use port-forward, and open url http://localhost:8081
```shell
kubectl port-forward -n argo-workflows svc/argo-workflows-server 8081:2746
```


Get authentication token using argo cli
```shell
argo auth token
```
Smoke test for argo-workflows:
```shell
argo submit -n argo-workflows --serviceaccount argo-workflow https://raw.githubusercontent.com/argoproj/argo-workflows/main/examples/hello-world.yaml

argo list -n argo-workflows

argo logs @latest -n argo-workflows
```




### TODOs:

### GitOps:
- Rename appset relase name to `aws-cluster-autoscaler`

### Argo Workflows
- multicluster support (need to disable autoscaler, and find clusters by tag and region)
- save the original value for min,desire,max in nodegorup tags instead of karpenter

### Terraform:
- rename appset cluster-addons to bootstrap
- disable argocd dex and notifications
    dex:
      enabled: false
    notifications:
      enabled: false
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
- There is a problem with IAM policy with termination node handler in terraform


