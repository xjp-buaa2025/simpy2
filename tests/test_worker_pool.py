"""
工人池单元测试
测试WorkerPool的核心功能

测试内容:
- 工人获取与释放
- 休息逻辑（时间触发）
- 工人状态跟踪
- 统计数据计算
"""

import pytest
import simpy

from app.models.config_model import GlobalConfig
from app.models.enums import WorkerState
from app.core.worker_pool import WorkerPool


class TestWorkerPool:
    """工人池测试类"""
    
    def test_pool_initialization(self):
        """测试工人池初始化"""
        env = simpy.Environment()
        config = GlobalConfig(num_workers=4)
        pool = WorkerPool(env, config)
        
        assert len(pool.workers) == 4
        assert pool.get_available_count() == 4
        assert pool.get_working_count() == 0
        assert pool.get_resting_count() == 0
    
    def test_worker_request_single(self):
        """测试请求单个工人"""
        env = simpy.Environment()
        config = GlobalConfig(num_workers=2)
        pool = WorkerPool(env, config)
        
        def process():
            workers = yield from pool.request_workers(1)
            assert len(workers) == 1
            assert workers[0].state == WorkerState.WORKING
            assert pool.get_available_count() == 1
            
            pool.release_workers(workers)
            assert pool.get_available_count() == 2
        
        env.process(process())
        env.run()
    
    def test_worker_request_multiple(self):
        """测试请求多个工人"""
        env = simpy.Environment()
        config = GlobalConfig(num_workers=4)
        pool = WorkerPool(env, config)
        
        def process():
            workers = yield from pool.request_workers(3)
            assert len(workers) == 3
            assert pool.get_available_count() == 1
            assert pool.get_working_count() == 3
            
            pool.release_workers(workers)
            assert pool.get_available_count() == 4
        
        env.process(process())
        env.run()
    
    def test_worker_request_blocking(self):
        """测试请求超出可用数量时阻塞"""
        env = simpy.Environment()
        config = GlobalConfig(num_workers=2)
        pool = WorkerPool(env, config)
        
        request_times = []
        
        def requester1():
            workers = yield from pool.request_workers(2)
            request_times.append(('req1_got', env.now))
            yield env.timeout(10)
            pool.release_workers(workers)
            request_times.append(('req1_released', env.now))
        
        def requester2():
            yield env.timeout(1)  # Start slightly later
            request_times.append(('req2_start', env.now))
            workers = yield from pool.request_workers(1)
            request_times.append(('req2_got', env.now))
            pool.release_workers(workers)
        
        env.process(requester1())
        env.process(requester2())
        env.run()
        
        # req2 should wait until req1 releases
        assert request_times[0] == ('req1_got', 0)
        assert request_times[1] == ('req2_start', 1)
        assert request_times[2] == ('req1_released', 10)
        assert request_times[3][0] == 'req2_got'
        assert request_times[3][1] >= 10
    
    def test_rest_execution(self):
        """测试休息执行"""
        env = simpy.Environment()
        config = GlobalConfig(num_workers=2, rest_duration_time=5)
        pool = WorkerPool(env, config)
        
        def process():
            workers = yield from pool.request_workers(1)
            worker = workers[0]
            
            # Simulate work time
            worker.consecutive_work_time = 60
            
            # Execute rest
            assert worker.state == WorkerState.WORKING
            yield from pool.execute_rest(workers, 5, "test")
            
            # After rest
            assert worker.state == WorkerState.WORKING  # Still held by task
            assert worker.consecutive_work_time == 0    # Reset
            assert worker.total_rest_time == 5
            
            # Worker still not in pool
            assert pool.get_available_count() == 1
            
            pool.release_workers(workers)
            assert pool.get_available_count() == 2
        
        env.process(process())
        env.run()
    
    def test_time_rest_check(self):
        """测试时间触发休息检查"""
        env = simpy.Environment()
        config = GlobalConfig(num_workers=1, rest_time_threshold=50)
        pool = WorkerPool(env, config)
        
        def process():
            workers = yield from pool.request_workers(1)
            worker = workers[0]
            
            # Below threshold
            worker.consecutive_work_time = 40
            assert not pool.check_workers_need_rest(workers, 50)
            
            # At threshold
            worker.consecutive_work_time = 50
            assert pool.check_workers_need_rest(workers, 50)
            
            # Above threshold
            worker.consecutive_work_time = 60
            assert pool.check_workers_need_rest(workers, 50)
            
            pool.release_workers(workers)
        
        env.process(process())
        env.run()
    
    def test_work_time_tracking(self):
        """测试工作时间跟踪"""
        env = simpy.Environment()
        config = GlobalConfig(num_workers=1)
        pool = WorkerPool(env, config)
        
        def process():
            workers = yield from pool.request_workers(1)
            worker = workers[0]
            
            assert worker.total_work_time == 0
            assert worker.consecutive_work_time == 0
            
            pool.add_work_time_to_workers(workers, 30)
            assert worker.total_work_time == 30
            assert worker.consecutive_work_time == 30
            
            pool.add_work_time_to_workers(workers, 20)
            assert worker.total_work_time == 50
            assert worker.consecutive_work_time == 50
            
            # Simulate rest
            yield from pool.execute_rest(workers, 5, "test")
            assert worker.consecutive_work_time == 0
            assert worker.total_work_time == 50  # Total unchanged
            
            pool.release_workers(workers)
        
        env.process(process())
        env.run()
    
    def test_tasks_completed_tracking(self):
        """测试完成任务计数"""
        env = simpy.Environment()
        config = GlobalConfig(num_workers=2)
        pool = WorkerPool(env, config)
        
        def process():
            workers = yield from pool.request_workers(2)
            
            assert all(w.tasks_completed == 0 for w in workers)
            
            pool.increment_tasks_completed(workers)
            assert all(w.tasks_completed == 1 for w in workers)
            
            pool.increment_tasks_completed(workers)
            assert all(w.tasks_completed == 2 for w in workers)
            
            pool.release_workers(workers)
        
        env.process(process())
        env.run()
    
    def test_worker_stats(self):
        """测试工人统计数据"""
        env = simpy.Environment()
        config = GlobalConfig(num_workers=2)
        pool = WorkerPool(env, config)
        
        def process():
            workers = yield from pool.request_workers(1)
            pool.add_work_time_to_workers(workers, 100)
            pool.increment_tasks_completed(workers)
            yield from pool.execute_rest(workers, 10, "test")
            pool.release_workers(workers)
        
        env.process(process())
        env.run()
        
        stats = pool.get_worker_stats()
        assert len(stats) == 2
        
        # One worker was used
        used_worker = next(s for s in stats if s['total_work_time'] > 0)
        assert used_worker['total_work_time'] == 100
        assert used_worker['total_rest_time'] == 10
        assert used_worker['tasks_completed'] == 1
        assert used_worker['consecutive_work_time'] == 0  # Reset after rest
    
    def test_reset_all_workers(self):
        """测试重置所有工人"""
        env = simpy.Environment()
        config = GlobalConfig(num_workers=2)
        pool = WorkerPool(env, config)
        
        def process():
            workers = yield from pool.request_workers(2)
            for w in workers:
                w.total_work_time = 100
                w.tasks_completed = 5
            pool.release_workers(workers)
        
        env.process(process())
        env.run()
        
        pool.reset_all_workers()
        
        for worker in pool.workers.values():
            assert worker.total_work_time == 0
            assert worker.total_rest_time == 0
            assert worker.consecutive_work_time == 0
            assert worker.tasks_completed == 0
            assert worker.state == WorkerState.IDLE


class TestWorkerPoolConcurrency:
    """工人池并发测试"""
    
    def test_concurrent_requests(self):
        """测试并发请求"""
        env = simpy.Environment()
        config = GlobalConfig(num_workers=3)
        pool = WorkerPool(env, config)
        
        results = []
        
        def worker_task(task_id, num_workers, duration):
            workers = yield from pool.request_workers(num_workers)
            results.append((task_id, 'start', env.now, len(workers)))
            yield env.timeout(duration)
            pool.release_workers(workers)
            results.append((task_id, 'end', env.now))
        
        # Start multiple tasks
        env.process(worker_task('A', 2, 10))
        env.process(worker_task('B', 2, 5))
        env.process(worker_task('C', 1, 8))
        
        env.run()
        
        # All tasks should complete
        assert len([r for r in results if r[1] == 'end']) == 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
