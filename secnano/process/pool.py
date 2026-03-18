"""子进程池。

参考 nanoclaw group-queue.ts 的三个核心机制，用 Python asyncio 原语简化：
1. 全局并发上限    → asyncio.Semaphore      (等效 GroupQueue.activeCount + MAX_CONCURRENT_CONTAINERS)
2. 进程生命周期管理 → _running dict           (等效 GroupQueue.groups Map + GroupState)
3. 超时 + 强杀    → asyncio.wait_for + kill (等效 container-runner.ts killOnTimeout)

不需要移植的 nanoclaw 逻辑：
- drainGroup/drainWaiting: Semaphore 自然阻塞，无需手动 drain
- sendMessage/closeStdin/notifyIdle: pipe 替代文件 IPC
- scheduleRetry/retryCount: 第一版不做自动重试
- isTaskContainer/pendingMessages 区分: 只有任务执行，无消息模式
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Awaitable, Callable

from secnano.process.protocol import WorkerInput, WorkerMessage

# 默认并发上限，等效 nanoclaw config.ts 的 MAX_CONCURRENT_CONTAINERS
DEFAULT_MAX_CONCURRENT = 4
# 默认超时，等效 nanoclaw config.ts 的 CONTAINER_TIMEOUT
DEFAULT_TIMEOUT = 300
# 终止优雅等待期：terminate 后等这么久再 kill，
# 等效 nanoclaw container-runner.ts 的 exec(stopContainer, {timeout: 15000})
TERMINATE_GRACE_SECONDS = 5


class ProcessPool:

    def __init__(self, max_concurrent: int = DEFAULT_MAX_CONCURRENT):
        self._sem = asyncio.Semaphore(max_concurrent)
        self._running: dict[str, asyncio.subprocess.Process] = {}

    async def run(
        self,
        task: WorkerInput,
        on_message: Callable[[WorkerMessage], Awaitable[None]] | None = None,
    ) -> WorkerMessage:
        """启动子进程执行任务，阻塞直到完成或超时。返回最终的 result/error WorkerMessage。

        流程对应 nanoclaw container-runner.ts runContainerAgent():
        1. sem.acquire()     ← 等效 GroupQueue 并发检查 (group-queue.ts L73)
        2. create_subprocess ← 等效 spawn(CONTAINER_RUNTIME_BIN, ...) (container-runner.ts L296)
        3. stdin.write(JSON) ← 等效 container.stdin.write(JSON.stringify(input)) (container-runner.ts L310)
        4. stdin.close()     ← 等效 container.stdin.end() (container-runner.ts L311)
        5. read stdout lines ← 等效 container.stdout.on('data') + OUTPUT_MARKER 解析 (container-runner.ts L319-375)
        6. wait_for(timeout) ← 等效 setTimeout(killOnTimeout, timeoutMs) (container-runner.ts L410-430)
        7. proc.wait()       ← 等效 container.on('close') (container-runner.ts L435)
        """
        async with self._sem:
            return await self._run_guarded(task, on_message)

    async def _run_guarded(
        self,
        task: WorkerInput,
        on_message: Callable[[WorkerMessage], Awaitable[None]] | None,
    ) -> WorkerMessage:
        python = sys.executable
        proc = await asyncio.create_subprocess_exec(
            python, "-m", "secnano.process.worker",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._running[task.task_id] = proc

        try:
            # 发送任务 (等效 nanoclaw container.stdin.write + .end)
            assert proc.stdin is not None
            proc.stdin.write(task.to_json_line().encode() + b"\n")
            await proc.stdin.drain()
            proc.stdin.close()

            # 带超时读取结果 (等效 nanoclaw killOnTimeout)
            result = await asyncio.wait_for(
                self._read_output(proc, task.task_id, on_message),
                timeout=task.timeout,
            )
            return result

        except asyncio.TimeoutError:
            # 等效 nanoclaw container-runner.ts L416-428:
            # exec(stopContainer) → 优雅终止 → 超时后 SIGKILL
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=TERMINATE_GRACE_SECONDS)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()

            return WorkerMessage(
                type="error",
                task_id=task.task_id,
                content=f"子进程超时（{task.timeout}s），已终止",
            )

        except Exception as e:
            # 等效 nanoclaw container.on('error') (container-runner.ts L632-639)
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
            return WorkerMessage(
                type="error",
                task_id=task.task_id,
                content=f"子进程执行异常: {e}",
            )

        finally:
            self._running.pop(task.task_id, None)

    async def _read_output(
        self,
        proc: asyncio.subprocess.Process,
        task_id: str,
        on_message: Callable[[WorkerMessage], Awaitable[None]] | None,
    ) -> WorkerMessage:
        """逐行读 stdout jsonlines。

        等效 nanoclaw container-runner.ts L319-375 的 OUTPUT_MARKER 流式解析，
        但简化为每行一个完整 JSON，无需 sentinel marker 配对。
        """
        last_result: WorkerMessage | None = None
        assert proc.stdout is not None

        async for raw_line in proc.stdout:
            line = raw_line.decode().strip()
            if not line:
                continue
            try:
                msg = WorkerMessage.from_json_line(line)
            except (json.JSONDecodeError, TypeError):
                continue  # 忽略非 JSON 行（如 print 调试输出）

            if on_message:
                await on_message(msg)

            if msg.type in {"result", "error"}:
                last_result = msg

        # 等效 nanoclaw container.on('close') (container-runner.ts L435)
        returncode = await proc.wait()

        if last_result:
            return last_result

        # 无输出但正常退出 → 等效 nanoclaw "Container completed but no output"
        if returncode == 0:
            return WorkerMessage(type="result", task_id=task_id, content="任务完成，但无输出")
        else:
            # 读 stderr 辅助诊断（等效 nanoclaw container-runner.ts L595-610 读 stderr 切片）
            stderr_data = ""
            if proc.stderr:
                stderr_bytes = await proc.stderr.read()
                stderr_data = stderr_bytes.decode(errors="replace")[-2000:]
            return WorkerMessage(
                type="error",
                task_id=task_id,
                content=f"子进程退出码 {returncode}: {stderr_data}",
            )

    async def cancel(self, task_id: str) -> bool:
        """取消运行中的子进程。等效 nanoclaw GroupQueue 的进程强杀。"""
        if proc := self._running.get(task_id):
            proc.kill()
            await proc.wait()
            self._running.pop(task_id, None)
            return True
        return False

    def get_running_count(self) -> int:
        return len(self._running)
