from caosched.phase0.benchmarks.workloads import WORKLOADS


def test_matmul_prepare_is_deterministic_given_seed():
    workload = WORKLOADS["matmul"]
    a1, b1 = workload.prepare(8, seed=42)
    a2, b2 = workload.prepare(8, seed=42)
    assert (a1 == a2).all()
    assert (b1 == b2).all()


def test_matmul_run_does_not_raise():
    workload = WORKLOADS["matmul"]
    inputs = workload.prepare(8, seed=0)
    workload.run(inputs)


def test_compression_prepare_is_deterministic_given_seed():
    workload = WORKLOADS["compression"]
    payload1 = workload.prepare(1000, seed=1)
    payload2 = workload.prepare(1000, seed=1)
    assert payload1 == payload2
    assert len(payload1) == 1000


def test_compression_run_does_not_raise():
    workload = WORKLOADS["compression"]
    payload = workload.prepare(1000, seed=0)
    workload.run(payload)


def test_image_filter_prepare_is_deterministic_given_seed():
    workload = WORKLOADS["image_filter"]
    img1 = workload.prepare(16, seed=1)
    img2 = workload.prepare(16, seed=1)
    assert img1.tobytes() == img2.tobytes()


def test_image_filter_run_does_not_raise():
    workload = WORKLOADS["image_filter"]
    img = workload.prepare(16, seed=0)
    workload.run(img)
