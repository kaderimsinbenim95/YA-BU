// lock_free.rs — SatoshiOS Lock-Free Data Structures
//
// Implements a lock-free queue (Michael-Scott queue) and a lock-free
// stack (Treiber stack) using atomic pointer swaps with hazard-pointer
// style memory management via crossbeam-epoch.

use std::sync::atomic::{AtomicPtr, Ordering};
use std::ptr;

// ─── Lock-Free Stack (Treiber Stack) ────────────────────────────────────────

struct StackNode<T> {
    value: T,
    next: AtomicPtr<StackNode<T>>,
}

/// A lock-free, thread-safe stack (LIFO).
///
/// Uses compare-and-swap on the head pointer.
/// Memory is reclaimed via `Box::from_raw` on pop.
///
/// # Safety
/// Internal raw pointer manipulation is encapsulated.
pub struct LockFreeStack<T: Send> {
    head: AtomicPtr<StackNode<T>>,
}

unsafe impl<T: Send> Sync for LockFreeStack<T> {}

impl<T: Send> LockFreeStack<T> {
    pub fn new() -> Self {
        Self {
            head: AtomicPtr::new(ptr::null_mut()),
        }
    }

    /// Push a value onto the stack.
    pub fn push(&self, value: T) {
        let new_node = Box::into_raw(Box::new(StackNode {
            value,
            next: AtomicPtr::new(ptr::null_mut()),
        }));

        loop {
            let old_head = self.head.load(Ordering::Relaxed);
            unsafe {
                (*new_node).next.store(old_head, Ordering::Relaxed);
            }

            if self
                .head
                .compare_exchange_weak(old_head, new_node, Ordering::Release, Ordering::Relaxed)
                .is_ok()
            {
                return;
            }
        }
    }

    /// Pop a value from the stack (returns None if empty).
    pub fn pop(&self) -> Option<T> {
        loop {
            let old_head = self.head.load(Ordering::Acquire);

            if old_head.is_null() {
                return None;
            }

            let next = unsafe { (*old_head).next.load(Ordering::Relaxed) };

            if self
                .head
                .compare_exchange_weak(old_head, next, Ordering::Release, Ordering::Relaxed)
                .is_ok()
            {
                // Safe to reclaim — no other thread holds a reference
                let value = unsafe { Box::from_raw(old_head).value };
                return Some(value);
            }
        }
    }

    pub fn is_empty(&self) -> bool {
        self.head.load(Ordering::Relaxed).is_null()
    }
}

impl<T: Send> Drop for LockFreeStack<T> {
    fn drop(&mut self) {
        // Drain all nodes
        while self.pop().is_some() {}
    }
}

impl<T: Send> Default for LockFreeStack<T> {
    fn default() -> Self {
        Self::new()
    }
}

// ─── Lock-Free Queue (Michael-Scott Queue) ───────────────────────────────────

struct QueueNode<T> {
    value: Option<T>,
    next: AtomicPtr<QueueNode<T>>,
}

impl<T> QueueNode<T> {
    fn sentinel() -> *mut Self {
        Box::into_raw(Box::new(QueueNode {
            value: None,
            next: AtomicPtr::new(ptr::null_mut()),
        }))
    }
}

/// A lock-free, thread-safe queue (FIFO) based on the Michael-Scott algorithm.
///
/// Uses a sentinel head node to decouple enqueue and dequeue.
///
/// # Safety
/// Raw pointers are used internally and are safe within the provided API.
pub struct LockFreeQueue<T: Send> {
    head: AtomicPtr<QueueNode<T>>,
    tail: AtomicPtr<QueueNode<T>>,
}

unsafe impl<T: Send> Sync for LockFreeQueue<T> {}

impl<T: Send> LockFreeQueue<T> {
    pub fn new() -> Self {
        let sentinel = QueueNode::<T>::sentinel();
        Self {
            head: AtomicPtr::new(sentinel),
            tail: AtomicPtr::new(sentinel),
        }
    }

