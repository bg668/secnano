from src.v2.schemas.cognition import CognitionRequest


def build_prompt(request: CognitionRequest) -> str:
    context_block = "\n".join(request.context) if request.context else "(no external context)"
    return (
        f"SOUL:\n{request.role_spec.soul}\n\n"
        f"ROLE:\n{request.role_spec.role}\n\n"
        f"MEMORY:\n{request.role_spec.memory}\n\n"
        f"POLICY:\n{request.role_spec.policy}\n\n"
        f"CONTEXT:\n{context_block}\n\n"
        f"TASK:\n{request.inbound.task}\n\n"
        "Respond in the control format: TOOL:<tool_name> ARGS:<space separated args>"
    )
