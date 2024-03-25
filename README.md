# Live Migration from Node-AutocScaler to Karpenter with Argo-Workflows
Using Argo Workflows for live migration from [CNCF Cluster AutoScaler](https://github.com/kubernetes/autoscaler) to [CNCF Karpenter](https://github.com/kubernetes-sigs/karpenter)


Slides: [Migrate-to-Karpenter-Argo-Workflows.pdf](./Migrate-to-Karpenter-Argo-Workflows.pdf)

Watch the video on youtube: https://youtu.be/rq57liGu0H4
[![Watch the video](https://img.youtube.com/vi/rq57liGu0H4/maxresdefault.jpg)](https://youtu.be/rq57liGu0H4)


# Run the Demo

Tools:
- terraform
- kubectl
- https://github.com/awslabs/eks-node-viewer

Terminal: Terraform
```shell
cd terraform/
terraform init
terraform apply
```
Review the output and run
```shell
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
echo "ArgoCD Username: admin"
echo "ArgoCD Password: $(kubectl get secrets argocd-initial-admin-secret -n argocd --template="{{index .data.password | base64decode}}")"
echo "ArgoCD URL: http://localhost:8080"
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
eks-node-viewer --kubeconfig /tmp/argocon-1 -node-selector eks.amazonaws.com/nodegroup  -disable-pricing
```

Terminal: List Karpenter nodes
New shell
```shell
export KUBECONFIG="/tmp/argocon-1"
eks-node-viewer -kubeconfig /tmp/argocon-1 -node-selector karpenter.sh/nodepool -disable-pricing
```

# Delete Demo
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

### Listing Node from Karpenter Node Pool
To get all the nodes created by a node group
```shell
watch kubectl get nodes -l karpenter.sh/nodepool
```
To get all the nodes created by a node group and used by `team-1`
```shell
watch kubectl get nodes -l karpenter.sh/nodepool,team=team-1
```

Smoke test for argo-workflows:
```shell
argo submit -n argo-workflows --serviceaccount argo-workflow https://raw.githubusercontent.com/argoproj/argo-workflows/main/examples/hello-world.yaml

argo list -n argo-workflows

argo logs @latest -n argo-workflows
```




### TODOs:

### GitOps:
- save karpenters in gitops repo for argocd to sync

### Argo Workflows
- save the original value for min,desire,max in nodegorup tags instead of karpenter
- multicluster support (handle multiple kubeconfigs)

### Terraform:
- rename appset cluster-addons to bootstrap