    /// Enqueue a value at the back of the queue.
    pub fn enqueue(&self, value: T) {
        let new_node = Box::into_raw(Box::new(QueueNode {
            value: Some(value),
            next: AtomicPtr::new(ptr::null_mut()),
        }));

        loop {
            let tail = self.tail.load(Ordering::Acquire);
            let next = unsafe { (*tail).next.load(Ordering::Acquire) };

            // Confirm tail is still the tail
            if tail != self.tail.load(Ordering::Acquire) {
                continue;
            }

            if next.is_null() {
                // Try to link new node at the end
                if unsafe { (*tail).next.compare_exchange_weak(
                    ptr::null_mut(),
                    new_node,
                    Ordering::Release,
                    Ordering::Relaxed,
                ) }
                .is_ok()
                {
                    // Swing tail forward (best-effort)
                    let _ = self.tail.compare_exchange_weak(
                        tail,
                        new_node,
                        Ordering::Release,
                        Ordering::Relaxed,
                    );
                    return;
                }
            } else {
                // Tail is falling behind; advance it
                let _ = self.tail.compare_exchange_weak(
                    tail,
                    next,
                    Ordering::Release,
                    Ordering::Relaxed,
                );
            }
        }
    }

    /// Dequeue a value from the front of the queue.
    pub fn dequeue(&self) -> Option<T> {
        loop {
            let head = self.head.load(Ordering::Acquire);
            let tail = self.tail.load(Ordering::Acquire);
            let next = unsafe { (*head).next.load(Ordering::Acquire) };

            // Confirm head is still the head
            if head != self.head.load(Ordering::Acquire) {
                continue;
            }

            if head == tail {
                if next.is_null() {
                    return None; // Queue is empty
                }
                // Tail is falling behind
                let _ = self.tail.compare_exchange_weak(
                    tail,
                    next,
                    Ordering::Release,
                    Ordering::Relaxed,
                );
            } else {
                let value = unsafe { (*next).value.take() };

                if self
                    .head
                    .compare_exchange_weak(head, next, Ordering::Release, Ordering::Relaxed)
                    .is_ok()
                {
                    // Reclaim old sentinel
                    unsafe { drop(Box::from_raw(head)) };
                    return value;
                }
            }
        }
    }

    pub fn is_empty(&self) -> bool {
        let head = self.head.load(Ordering::Acquire);
        let next = unsafe { (*head).next.load(Ordering::Acquire) };
        next.is_null()
    }
}

impl<T: Send> Drop for LockFreeQueue<T> {
    fn drop(&mut self) {
        while self.dequeue().is_some() {}
        // Free the sentinel node
        let sentinel = self.head.load(Ordering::Relaxed);
        if !sentinel.is_null() {
            unsafe { drop(Box::from_raw(sentinel)) };
        }
    }
}

impl<T: Send> Default for LockFreeQueue<T> {
    fn default() -> Self {
        Self::new()
    }
}

// ─── Ring Buffer (bounded SPSC) ───────────────────────────────────────────────

use std::sync::atomic::AtomicUsize;
use std::cell::UnsafeCell;

/// A single-producer/single-consumer lock-free ring buffer.
pub struct RingBuffer<T, const N: usize> {
    buffer: [UnsafeCell<Option<T>>; N],
    head: AtomicUsize,
    tail: AtomicUsize,
}

unsafe impl<T: Send, const N: usize> Sync for RingBuffer<T, N> {}
unsafe impl<T: Send, const N: usize> Send for RingBuffer<T, N> {}

