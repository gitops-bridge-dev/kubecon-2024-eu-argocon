# kubecon-2024-eu-argocon
Using Argo Workflows for live migration from [CNCF Cluster AutoScaler](https://github.com/kubernetes/autoscaler) to [CNCF Karpenter](https://github.com/kubernetes-sigs/karpenter)



# Workflows

## Move workload from nodegroup to karpenter nodes (mode=karpenter)
1. Take as input the nodegroup name `team-a-12345`
1. Check if there is corresponding karpenter nodeclass and nodepoll with name of nodegroup
1. If no karpenter resource present then generate karnpenter nodeclass and nodepool, otherwise skip
    - `genkarpenter.py <nodegroup>`
    - Apply karpenter resources via apply or gitops (ie. ArgoCD) if generated file, otherwise skip
    - `kuebctl apply -f <file>`
1. Add taint `NoExecute:migratedto:karpenter` to nodegroup. This will evict all pods, and not allow pods into it unless can tolerate the tain.
1. Set Desired size and Minimum size to 0 (zero) for the nodegroup, then cluster-autoscaler will scale to zero the nodegroup

## Move worklaods from karpenter to nodegroups (mode=nodegroup)
1. Take as input the nodegroup name `team-a-12345`
1. Check if there is a karpenter nodepool with nodegroup name, otherwise stop
1. Update nodegroup taints and asg values
    - Remove taint "NoExecute:migratedfrom:karpenter" from nodegroup
    - Scale from zero, set Desired size and Minimum size original values use the annotations from karpenter pool
1. Wait for nodegroup status active, and desire of nodes running
1. Remove nodepool with nodegroup name to cordon, drain, and delete all pods

