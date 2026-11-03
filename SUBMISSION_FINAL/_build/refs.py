"""Reference database (IEEE style). Every entry was checked against the paper itself (PDF in the project's base-papers folder), the publisher/arXiv
page, Google Patents, or the vendor documentation page during this work; the note after each key says what was actually read.
Cite in text with {{key}}; numbering is by first appearance in each document.
"""
REFS = {
    # ---- literature (base papers) -----------------------------------------
    "lachesis": "J. Luo, Y. Zhou, X. Li, M. Yuan, J. Zeng, and J. Yao, “Learning to optimize DAG scheduling in heterogeneous environment,” in *Proc. IEEE Int. Conf. Mobile Data Manage. (MDM)*, 2022, doi: 10.1109/MDM55031.2022.00040 (arXiv:2103.06980).",  # full text read
    "dddqn": "C. Sun, T. Yang, and Y. Lei, “DDDQN-TS: A task scheduling and load balancing method based on optimized deep reinforcement learning in heterogeneous computing environment,” *Int. J. Intell. Syst.*, vol. 37, no. 11, pp. 9138–9172, 2022, doi: 10.1002/int.22983.",
    "wang22": "J. Wang, J. Hu, G. Min, W. Zhan, A. Y. Zomaya, and N. Georgalas, “Dependent task offloading for edge computing based on deep reinforcement learning,” *IEEE Trans. Comput.*, 2022, doi: 10.1109/TC.2021.3131040.",
    "rodriguez": "A. Rodríguez, A. Navarro, K. Nikov, J. Nunez-Yanez, R. Gran, D. Suárez Gracia, and R. Asenjo, “Lightweight asynchronous scheduling in heterogeneous reconfigurable systems,” *J. Syst. Archit.*, vol. 124, Art. no. 102398, 2022, doi: 10.1016/j.sysarc.2022.102398.",
    "song23": "Y. Song, C. Li, L. Tian, and H. Song, “A reinforcement learning based job scheduling algorithm for heterogeneous computing environment,” *Comput. Electr. Eng.*, vol. 107, Art. no. 108653, 2023, doi: 10.1016/j.compeleceng.2023.108653.",
    "gong23": "B. Gong and X. Jiang, “Dependent task-offloading strategy based on deep reinforcement learning in mobile edge computing,” *Wireless Commun. Mobile Comput.*, 2023, doi: 10.1155/2023/4665067.",
    "sata": "J. Liu, Y. Mi, X. Zhang, and X. Li, “Task graph offloading via deep reinforcement learning in mobile edge computing,” *Future Gener. Comput. Syst.*, vol. 158, pp. 545–555, 2024, doi: 10.1016/j.future.2024.04.034 (arXiv:2309.10569).",
    "cao24": "Z. Cao, X. Deng, S. Yue, P. Jiang, J. Ren, and J. Gui, “Dependent task offloading in edge computing using GNN and deep reinforcement learning,” *IEEE Internet Things J.*, vol. 11, no. 12, pp. 21632–21646, 2024, doi: 10.1109/JIOT.2024.3374969.",
    "nieto": "G. Nieto, I. de la Iglesia, U. Lopez-Novoa, and C. Perfecto, “Deep reinforcement learning techniques for dynamic task offloading in the 5G edge-cloud continuum,” *J. Cloud Comput.*, vol. 13, Art. no. 94, 2024, doi: 10.1186/s13677-024-00658-0.",
    "adprl": "X. Chen, J. Cao, Y. Sahni, S. Jiang, and Z. Liang, “Dynamic task offloading in edge computing based on dependency-aware reinforcement learning,” *IEEE Trans. Cloud Comput.*, vol. 12, no. 2, pp. 594–608, Apr.–Jun. 2024, doi: 10.1109/TCC.2024.3381646.",
    "metarl": "J. Liu, P. Xie, W. Li, B. Tang, and J. Liu, “Dynamic task offloading scheme for edge computing via meta-reinforcement learning,” *Comput. Mater. Contin.*, vol. 82, no. 2, 2025, doi: 10.32604/cmc.2024.058810.",
    "iov": "C. Liu, H. Wang, M. Zhao, J. Liu, X. Zhao, and P. Yuan, “Dependency-aware online task offloading based on deep reinforcement learning for IoV,” *J. Cloud Comput.*, vol. 13, Art. no. 136, 2024, doi: 10.1186/s13677-024-00701-0.",
    "tan25": "Q. Tan, W. Chen, and D. Liu, “Task scheduling for heterogeneous multi-core processors based on deep reinforcement learning,” *Int. J. Intell. Syst.*, vol. 2025, Art. no. 7562400, 2025, doi: 10.1155/int/7562400.",
    # ---- classical / related ----------------------------------------------
    "heft": "H. Topcuoglu, S. Hariri, and M.-Y. Wu, “Performance-effective and low-complexity task scheduling for heterogeneous computing,” *IEEE Trans. Parallel Distrib. Syst.*, vol. 13, no. 3, pp. 260–274, Mar. 2002.",
    "peft": "H. Arabnejad and J. G. Barbosa, “List scheduling algorithm for heterogeneous systems by an optimistic cost table,” *IEEE Trans. Parallel Distrib. Syst.*, vol. 25, no. 3, pp. 682–694, Mar. 2014, doi: 10.1109/TPDS.2013.57.",
    "lotaru": "J. Bader, F. Lehmann, L. Thamsen, U. Leser, and O. Kao, “Lotaru: Locally predicting workflow task runtimes for resource management on heterogeneous infrastructures,” *Future Gener. Comput. Syst.*, vol. 150, pp. 171–185, 2024, doi: 10.1016/j.future.2023.08.022.",
    "ilyushkin": "A. Ilyushkin and D. Epema, “The impact of task runtime estimate accuracy on scheduling workloads of workflows,” in *Proc. IEEE/ACM Int. Symp. Cluster, Cloud Grid Comput. (CCGrid)*, 2018, pp. 331–341, doi: 10.1109/CCGRID.2018.00048.",
    "starpu": "C. Augonnet, S. Thibault, R. Namyst, and P.-A. Wacrenier, “StarPU: A unified platform for task scheduling on heterogeneous multicore architectures,” *Concurrency Comput.: Pract. Exper.*, 2011 (journal version; see also Euro-Par 2009, LNCS 5704, pp. 863–874).",
    "decima": "H. Mao, M. Schwarzkopf, S. B. Venkatakrishnan, Z. Meng, and M. Alizadeh, “Learning scheduling algorithms for data processing clusters,” in *Proc. ACM SIGCOMM*, 2019 (arXiv:1810.01963).",
    "lureda": "T. Lu and S. Reda, “Agentic CPU-GPU scheduling for heterogeneous AI workloads,” arXiv:2607.22242, Jul. 2026.",
    "agentxpu": "X. Wei *et al.*, “Agent.xpu: Efficient scheduling of agentic LLM workloads on heterogeneous SoC,” arXiv:2506.24045, 2025.",
    "wfcommons": "T. Coleman, H. Casanova, L. Pottier, M. Kaushik, E. Deelman, and R. Ferreira da Silva, “WfCommons: A framework for enabling scientific workflow research and development,” *Future Gener. Comput. Syst.*, vol. 128, pp. 16–27, 2022, doi: 10.1016/j.future.2021.09.043.",
    "montage": "Caltech/IPAC, “Montage: An astronomical image mosaic engine,” software, https://github.com/Caltech-IPAC/Montage (commit ac0a1533, used in this work).",
    # ---- patents ----------------------------------------------------------
    "p_xilinx": "S. Nagpal, A. Karumannil, V. Jain, and A. K. Patil (Xilinx, Inc.), “Scheduling processing of machine learning tasks on heterogeneous compute circuits,” U.S. Patent 11,561,826 B1, Jan. 24, 2023 (filed Nov. 12, 2020).",
    "p_ibm1": "A. Vega *et al.* (International Business Machines Corp.), “Heterogeneous system on a chip scheduler with learning agent,” U.S. Patent 11,740,933 B2, Aug. 29, 2023.",
    "p_ibm2": "A. Amarnath *et al.* (International Business Machines Corp.), “Learning agent based application scheduling,” U.S. Patent 11,966,776 B2, Apr. 23, 2024.",
    "p_intel": "R. Barik, T. Shpeisman, B. T. Lewis, and R. Kaleem (Intel Corp.), “Adaptive scheduling for task assignment among heterogeneous processor cores,” U.S. Patent 10,186,007 B2, Jan. 22, 2019.",
    "p_samsung": "R. Kim and M.-S. Kim (Samsung Electronics Co., Ltd.), “Method and apparatus for performing task scheduling in terminal,” U.S. Patent 10,162,671 B2, Dec. 25, 2018.",
    "p_apple": "B. P. Englert, E. B. Harris, N. G. Crane, and B. J. Corey (Apple Inc.), “Scheduling heterogeneous execution on heterogeneous hardware,” U.S. Patent 11,775,811 B2, Oct. 3, 2023.",
    "p_google": "J. Wang and H. Huang (Google LLC), “Task scheduling for machine-learning workloads,” U.S. Patent 11,544,113 B2, Jan. 3, 2023.",
    # ---- statistics / market ----------------------------------------------
    "iea": "International Energy Agency, “Energy and AI,” Paris, France, Apr. 2025 (figures as reported in the summary and press coverage; the primary report page was not opened in this work).",
    "top500": "TOP500, “June 2025 list: highlights,” https://top500.org/lists/top500/2025/06/highs; accelerator counts and shares as analysed by The Next Platform, Jun. 10, 2025.",
    "iotanalytics": "IoT Analytics, “Number of connected IoT devices,” https://iot-analytics.com/number-connected-iot-devices/ (18.5 billion at end of 2024; 21.1 billion in 2025).",
    "cheng18": "Y. Cheng, Z. Chai, and A. Anwar, “Characterizing co-located datacenter workloads: An Alibaba case study,” arXiv:1808.02919, 2018.",
    # ---- products ---------------------------------------------------------
    "intel_td": "Intel, “What is Intel Thread Director?,” Intel support article 000097053, https://www.intel.com/content/www/us/en/support/articles/000097053/processors.html.",
    "linux_eas": "The Linux Kernel documentation, “Energy Aware Scheduling,” https://docs.kernel.org/scheduler/sched-energy.html.",
    "ms_qos": "Microsoft, “Quality of Service (Win32 apps),” Microsoft Learn, 2025, https://learn.microsoft.com/en-us/windows/win32/procthread/quality-of-service.",
    "aws_batch": "Amazon Web Services, “What is AWS Batch?,” AWS Batch User Guide, https://docs.aws.amazon.com/batch/latest/userguide/what-is-batch.html.",
    "k8s": "The Kubernetes Authors, “Kubernetes Scheduler (kube-scheduler),” https://kubernetes.io/docs/concepts/scheduling-eviction/kube-scheduler/.",
    "ray": "Anyscale/Ray Project, “Scheduling — Ray Core documentation,” https://docs.ray.io/en/latest/ray-core/scheduling/index.html.",
    "spark": "Apache Software Foundation, “Job scheduling — Spark documentation,” https://spark.apache.org/docs/latest/job-scheduling.html.",
    "slurm": "SchedMD, “Generic Resource (GRES) scheduling,” Slurm Workload Manager documentation, https://slurm.schedmd.com/gres.html.",
    "starpu_web": "Inria, “StarPU: A unified runtime system for heterogeneous multicore architectures,” https://starpu.gitlabpages.inria.fr/.",
    "pegasus": "Pegasus Team, “Pegasus Workflow Management System documentation, v5.1.3,” https://pegasus.isi.edu/documentation/.",
    "runai": "NVIDIA, “NVIDIA Run:ai documentation,” https://run-ai-docs.nvidia.com/ (landing page only was read).",
    "rpi5": "Raspberry Pi Ltd, “Raspberry Pi 5 product page,” https://www.raspberrypi.com/products/raspberry-pi-5/.",
    "copilot": "Microsoft/Qualcomm, Copilot+ PC requirement of an NPU of at least 40 TOPS, as stated in vendor documents (e.g., Qualcomm, “What TOPS means: Snapdragon X Series”).",
    "ccgrid27": "CCGrid 2027 Call for Papers, https://easychair.org/cfp/ccgrid27 (accessed Nov. 2026).",
}