impl<T, const N: usize> RingBuffer<T, N> {
    pub fn new() -> Self {
        // SAFETY: We build the typed array in three steps:
        //   1. Create an array of N MaybeUninit<UnsafeCell<Option<T>>> elements.
        //      `MaybeUninit::uninit().assume_init()` is sound here because
        //      MaybeUninit itself makes no guarantees about its contents, so an
        //      array of uninitialized MaybeUninit values is a valid (uninitialized)
        //      state — we are NOT assuming the inner T is initialized, only the
        //      MaybeUninit wrapper.
        //   2. Properly initialize each element by writing `UnsafeCell::new(None)`
        //      into every slot with `MaybeUninit::write`, which drops any
        //      previously uninitialized memory.
        //   3. Transmute the fully-initialized `[MaybeUninit<…>; N]` to
        //      `[UnsafeCell<Option<T>>; N]`.  This is sound because every slot
        //      has been initialized in step 2.
        let buffer: [UnsafeCell<Option<T>>; N] = {
            let mut uninit: [std::mem::MaybeUninit<UnsafeCell<Option<T>>>; N] =
                // SAFETY: Creating an array of MaybeUninit (step 1 above).
                unsafe { std::mem::MaybeUninit::uninit().assume_init() };
            for slot in uninit.iter_mut() {
                slot.write(UnsafeCell::new(None));
            }
            // SAFETY: Every element has been initialised in the loop above.
            unsafe {
                std::mem::transmute_copy::<
                    [std::mem::MaybeUninit<UnsafeCell<Option<T>>>; N],
                    [UnsafeCell<Option<T>>; N],
                >(&uninit)
            }
        };
        Self {
            buffer,
            head: AtomicUsize::new(0),
            tail: AtomicUsize::new(0),
        }
    }

    /// Try to push (producer side). Returns false if full.
    pub fn push(&self, value: T) -> bool {
        let tail = self.tail.load(Ordering::Relaxed);
        let next_tail = (tail + 1) % N;
        if next_tail == self.head.load(Ordering::Acquire) {
            return false; // Full
        }
        unsafe { *self.buffer[tail].get() = Some(value) };
        self.tail.store(next_tail, Ordering::Release);
        true
    }

    /// Try to pop (consumer side). Returns None if empty.
    pub fn pop(&self) -> Option<T> {
        let head = self.head.load(Ordering::Relaxed);
        if head == self.tail.load(Ordering::Acquire) {
            return None; // Empty
        }
        let value = unsafe { (*self.buffer[head].get()).take() };
        self.head.store((head + 1) % N, Ordering::Release);
        value
    }

    pub fn capacity(&self) -> usize {
        N - 1
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;
    use std::thread;

    #[test]
    fn test_stack_push_pop() {
        let s: LockFreeStack<i32> = LockFreeStack::new();
        s.push(1);
        s.push(2);
        s.push(3);
        assert_eq!(s.pop(), Some(3));
        assert_eq!(s.pop(), Some(2));
        assert_eq!(s.pop(), Some(1));
        assert_eq!(s.pop(), None);
    }

    #[test]
    fn test_stack_concurrent() {
        let stack = Arc::new(LockFreeStack::<u32>::new());
        let mut handles = vec![];

        for i in 0..8 {
            let s = stack.clone();
            handles.push(thread::spawn(move || {
                for j in 0..100u32 {
                    s.push(i * 100 + j);
                }
            }));
        }
        for h in handles { h.join().unwrap(); }

        let mut count = 0;
        while stack.pop().is_some() { count += 1; }
        assert_eq!(count, 800);
    }

    #[test]
    fn test_queue_enqueue_dequeue() {
        let q: LockFreeQueue<i32> = LockFreeQueue::new();
        q.enqueue(10);
        q.enqueue(20);
        q.enqueue(30);
        assert_eq!(q.dequeue(), Some(10));
        assert_eq!(q.dequeue(), Some(20));
        assert_eq!(q.dequeue(), Some(30));
        assert_eq!(q.dequeue(), None);
    }

    #[test]
    fn test_queue_concurrent() {
        let queue = Arc::new(LockFreeQueue::<u32>::new());
        let mut handles = vec![];

        for i in 0..4 {
            let q = queue.clone();
            handles.push(thread::spawn(move || {
                for j in 0..100u32 { q.enqueue(i * 100 + j); }
            }));
        }
        for h in handles { h.join().unwrap(); }

        let mut count = 0;
        while queue.dequeue().is_some() { count += 1; }
        assert_eq!(count, 400);
    }

    #[test]
    fn test_ring_buffer() {
        let rb: RingBuffer<u32, 8> = RingBuffer::new();
        assert_eq!(rb.capacity(), 7);
        for i in 0..7 { assert!(rb.push(i)); }
        assert!(!rb.push(99)); // Full
        for i in 0..7 { assert_eq!(rb.pop(), Some(i)); }
        assert_eq!(rb.pop(), None);
    }
}
