import logging
import os


def setup_logging():
    level = os.environ.get("AGENTFLOW_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    # Suppress noisy uvicorn access logs (we have our own middleware)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"agentflow.{name}")


class _TaskLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        run_id = self.extra.get("run_id", "?")
        task_id = self.extra.get("task_id", "?")
        return f"[run={run_id} task={task_id}] {msg}", kwargs


def task_logger(run_id: str, task_id: str) -> logging.LoggerAdapter:
    logger = logging.getLogger("agentflow.orchestrator")
    return _TaskLoggerAdapter(logger, {"run_id": run_id, "task_id": task_id})
