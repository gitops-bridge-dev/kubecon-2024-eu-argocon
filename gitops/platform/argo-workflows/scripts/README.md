virtualenv myenv
pip install
# aws config ...
# export KUBECONFIG="/tmp/karpenter"
# aws eks --region us-east-2 update-kubeconfig --name karpenter
python main.py karpenter karpenter us-east-2