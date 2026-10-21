"""On-demand labor retains individual fatigue without headcount queues."""
import simpy
import pytest
from app.core.worker_pool import WorkerPool
from app.models.config_model import GlobalConfig
from app.models.enums import WorkerState


def test_empty_pool_grows_atomically_and_reuses_only_idle_workers():
    pool = WorkerPool(simpy.Environment(), GlobalConfig(num_workers=1000))
    assert not pool.get_all_workers()
    first = pool.reserve_now(3)
    second = pool.reserve_now(2)
    assert len(pool.workers) == 5
    assert not set(w.id for w in first) & set(w.id for w in second)
    pool.release_workers(first)
    assert [w.id for w in pool.reserve_now(3)] == [w.id for w in first]
    assert len(pool.workers) == 5


def test_reuse_preserves_fatigue_and_balances_deterministically():
    pool = WorkerPool(simpy.Environment(), GlobalConfig())
    first, second = pool.reserve_now(2)
    first.add_work_time(50, 8)
    second.add_work_time(10, 5)
    pool.release_workers([first, second])
    assert pool.reserve_now(1) == [second]
    assert first.consecutive_work_time == 50 and first.fatigue_level > 0
    assert pool.check_workers_need_rest([first], 50)


def test_rest_holds_team_and_parallel_task_gets_immediate_supply():
    env = simpy.Environment()
    pool = WorkerPool(env, GlobalConfig())
    first = pool.reserve_now(1)
    first[0].add_work_time(60, 8)
    def resting():
        yield from pool.execute_rest(first, 5)
        assert first[0].state == WorkerState.WORKING
        assert first[0].consecutive_work_time == 0
        assert first[0].total_rest_time == 5
        pool.release_workers(first)
    def parallel():
        yield env.timeout(1)
        second = yield from pool.request_workers(1)
        assert env.now == 1 and second[0].id != first[0].id
        assert first[0].state == WorkerState.RESTING
        pool.release_workers(second)
    env.process(resting()); env.process(parallel()); env.run()
    assert pool.get_available_count() == 2


@pytest.mark.parametrize('count', [0, -1, 1.5])
def test_invalid_team_size(count):
    with pytest.raises(ValueError):
        WorkerPool(simpy.Environment(), GlobalConfig()).reserve_now(count)


def test_reset_starts_a_new_empty_roster():
    pool = WorkerPool(simpy.Environment(), GlobalConfig())
    pool.reserve_now(4)
    pool.reset_all_workers()
    assert not pool.workers
    assert pool.reserve_now(1)[0].id == 'Worker_01'
