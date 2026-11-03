p = "build_paper_final.py"
s = open(p, encoding="utf-8").read()
anchor = '    d.nextlabel = "rw"\n'
assert anchor in s
new = (
    '    d.nextlabel = "prod"\n'
    '    d.table("Products that decide where work runs (only what the cited documentation pages state)",\n'
    '            ["Product", "Scope", "Heterogeneity handled", "Prediction / learning"],\n'
    '            [["Intel Thread Director {{intel_td}}", "hybrid client CPU", "P versus E cores; hardware tracks instruction mix per thread and informs the OS", "hardware classification"],\n'
    '             ["Windows QoS {{ms_qos}}", "OS scheduler", "QoS levels may restrict threads to a subset of processors", "heuristics and developer hints"],\n'
    '             ["Linux EAS {{linux_eas}}", "kernel", "asymmetric CPU capacity; energy model", "none; energy-model lookup"],\n'
    '             ["Kubernetes {{k8s}}", "cluster", "extended resources through filter and score plugins", "none stated"],\n'
    '             ["AWS Batch {{aws_batch}}", "cloud batch", "EC2, Fargate, ECS and EKS compute", "none stated"],\n'
    '             ["Slurm {{slurm}}", "HPC batch", "GPUs, MPS and MIG devices as generic resources", "none stated"],\n'
    '             ["Ray {{ray}}", "distributed Python", "declared CPU and GPU resources; placement groups", "none stated"],\n'
    '             ["StarPU {{starpu}}", "task runtime", "CPU and GPU tasks, data transfers", "performance models"]],\n'
    '            [0.9, 0.55, 1.3, 0.7], size=6.5)\n'
    '    d.para("The products split the work: operating-system features place threads, cluster products place containers or jobs against declared requests, and only workflow runtimes such as StarPU understand task graphs. No product page we read combines application-level DAG knowledge, learned per-resource runtime estimates and published decision-overhead measurements on a laptop-class hybrid CPU/GPU system.")\n'
)
s = s.replace(anchor, new + anchor, 1)
open(p, "w", encoding="utf-8").write(s)
print("ok")
