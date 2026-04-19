"""
Agent API Router — SSE streaming endpoints for agent-powered features.

Provides:
- /agents/{company}/{product}/analyst/stream     — Research Analyst (SSE)
- /agents/{company}/{product}/analyst/sync        — Research Analyst (JSON fallback)
- /agents/{company}/{product}/memo/generate       — Memo Writer (SSE)
- /agents/{company}/{product}/memo/regenerate-section — Memo section regen (SSE)
- /agents/{company}/{product}/compliance/check    — Compliance Monitor (SSE)
- /agents/{company}/{product}/compliance/check/sync — Compliance Monitor (JSON)
- /agents/onboarding/analyze                      — Onboarding Agent (SSE)
- /agents/sessions/{session_id}                   — Session management
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Request schemas ──────────────────────────────────────────────────────

class AgentChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    snapshot: Optional[str] = None
    currency: Optional[str] = None
    as_of_date: Optional[str] = None


class MemoGenerateRequest(BaseModel):
    template_key: str
    sections: Optional[list] = None
    snapshot: Optional[str] = None
    currency: Optional[str] = None
    session_id: Optional[str] = None


class MemoSectionRequest(BaseModel):
    memo_id: str
    section_key: str
    instruction: Optional[str] = None
    session_id: Optional[str] = None


class ComplianceCheckRequest(BaseModel):
    snapshot: Optional[str] = None
    currency: Optional[str] = None
    session_id: Optional[str] = None


class OnboardingRequest(BaseModel):
    company: str
    product: str
    question: Optional[str] = None
    session_id: Optional[str] = None


# ── Agent loading ────────────────────────────────────────────────────────

def _load_agent(agent_name: str):
    """Load an agent with its tools from the registry."""
    from core.agents.config import load_agent_config
    from core.agents.runtime import AgentRunner
    from core.agents.tools import build_tools_for_agent

    tool_specs = build_tools_for_agent(agent_name)
    config = load_agent_config(agent_name, tool_specs=tool_specs)
    return AgentRunner(config)


def _get_or_create_session(session_id: Optional[str], agent_name: str, metadata: dict):
    """Load existing session or create new one."""
    from core.agents.session import AgentSession

    if session_id:
        session = AgentSession.load(session_id)
        if session:
            return session

    return AgentSession.create(agent_name, metadata=metadata)


# ── Rate limiting ────────────────────────────────────────────────────────

def _check_rate_limits(request: Request):
    """Check all rate limits. Raises HTTPException if exceeded."""
    from core.agents.rate_limit import rate_limiter

    err = rate_limiter.check_session_limit(request)
    if err:
        raise HTTPException(status_code=429, detail=err)

    err = rate_limiter.check_concurrent_limit(request)
    if err:
        raise HTTPException(status_code=429, detail=err)

    err = rate_limiter.check_token_limit(request)
    if err:
        raise HTTPException(status_code=429, detail=err)


# ── SSE streaming helper ────────────────────────────────────────────────

async def _stream_agent(agent_name: str, message: str, session, request: Request = None):
    """Generator that yields SSE events from an agent stream.

    Drains the agent's async-generator output into an asyncio.Queue via a
    background producer task so the consumer loop can wake every 500ms even
    when the agent is blocked inside a long tool call. A `: keepalive\\n\\n`
    SSE comment is emitted after 20s of idle to keep Cloudflare's edge proxy
    from cutting the connection mid-stream (~100s idle-proxy cap on Free tier).
    Comment lines are spec-ignored by clients. Mirrors the heartbeat pattern
    in memo_generate_stream. See tasks/lessons.md 2026-04-19 entry.
    """
    from core.agents.rate_limit import rate_limiter

    if request:
        rate_limiter.stream_started(request)

    queue: asyncio.Queue = asyncio.Queue()
    _SENTINEL = object()

    async def _producer():
        try:
            agent = _load_agent(agent_name)
            async for event in agent.stream(message, session):
                await queue.put(event)
        except Exception as e:
            await queue.put(("__error__", e))
        finally:
            await queue.put(_SENTINEL)

    producer_task = asyncio.create_task(_producer())
    HEARTBEAT_INTERVAL_S = 20
    last_yield = time.monotonic()

    try:
        while True:
            if request and await request.is_disconnected():
                session.save()
                producer_task.cancel()
                return

            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                if time.monotonic() - last_yield >= HEARTBEAT_INTERVAL_S:
                    # SSE comment line — ignored by clients, keeps CF edge alive
                    yield ": keepalive\n\n"
                    last_yield = time.monotonic()
                continue

            if event is _SENTINEL:
                break

            if isinstance(event, tuple) and len(event) == 2 and event[0] == "__error__":
                raise event[1]

            if event.type == "done" and request:
                total = event.data.get("total_input_tokens", 0) + event.data.get("total_output_tokens", 0)
                rate_limiter.record_tokens(request, total)

            yield event.to_sse()
            last_yield = time.monotonic()
    finally:
        if not producer_task.done():
            producer_task.cancel()
        try:
            await producer_task
        except (asyncio.CancelledError, Exception):
            pass
        if request:
            rate_limiter.stream_ended(request)


# ── Analyst endpoints ────────────────────────────────────────────────────

@router.post("/{company}/{product}/analyst/stream")
async def analyst_stream(company: str, product: str, body: AgentChatRequest, request: Request):
    """Stream analyst agent response via SSE."""
    _check_rate_limits(request)
    metadata = {
        "company": company,
        "product": product,
        "snapshot": body.snapshot,
        "currency": body.currency,
        "as_of_date": body.as_of_date,
    }
    session = _get_or_create_session(body.session_id, "analyst", metadata)

    # Inject company/product context into the question if first message
    question = body.question
    if session.turn_count == 0:
        question = f"[Context: company={company}, product={product}" + \
            (f", snapshot={body.snapshot}" if body.snapshot else "") + \
            (f", currency={body.currency}" if body.currency else "") + \
            (f", as_of_date={body.as_of_date}" if body.as_of_date else "") + \
            f"]\n\n{body.question}"

    return StreamingResponse(
        _stream_agent("analyst", question, session, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Session-Id": session.session_id,
        },
    )


@router.post("/{company}/{product}/analyst/sync")
async def analyst_sync(company: str, product: str, body: AgentChatRequest):
    """Non-streaming analyst agent (JSON response)."""
    metadata = {
        "company": company,
        "product": product,
        "snapshot": body.snapshot,
        "currency": body.currency,
    }
    session = _get_or_create_session(body.session_id, "analyst", metadata)

    question = body.question
    if session.turn_count == 0:
        question = f"[Context: company={company}, product={product}]\n\n{body.question}"

    agent = _load_agent("analyst")
    result = await agent.run(question, session)

    return {
        "answer": result.text,
        "session_id": session.session_id,
        "tool_calls": result.tool_calls_made,
        "tokens": {
            "input": result.total_input_tokens,
            "output": result.total_output_tokens,
        },
        "turns_used": result.turns_used,
    }


# ── Memo endpoints ───────────────────────────────────────────────────────

@router.post("/{company}/{product}/memo/generate")
async def memo_generate_stream(company: str, product: str, body: MemoGenerateRequest, request: Request):
    """Stream memo generation via the hybrid pipeline.

    Runs the full 6-stage pipeline in a background thread while emitting SSE
    progress events. The memo is persisted via MemoStorage.save() before the
    final 'done' event is sent, so the frontend receives a valid memo_id.
    """
    _check_rate_limits(request)

    # Run the generator in a thread and bridge its progress_cb to an asyncio queue.
    # This keeps the pipeline synchronous (already thread-parallel internally)
    # while letting us yield SSE events as stages complete.
    async def event_stream():
        import concurrent.futures
        from core.memo.generator import MemoGenerator
        from core.memo.storage import MemoStorage

        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def progress_cb(event_type: str, payload: dict):
            # Called from worker thread — thread-safe put via loop
            try:
                loop.call_soon_threadsafe(queue.put_nowait, (event_type, payload))
            except RuntimeError:
                pass  # Loop closed — stream ending

        def _run_pipeline():
            generator = MemoGenerator()
            memo = generator.generate_full_memo(
                company=company,
                product=product,
                template_key=body.template_key,
                custom_sections=body.sections,
                snapshot=body.snapshot,
                currency=body.currency,
                progress_cb=progress_cb,
                polish=True,
            )
            # Capture transient data (research packs) BEFORE save strips them.
            research_packs_copy = dict(memo.get("_research_packs") or {})

            # Persist before signalling done
            storage = MemoStorage()
            try:
                storage.save(memo)
            except Exception as e:
                logger.error("Memo save failed in agent pipeline: %s", e)
                progress_cb("error", {"message": f"save_failed: {e}"})
                return memo

            # Best-effort: record the memo's thesis signal into Company Mind
            # so future memos see prior recommendations and can flag drift.
            try:
                from core.memo.agent_research import record_memo_thesis_to_mind
                record_memo_thesis_to_mind(memo, research_packs=research_packs_copy)
            except Exception as e:
                logger.warning("Thesis recording failed: %s", e)

            progress_cb("saved", {
                "memo_id": memo["id"],
                "generation_mode": memo.get("generation_mode"),
                "polished": memo.get("polished"),
                "elapsed_s": (memo.get("generation_meta") or {}).get("total_elapsed_s"),
                "cost_usd_estimate": (memo.get("generation_meta") or {}).get("cost_usd_estimate"),
                "models_used": memo.get("models_used"),
            })
            return memo

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(_run_pipeline)

        # Heartbeat cadence: CF Free idle-proxy cap is ~100s. Individual pipeline
        # stages (research, polish) can run 60-90s without emitting progress,
        # which triggers a silent edge cut and browser sees ERR_HTTP2_PROTOCOL_ERROR
        # ("network error"). An SSE comment line (`:`-prefixed) is ignored by
        # clients per spec but keeps byte flow alive through the proxy.
        # See tasks/lessons.md 2026-04-19 entry on CF HTTP/2 + SSE.
        HEARTBEAT_INTERVAL_S = 20

        # Stream events until the future resolves
        last_yield = time.monotonic()
        done = False
        while not done:
            try:
                event_type, payload = await asyncio.wait_for(queue.get(), timeout=0.5)
                data = json.dumps(payload)
                yield f"event: {event_type}\ndata: {data}\n\n"
                last_yield = time.monotonic()
                if event_type in ("saved", "error"):
                    done = True
            except asyncio.TimeoutError:
                if future.done():
                    # Drain any pending events then exit
                    while not queue.empty():
                        event_type, payload = queue.get_nowait()
                        yield f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"
                        last_yield = time.monotonic()
                    done = True
                elif time.monotonic() - last_yield >= HEARTBEAT_INTERVAL_S:
                    # SSE comment line — ignored by clients, keeps CF edge alive
                    yield ": keepalive\n\n"
                    last_yield = time.monotonic()
                continue
            if await request.is_disconnected():
                logger.info("Client disconnected from memo stream")
                done = True

        # Final done event so the frontend stops listening
        try:
            memo = future.result(timeout=5)
            yield f"event: done\ndata: {json.dumps({'memo_id': memo.get('id'), 'ok': True})}\n\n"
        except Exception as e:
            logger.error("Memo pipeline failed: %s", e)
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
        finally:
            executor.shutdown(wait=False)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{company}/{product}/memo/regenerate-section")
async def memo_regenerate_section(company: str, product: str, body: MemoSectionRequest, request: Request):
    """Regenerate a single memo section."""
    _check_rate_limits(request)
    metadata = {
        "company": company,
        "product": product,
        "memo_id": body.memo_id,
    }
    session = _get_or_create_session(body.session_id, "memo_writer", metadata)

    instruction = body.instruction or "Regenerate this section with fresh data."
    prompt = (
        f"Regenerate section '{body.section_key}' for memo {body.memo_id} ({company}/{product})."
        f" {instruction}"
        f" Pull fresh analytics and data room research. Output as JSON with keys: section_key, title, content, metrics, citations."
    )

    return StreamingResponse(
        _stream_agent("memo_writer", prompt, session, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Session-Id": session.session_id,
        },
    )


# ── Compliance endpoints ─────────────────────────────────────────────────

@router.post("/{company}/{product}/compliance/check")
async def compliance_check_stream(company: str, product: str, body: ComplianceCheckRequest, request: Request):
    """Stream compliance check via agent."""
    _check_rate_limits(request)

    # Compliance cooldown
    from core.agents.rate_limit import rate_limiter
    force = getattr(body, 'force', False)
    err = rate_limiter.check_compliance_cooldown(company, product, force=force)
    if err:
        raise HTTPException(status_code=429, detail=err)
    rate_limiter.record_compliance_run(company, product)

    metadata = {
        "company": company,
        "product": product,
        "snapshot": body.snapshot,
    }
    session = _get_or_create_session(body.session_id, "compliance_monitor", metadata)

    prompt = (
        f"Run a full covenant compliance check for {company}/{product}."
        f" Check all covenants, report pass/breach for each, investigate root causes for any breaches,"
        f" and record material findings."
    )
    if body.snapshot:
        prompt += f" Use snapshot: {body.snapshot}."

    return StreamingResponse(
        _stream_agent("compliance_monitor", prompt, session, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Session-Id": session.session_id,
        },
    )


@router.post("/{company}/{product}/compliance/check/sync")
async def compliance_check_sync(company: str, product: str, body: ComplianceCheckRequest):
    """Non-streaming compliance check."""
    metadata = {"company": company, "product": product}
    session = _get_or_create_session(body.session_id, "compliance_monitor", metadata)

    prompt = f"Run a full covenant compliance check for {company}/{product}."
    if body.snapshot:
        prompt += f" Use snapshot: {body.snapshot}."

    agent = _load_agent("compliance_monitor")
    result = await agent.run(prompt, session)

    return {
        "report": result.text,
        "session_id": session.session_id,
        "tool_calls": result.tool_calls_made,
        "turns_used": result.turns_used,
    }


# ── Onboarding endpoint ─────────────────────────────────────────────────

@router.post("/onboarding/analyze")
async def onboarding_analyze(body: OnboardingRequest, request: Request):
    """Stream onboarding analysis."""
    _check_rate_limits(request)
    metadata = {
        "company": body.company,
        "product": body.product,
    }
    session = _get_or_create_session(body.session_id, "onboarding", metadata)

    prompt = body.question or (
        f"Analyze the data for {body.company}/{body.product}."
        f" Inspect the tape structure, classify columns, assess data quality,"
        f" and propose a configuration for the platform."
    )

    return StreamingResponse(
        _stream_agent("onboarding", prompt, session, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Session-Id": session.session_id,
        },
    )


# ── Session management ───────────────────────────────────────────────────

@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session details (without full message history)."""
    from core.agents.session import AgentSession

    session = AgentSession.load(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    return {
        "session_id": session.session_id,
        "agent_name": session.agent_name,
        "metadata": session.metadata,
        "created_at": session.created_at,
        "last_active": session.last_active,
        "turn_count": session.turn_count,
        "total_tokens": session.total_tokens,
        "message_count": len(session.messages),
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    from core.agents.session import AgentSession

    session = AgentSession.load(session_id)
    if session:
        session.delete()
    return {"status": "deleted"}


@router.get("/sessions")
async def list_sessions(limit: int = 20):
    """List recent agent sessions."""
    from core.agents.session import AgentSession
    return AgentSession.list_recent(limit=limit)


@router.get("/rate-limits")
async def get_rate_limits(request: Request):
    """Get current rate limit stats for the authenticated user."""
    from core.agents.rate_limit import rate_limiter
    return rate_limiter.get_user_stats(request)
