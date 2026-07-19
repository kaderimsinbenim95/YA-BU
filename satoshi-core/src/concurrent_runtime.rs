// concurrent_runtime.rs — SatoshiOS Async/Concurrent Runtime
//
// Implements an async task runtime backed by a Tokio executor.
// Provides a high-level API for spawning tasks, joining results,
// and running concurrent blocks — the async primitives used by
// SatoshiLang's `async task` and `concurrent { }` constructs.

use std::future::Future;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tokio::runtime::{Builder, Runtime};
use tokio::task::JoinHandle;
use tokio::sync::{mpsc, Semaphore};
use tokio::time::timeout;

/// Result type for runtime operations.
pub type RuntimeResult<T> = Result<T, RuntimeError>;

#[derive(Debug)]
pub enum RuntimeError {
    SpawnError(String),
    Timeout(Duration),
    Panic(String),
    ChannelClosed,
    SemaphoreAcquireError,
}

impl std::fmt::Display for RuntimeError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            RuntimeError::SpawnError(msg) => write!(f, "SpawnError: {}", msg),
            RuntimeError::Timeout(d) => write!(f, "Timeout after {:?}", d),
            RuntimeError::Panic(msg) => write!(f, "Task panicked: {}", msg),
            RuntimeError::ChannelClosed => write!(f, "Channel closed"),
            RuntimeError::SemaphoreAcquireError => write!(f, "Semaphore acquire failed"),
        }
    }
}

// ─── Runtime Metrics ────────────────────────────────────────────────────────

#[derive(Debug, Default, Clone)]
pub struct RuntimeMetrics {
    pub tasks_spawned: u64,
    pub tasks_completed: u64,
    pub tasks_timed_out: u64,
    pub tasks_panicked: u64,
    pub total_task_time_ms: u64,
}

// ─── ConcurrentRuntime ──────────────────────────────────────────────────────

/// Manages a Tokio multi-thread runtime with metrics tracking.
pub struct ConcurrentRuntime {
    runtime: Runtime,
    metrics: Arc<Mutex<RuntimeMetrics>>,
    /// Maximum concurrent tasks.
    max_concurrency: usize,
    task_timeout: Duration,
}

impl ConcurrentRuntime {
    /// Create a new runtime.
    ///
    /// * `worker_threads` — number of OS threads (0 = cpu count)
    /// * `max_concurrency` — semaphore limit on simultaneous tasks
    /// * `task_timeout_secs` — per-task timeout
    pub fn new(worker_threads: usize, max_concurrency: usize, task_timeout_secs: u64) -> Self {
        let threads = if worker_threads == 0 {
            num_cpus::get()
        } else {
            worker_threads
        };

        let runtime = Builder::new_multi_thread()
            .worker_threads(threads)
            .thread_name("satoshi-worker")
            .enable_all()
            .build()
            .expect("Failed to build Tokio runtime");

        println!(
            "[Runtime] ConcurrentRuntime started — {} workers, max_concurrency={}, timeout={}s",
            threads, max_concurrency, task_timeout_secs
        );

        Self {
            runtime,
            metrics: Arc::new(Mutex::new(RuntimeMetrics::default())),
            max_concurrency,
            task_timeout: Duration::from_secs(task_timeout_secs),
        }
    }

    /// Spawn a future and return its JoinHandle.
    pub fn spawn<F, T>(&self, future: F) -> JoinHandle<T>
    where
        F: Future<Output = T> + Send + 'static,
        T: Send + 'static,
    {
        let metrics = self.metrics.clone();
        {
            let mut m = metrics.lock().unwrap();
            m.tasks_spawned += 1;
        }

        let start = Instant::now();
        let m2 = metrics.clone();

        self.runtime.spawn(async move {
            let result = future.await;
            let elapsed = start.elapsed().as_millis() as u64;
            let mut m = m2.lock().unwrap();
            m.tasks_completed += 1;
            m.total_task_time_ms += elapsed;
            result
        })
    }

    /// Run a future to completion on the current thread (blocking).
    pub fn block_on<F: Future>(&self, future: F) -> F::Output {
        self.runtime.block_on(future)
    }

