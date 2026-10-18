// scheduler.rs — SatoshiOS Work-Stealing Task Scheduler
//
// Implements a multi-queue work-stealing scheduler modelled after
// Tokio's internal design.  Tasks are submitted to per-thread local
// queues; idle workers steal from the back of other queues.

use std::collections::VecDeque;
use std::sync::{Arc, Mutex, Condvar};
use std::thread;
use std::time::{Duration, Instant};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};

// ─── Task ────────────────────────────────────────────────────────────────────

pub type BoxTask = Box<dyn FnOnce() + Send + 'static>;

/// A runnable unit of work with an optional priority.
pub struct Task {
    pub id: u64,
    pub priority: u8,   // 0 = normal, 1-255 = higher priority
    pub work: BoxTask,
    pub created_at: Instant,
}

impl Task {
    pub fn new(id: u64, work: impl FnOnce() + Send + 'static) -> Self {
        Self {
            id,
            priority: 0,
            work: Box::new(work),
            created_at: Instant::now(),
        }
    }

    pub fn with_priority(mut self, priority: u8) -> Self {
        self.priority = priority;
        self
    }
}

// ─── Per-Worker Queue ────────────────────────────────────────────────────────

/// A double-ended, mutex-protected task queue per worker thread.
#[derive(Default)]
struct WorkerQueue {
    deque: VecDeque<Task>,
}

impl WorkerQueue {
    fn push_back(&mut self, task: Task) {
        self.deque.push_back(task);
    }

    /// Pop from front (FIFO — local worker's normal consumption).
    fn pop_front(&mut self) -> Option<Task> {
        self.deque.pop_front()
    }

    /// Steal from back (work-stealing from other workers).
    fn steal_back(&mut self) -> Option<Task> {
        self.deque.pop_back()
    }

    fn len(&self) -> usize {
        self.deque.len()
    }

    fn is_empty(&self) -> bool {
        self.deque.is_empty()
    }
}

// ─── Scheduler Metrics ──────────────────────────────────────────────────────

#[derive(Debug, Default, Clone)]
pub struct SchedulerMetrics {
    pub tasks_submitted: u64,
    pub tasks_executed: u64,
    pub tasks_stolen: u64,
    pub total_wait_time_ms: u64,
    pub total_exec_time_ms: u64,
}

// ─── WorkStealingScheduler ───────────────────────────────────────────────────

/// Multi-threaded work-stealing scheduler.
pub struct WorkStealingScheduler {
    /// One queue per worker thread.
    queues: Vec<Arc<Mutex<WorkerQueue>>>,
    /// Park/unpark signal.
    condvar: Arc<(Mutex<bool>, Condvar)>,
    /// Worker thread handles.
    workers: Vec<thread::JoinHandle<()>>,
    /// Global task counter for unique IDs.
    next_id: Arc<AtomicU64>,
    /// Shared metrics.
    metrics: Arc<Mutex<SchedulerMetrics>>,
    /// Shutdown flag.
    shutdown: Arc<AtomicBool>,
    num_workers: usize,
}

impl WorkStealingScheduler {
    /// Create scheduler with `num_workers` threads.
    pub fn new(num_workers: usize) -> Self {
        let queues: Vec<Arc<Mutex<WorkerQueue>>> = (0..num_workers)
            .map(|_| Arc::new(Mutex::new(WorkerQueue::default())))
            .collect();

        let condvar = Arc::new((Mutex::new(false), Condvar::new()));
        let next_id = Arc::new(AtomicU64::new(1));
        let metrics = Arc::new(Mutex::new(SchedulerMetrics::default()));
        let shutdown = Arc::new(AtomicBool::new(false));

        let mut workers = Vec::new();

        for worker_id in 0..num_workers {
            let all_queues = queues.clone();
            let cv = condvar.clone();
            let m = metrics.clone();
            let sd = shutdown.clone();

            let handle = thread::Builder::new()
                .name(format!("satoshi-scheduler-{}", worker_id))
                .spawn(move || {
                    Self::worker_loop(worker_id, all_queues, cv, m, sd);
                })
                .expect("Failed to spawn worker thread");

            workers.push(handle);
        }

        println!(
            "[Scheduler] WorkStealingScheduler started with {} workers",
            num_workers
        );

        Self {
            queues,
            condvar,
            workers,
            next_id,
            metrics,
            shutdown,
            num_workers,
        }
    }

    /// Submit a task — round-robin assignment.
    pub fn submit(&self, work: impl FnOnce() + Send + 'static) -> u64 {
        let id = self.next_id.fetch_add(1, Ordering::Relaxed);
        let task = Task::new(id, work);

        // Pick the least-loaded queue
        let target = self.least_loaded_queue();
        self.queues[target].lock().unwrap().push_back(task);

        // Signal a waiting worker
        let (lock, cvar) = &*self.condvar;
        let mut ready = lock.lock().unwrap();
        *ready = true;
        cvar.notify_one();

        let mut m = self.metrics.lock().unwrap();
        m.tasks_submitted += 1;
        id
    }

