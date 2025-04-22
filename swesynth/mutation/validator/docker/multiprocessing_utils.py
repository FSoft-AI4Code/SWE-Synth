import multiprocessing
import multiprocessing.synchronize
import os

__all__ = ["get_test_mapping_lock", "docker_max_semaphore"]


# Function to check if the lock is locked
def is_locked(lock):
    locked = not lock.acquire(block=False)  # Try to acquire the lock without blocking
    if not locked:
        lock.release()  # Release the lock if we successfully acquired it
    return locked


get_test_mapping_lock: multiprocessing.synchronize.Lock = multiprocessing.Lock()
num_semaphores: int = int(os.environ.get("SWESYNTH_DOCKER_MAX_SEMAPHORE", (os.cpu_count() or 4) // 2))
docker_max_semaphore: multiprocessing.synchronize.Semaphore = multiprocessing.Semaphore(num_semaphores)

num_mutator_semaphores: int = int(os.environ.get("SWESYNTH_MUTATOR_MAX_SEMAPHORE", 16))
concurrent_waiting_mutator_counter_semaphores: multiprocessing.synchronize.Semaphore = multiprocessing.Semaphore(num_mutator_semaphores)

manager = multiprocessing.Manager()
test_log_stream_dict = manager.dict()
