# kubecon-2024-eu-argocon
Using Argo Workflows for live migration from [CNCF Cluster AutoScaler](https://github.com/kubernetes/autoscaler) to [CNCF Karpenter](https://github.com/kubernetes-sigs/karpenter)



## Workflows
### Move workload from nodegroup to karpenter nodes
1. Take as input the nodegroup name `team-a-12345`
1. Check if there is corresponding karpenter nodeclass and nodepoll with name of nodegroup
1. If no karpenter resource present then generate karnpenter nodeclass and nodepool, otherwise skip
  - `genkarpenter.py <nodegroup>`
1. Apply karpenter resources via apply or gitops (ie. ArgoCD) if generated file, otherwise skip
  - `kuebctl apply -f <file>`
1. Cordon all nodes from nodegroup to avoid pods evicted landing on another node from the nodegroup
  - `kubectl cordon -l eks.amazonaws.com/nodegroup=team-a-12345`
1. Add taint "NoSchedule:migratebackfrom:karpenter" to nodegroup (no need to cordon this has same effect)
1. Drain nodegroup
1. Scale to zero as optional, set desire and min to 0 (zero) for the nodegroup




1. Drain all nodes from nodegroup this starts eviction off the pods
1. New pods will go Pending, and karpenter wo
1. Wait for all nodes to be drained