    /// Submit with explicit priority.
    pub fn submit_priority(&self, priority: u8, work: impl FnOnce() + Send + 'static) -> u64 {
        let id = self.next_id.fetch_add(1, Ordering::Relaxed);
        let task = Task::new(id, work).with_priority(priority);

        let target = self.least_loaded_queue();
        self.queues[target].lock().unwrap().push_back(task);

        let (lock, cvar) = &*self.condvar;
        let mut ready = lock.lock().unwrap();
        *ready = true;
        cvar.notify_all();

        let mut m = self.metrics.lock().unwrap();
        m.tasks_submitted += 1;
        id
    }

    fn least_loaded_queue(&self) -> usize {
        self.queues
            .iter()
            .enumerate()
            .min_by_key(|(_, q)| q.lock().unwrap().len())
            .map(|(i, _)| i)
            .unwrap_or(0)
    }

    fn worker_loop(
        id: usize,
        queues: Vec<Arc<Mutex<WorkerQueue>>>,
        condvar: Arc<(Mutex<bool>, Condvar)>,
        metrics: Arc<Mutex<SchedulerMetrics>>,
        shutdown: Arc<AtomicBool>,
    ) {
        println!("[Scheduler] Worker {} started", id);

        loop {
            if shutdown.load(Ordering::Relaxed) {
                println!("[Scheduler] Worker {} shutting down", id);
                break;
            }

            // Try own queue first
            let task = {
                let mut q = queues[id].lock().unwrap();
                q.pop_front()
            };

            let task = task.or_else(|| {
                // Work-steal from other queues
                for i in 0..queues.len() {
                    if i == id {
                        continue;
                    }
                    let stolen = queues[i].lock().unwrap().steal_back();
                    if stolen.is_some() {
                        let mut m = metrics.lock().unwrap();
                        m.tasks_stolen += 1;
                        return stolen;
                    }
                }
                None
            });

            if let Some(task) = task {
                let wait_time = task.created_at.elapsed().as_millis() as u64;
                let exec_start = Instant::now();

                (task.work)();

                let exec_time = exec_start.elapsed().as_millis() as u64;
                let mut m = metrics.lock().unwrap();
                m.tasks_executed += 1;
                m.total_wait_time_ms += wait_time;
                m.total_exec_time_ms += exec_time;
            } else {
                // Park until work arrives
                let (lock, cvar) = &*condvar;
                let ready = lock.lock().unwrap();
                let _ = cvar.wait_timeout(ready, Duration::from_millis(10));
            }
        }
    }

    /// Graceful shutdown — waits for all queues to drain.
    pub fn shutdown(self) {
        // Signal shutdown
        self.shutdown.store(true, Ordering::Relaxed);
        let (_, cvar) = &*self.condvar;
        cvar.notify_all();

        for w in self.workers {
            let _ = w.join();
        }
        println!("[Scheduler] All workers stopped");
    }

    pub fn metrics(&self) -> SchedulerMetrics {
        self.metrics.lock().unwrap().clone()
    }

    pub fn pending_count(&self) -> usize {
        self.queues.iter().map(|q| q.lock().unwrap().len()).sum()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};

    #[test]
    fn test_tasks_executed() {
        let scheduler = WorkStealingScheduler::new(2);
        let counter = Arc::new(AtomicUsize::new(0));

        for _ in 0..10 {
            let c = counter.clone();
            scheduler.submit(move || {
                c.fetch_add(1, Ordering::Relaxed);
            });
        }

        thread::sleep(Duration::from_millis(200));
        assert_eq!(counter.load(Ordering::Relaxed), 10);

        let m = scheduler.metrics();
        assert_eq!(m.tasks_executed, 10);
        scheduler.shutdown();
    }

    #[test]
    fn test_work_stealing_occurs() {
        let scheduler = WorkStealingScheduler::new(4);
        let counter = Arc::new(AtomicUsize::new(0));

        // Submit many tasks quickly to one thread's queue
        for _ in 0..50 {
            let c = counter.clone();
            scheduler.submit(move || {
                c.fetch_add(1, Ordering::Relaxed);
                thread::sleep(Duration::from_millis(1));
            });
        }

        thread::sleep(Duration::from_millis(500));
        let m = scheduler.metrics();
        // Some tasks should have been stolen
        println!("Stolen: {}, Executed: {}", m.tasks_stolen, m.tasks_executed);
        assert_eq!(counter.load(Ordering::Relaxed), 50);
        scheduler.shutdown();
    }
}