    /// Run multiple futures concurrently, bounded by `max_concurrency`.
    /// Returns all results in the original order.
    pub fn run_concurrent<F, T>(&self, futures: Vec<F>) -> Vec<RuntimeResult<T>>
    where
        F: Future<Output = T> + Send + 'static,
        T: Send + 'static,
    {
        let semaphore = Arc::new(Semaphore::new(self.max_concurrency));
        let task_timeout = self.task_timeout;
        let metrics = self.metrics.clone();

        self.runtime.block_on(async move {
            let handles: Vec<JoinHandle<RuntimeResult<T>>> = futures
                .into_iter()
                .map(|fut| {
                    let sem = semaphore.clone();
                    let m = metrics.clone();
                    {
                        let mut lk = m.lock().unwrap();
                        lk.tasks_spawned += 1;
                    }
                    let start = Instant::now();
                    let m2 = m.clone();

                    tokio::spawn(async move {
                        let _permit = sem.acquire().await.map_err(|_| {
                            RuntimeError::SemaphoreAcquireError
                        })?;

                        match timeout(task_timeout, fut).await {
                            Ok(result) => {
                                let elapsed = start.elapsed().as_millis() as u64;
                                let mut lk = m2.lock().unwrap();
                                lk.tasks_completed += 1;
                                lk.total_task_time_ms += elapsed;
                                Ok(result)
                            }
                            Err(_) => {
                                let mut lk = m2.lock().unwrap();
                                lk.tasks_timed_out += 1;
                                Err(RuntimeError::Timeout(task_timeout))
                            }
                        }
                    })
                })
                .collect();

            let mut results = Vec::with_capacity(handles.len());
            for handle in handles {
                match handle.await {
                    Ok(r) => results.push(r),
                    Err(e) => {
                        let mut lk = metrics.lock().unwrap();
                        lk.tasks_panicked += 1;
                        results.push(Err(RuntimeError::Panic(e.to_string())));
                    }
                }
            }
            results
        })
    }

    /// Current runtime metrics snapshot.
    pub fn metrics(&self) -> RuntimeMetrics {
        self.metrics.lock().unwrap().clone()
    }
}

// ─── Message-Passing Channel Helpers ────────────────────────────────────────

/// A typed async message channel pair.
pub struct Channel<T> {
    pub sender: mpsc::Sender<T>,
    pub receiver: mpsc::Receiver<T>,
}

impl<T> Channel<T> {
    pub fn new(capacity: usize) -> Self {
        let (sender, receiver) = mpsc::channel(capacity);
        Self { sender, receiver }
    }
}

// ─── Parallel Task Utilities ─────────────────────────────────────────────────

/// Execute an async block on the runtime and collect the result.
/// Convenience wrapper used by SatoshiLang `concurrent { ... }` blocks.
pub async fn concurrent_block<F, T>(futures: Vec<F>) -> Vec<T>
where
    F: Future<Output = T> + Send + 'static,
    T: Send + 'static,
{
    let handles: Vec<JoinHandle<T>> = futures
        .into_iter()
        .map(tokio::spawn)
        .collect();

    let mut results = Vec::with_capacity(handles.len());
    for h in handles {
        results.push(h.await.expect("concurrent_block: task panicked"));
    }
    results
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_runtime() -> ConcurrentRuntime {
        ConcurrentRuntime::new(2, 4, 5)
    }

    #[test]
    fn test_block_on_simple() {
        let rt = make_runtime();
        let result = rt.block_on(async { 42u32 });
        assert_eq!(result, 42);
    }

    #[test]
    fn test_run_concurrent_all_succeed() {
        let rt = make_runtime();
        let futures: Vec<_> = (0..8u32)
            .map(|i| async move { i * 2 })
            .collect();

        let results = rt.run_concurrent(futures);
        assert_eq!(results.len(), 8);
        for r in &results {
            assert!(r.is_ok());
        }
    }

    #[test]
    fn test_metrics_tracked() {
        let rt = make_runtime();
        rt.block_on(async { tokio::time::sleep(Duration::from_millis(1)).await });
        // spawn is not directly tracked in block_on, but run_concurrent is
        let futures: Vec<_> = (0..4u32).map(|i| async move { i }).collect();
        rt.run_concurrent(futures);
        let m = rt.metrics();
        assert_eq!(m.tasks_spawned, 4);
        assert_eq!(m.tasks_completed, 4);
    }

    #[test]
    fn test_channel_send_recv() {
        let rt = make_runtime();
        rt.block_on(async {
            let mut ch: Channel<u32> = Channel::new(10);
            ch.sender.send(99).await.unwrap();
            let val = ch.receiver.recv().await.unwrap();
            assert_eq!(val, 99);
        });
    }
}
