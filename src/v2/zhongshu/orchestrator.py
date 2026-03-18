from __future__ import annotations

from dataclasses import dataclass

from src.v2.hanlin.retriever import query
from src.v2.schemas.cognition import CognitionRequest
from src.v2.schemas.inbound import InboundEvent
from src.v2.schemas.reply import Reply
from src.v2.schemas.roles import RoleSpec
from src.v2.schemas.task import ExecutionResult
from src.v2.zhongshu.cognition.runtime import run_cognition


@dataclass(frozen=True)
class OrchestrationOutput:
    reply: Reply
    cognition_result: object
    execution_result: ExecutionResult


def orchestrate(event: InboundEvent, role_spec: RoleSpec, backend) -> OrchestrationOutput:
    context = tuple(query(event.task))
    cognition = run_cognition(
        CognitionRequest(inbound=event, role_spec=role_spec, context=context)
    )
    execution = backend.execute(cognition.execution_request)
    reply = Reply(task_id=event.task_id, content=execution.output)
    return OrchestrationOutput(reply=reply, cognition_result=cognition, execution_result=execution)
