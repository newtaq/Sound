from enum import StrEnum


class AgentActionType(StrEnum):
    TOOL_CALL = "tool_call"
    FINISH = "finish"
    

