"""
A5 Regression Test — Async Checkpoint & Resume Verification
Verifies that graph state is checkpointed after nodes complete,
and resuming from a checkpoint allows execution to continue without re-executing pre-checkpoint nodes.
"""

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict
from typing import Annotated
import operator

class SampleState(TypedDict):
    run_id: str
    stage_log: Annotated[list[str], operator.add]
    value: int

def node_0(state: SampleState) -> dict:
    return {"stage_log": ["n0_executed"], "value": 10}

def node_1(state: SampleState) -> dict:
    return {"stage_log": ["n1_executed"], "value": state["value"] + 5}

def node_2(state: SampleState) -> dict:
    return {"stage_log": ["n2_executed"], "value": state["value"] * 2}

@pytest.mark.asyncio
async def test_checkpoint_resume_execution() -> None:
    checkpointer = MemorySaver()
    builder = StateGraph(SampleState)
    builder.add_node("n0", node_0)
    builder.add_node("n1", node_1)
    builder.add_node("n2", node_2)

    builder.add_edge(START, "n0")
    builder.add_edge("n0", "n1")
    builder.add_edge("n1", "n2")
    builder.add_edge("n2", END)

    # Interrupt before n2 to simulate mid-run checkpointing/interruption
    graph = builder.compile(checkpointer=checkpointer, interrupt_before=["n2"])

    thread_config = {"configurable": {"thread_id": "test_run_123"}}
    
    # Run first phase up to interrupt
    initial_state = {"run_id": "test_run_123", "stage_log": [], "value": 0}
    state_after_n1 = await graph.ainvoke(initial_state, thread_config)

    assert "n0_executed" in state_after_n1["stage_log"]
    assert "n1_executed" in state_after_n1["stage_log"]
    assert "n2_executed" not in state_after_n1["stage_log"]
    assert state_after_n1["value"] == 15

    # Resume from checkpoint
    resumed_state = await graph.ainvoke(None, thread_config)

    assert "n2_executed" in resumed_state["stage_log"]
    assert resumed_state["value"] == 30
    # Assert n0 and n1 were NOT re-executed (only ran once)
    assert resumed_state["stage_log"].count("n0_executed") == 1
    assert resumed_state["stage_log"].count("n1_executed") == 1
    assert resumed_state["stage_log"].count("n2_executed") == 1
