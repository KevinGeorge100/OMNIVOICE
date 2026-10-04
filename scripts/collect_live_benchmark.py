"""Live Gateway Server-Latency Benchmark Collection Runner for OV-006.
Executes multi-session, multi-turn live calls against the real OmniVoice engine.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from omnivoice.config import Settings
from omnivoice.rag import Knowledge
from omnivoice.session import CallSession
from omnivoice.store import Store
from omnivoice.transport import MediaTransport
from omnivoice.vad import SileroFactory


class BenchmarkSocket:
    """Mock WebSocket transport that receives real streaming PCM frames and marks."""
    def __init__(self):
        self.sent = []
        self.closed = False

    async def send_json(self, data):
        self.sent.append(data)

    async def send_bytes(self, data):
        self.sent.append(data)

    async def close(self, code=1000):
        self.closed = True


SESSION_WORKLOADS = [
    # Session 1: Admissions & Campus Inquiries (Mix of FAQ + RAG + Limitations)
    [
        ("What are your campus hours?", "faq"),
        ("Where is the admissions office located?", "faq"),
        ("What is the contact email for support?", "faq"),
        ("What are the core course requirements for the Computer Science undergraduate program?", "rag"),
        ("Are there elective courses in Artificial Intelligence or Cloud Computing?", "rag"),
        ("What are the tuition fees for the MBA program?", "limitation"),
        ("Can you please double-check the MBA tuition fees?", "limitation_repeat"),
        ("When does the fall semester start?", "faq"),
        ("Is parking available on campus?", "faq"),
    ],
    # Session 2: Financial Aid & Scholarships
    [
        ("What are the eligibility requirements for merit-based scholarships?", "rag"),
        ("How are need-based institutional grants evaluated?", "rag"),
        ("When is the deadline to submit applications for spring semester aid?", "rag"),
        ("What is the penalty fee for late tuition payment?", "limitation"),
        ("What are your campus hours?", "faq"),
        ("Where is the admissions office located?", "faq"),
        ("Tell me about the capstone project in the computer science curriculum.", "rag"),
        ("What are the quiet study hours in the library?", "rag"),
        ("Can you transfer me to the financial aid officer?", "unsupported_action"),
    ],
    # Session 3: Housing & Campus Life
    [
        ("What types of room accommodations are offered in on-campus student housing?", "rag"),
        ("Are first-year residential students required to register for a meal plan?", "rag"),
        ("What facilities and security services are available in the hostels?", "rag"),
        ("What is the monthly cost for a single room with air conditioning?", "limitation"),
        ("When does the fall semester orientation begin?", "faq"),
        ("Is parking available on campus for visitors?", "faq"),
        ("What resources and digital journals are available at the central library?", "rag"),
        ("What is the contact email for support?", "faq"),
        ("Can you send me an email with the housing contract?", "unsupported_action"),
    ],
    # Session 4: Academics & International Student Support
    [
        ("How many credit hours must an international student maintain to preserve visa status?", "rag"),
        ("What advising and cultural services does the International Student Office provide?", "rag"),
        ("What are the prerequisites for the Data Structures and Algorithms courses?", "rag"),
        ("What is the minimum cumulative GPA required to maintain a scholarship?", "rag"),
        ("What are the hourly rates for campus parking pass?", "limitation"),
        ("Where is the admissions office located?", "faq"),
        ("What are your campus hours?", "faq"),
        ("Tell me about the multimedia production labs in the library.", "rag"),
        ("When does the fall semester start?", "faq"),
    ],
    # Session 5: Comprehensive Cross-Domain Evaluation
    [
        ("What are the required core subjects in Computer Science?", "rag"),
        ("Are cybersecurity and mobile app development offered as electives?", "rag"),
        ("What are the 24-hour study spaces available during exam periods?", "rag"),
        ("What is the meal plan cancellation fee?", "limitation"),
        ("Is parking available on campus?", "faq"),
        ("What is the contact email for support?", "faq"),
        ("What is the deadline for spring financial aid applications?", "rag"),
        ("Do international students have access to visa advising on campus?", "rag"),
        ("What are your campus hours?", "faq"),
        ("Where is the admissions office located?", "faq"),
    ],
    # Session 6: In-Depth Exploration & Edge Conditions
    [
        ("Explain the two-semester capstone project required for CS students.", "rag"),
        ("How many digital journals and print volumes does the library house?", "rag"),
        ("What facilities are included with on-campus student housing?", "rag"),
        ("What are the tuition fees for international students?", "limitation"),
        ("Are you sure there is no record of international tuition fees?", "limitation_repeat"),
        ("What is the minimum GPA needed for merit scholarships?", "rag"),
        ("When does the fall semester start?", "faq"),
        ("What are your campus hours?", "faq"),
        ("Can you book an appointment with an academic advisor for me?", "unsupported_action"),
        ("What is the contact email for support?", "faq"),
    ]
]


async def run_benchmark():
    settings = Settings()
    store = Store(settings.database)
    await store.open()
    
    tenant = await store.tenant("9d4ecfa5a2e34720abe284275c2d36e7")
    if not tenant:
        print("Error: Test tenant not found in database!")
        return

    vad_factory = SileroFactory(settings.silero_model) if settings.silero_model.is_file() else None
    
    http_client = httpx.AsyncClient(
        limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        follow_redirects=False,
        trust_env=False,
    )
    
    knowledge = Knowledge(store, None)
    await knowledge.refresh(tenant["id"])
    
    from omnivoice.providers import Groq
    llm = Groq(settings, http_client)
    
    from types import SimpleNamespace

    from omnivoice.actions import ActionEngine
    from omnivoice.events import TenantEvents
    
    services = SimpleNamespace(
        settings=settings,
        store=store,
        knowledge=knowledge,
        llm=llm,
        vad=vad_factory,
        actions=ActionEngine(store, http_client),
        events=TenantEvents(),
        active={},
    )
    
    print(f"\n{'='*75}")
    print("STARTING OV-006 LIVE GATEWAY SERVER-LATENCY BENCHMARK COLLECTION")
    print(f"{'='*75}\n")
    print(f"Target: {len(SESSION_WORKLOADS)} sessions with ~{sum(len(w) for w in SESSION_WORKLOADS)} total turns")
    print(f"Provider: Groq ({settings.groq_model}) + Sarvam TTS ({settings.tts_model}, {settings.tts_speaker})")
    print(f"Database: {settings.database}\n")
    
    # Clean previous benchmark runs from DB to ensure clean session records
    await store.execute("DELETE FROM calls WHERE status IN ('completed', 'interrupted', 'active')")
    
    total_valid_turns = 0
    session_records = []
    
    for sess_idx, workload in enumerate(SESSION_WORKLOADS, 1):
        import uuid
        call_id = uuid.uuid4().hex
        print(f"\n--- SESSION {sess_idx}/{len(SESSION_WORKLOADS)} (ID: {call_id[:8]}...) ---")
        
        ws = BenchmarkSocket()
        transport = MediaTransport(ws, "exotel", f"bench_{call_id[:8]}")
        session = CallSession(call_id, tenant, transport, services)
        session.line_number = "+914954269065"
        services.active[call_id] = session
        
        call_start = time.time()
        await store.execute(
            "INSERT INTO calls (id,tenant_id,provider,status,started) VALUES (?,?,?,?,?)",
            (call_id, tenant["id"], "exotel", "active", call_start),
        )
        
        # 1. Greet
        await session.tts.open()
        await session.greet()
        greeting_ms = session.metrics.get('greeting_first_audio_ms') or 0
        print(f"  [Greeting] Sent in {greeting_ms:.1f} ms")
        
        # 2. Execute workload turns
        for turn_idx, (user_text, turn_type) in enumerate(workload, 1):
            t_start = time.perf_counter()
            # Simulate a realistic VAD speech-end 120ms before STT final arrives
            voice_at_final = t_start - 0.120
            endpoint_delay = 120.0
            
            # Execute live response pipeline
            await session.respond(user_text, t_start, session.generation_id, voice_at_final, endpoint_delay)
            
            # Retrieve latest recorded turn metric
            if session.metrics["turns"]:
                t_metric = session.metrics["turns"][-1]
                turn_path = t_metric.get("path", "unknown")
                turnaround = t_metric.get("final_transcript_to_first_audio_sent_ms")
                ttft = t_metric.get("llm_ttft_ms")
                ttfa = t_metric.get("first_tts_ttfa_ms")
                turnaround_str = f"{turnaround:.1f}" if isinstance(turnaround, (int, float)) else "—"
                ttft_str = f"{round(ttft,1)}" if isinstance(ttft, (int, float)) else "—"
                ttfa_str = f"{round(ttfa,1)}" if isinstance(ttfa, (int, float)) else "—"
                err = t_metric.get("error")
                
                print(f"  Turn {turn_idx:02d} [{turn_type.upper():<12} | {turn_path:<14}]: turnaround={turnaround_str}ms | TTFT={ttft_str:<6}ms | TTFA={ttfa_str}ms | err={err} | Q: '{user_text[:35]}...'")
                if not err and turnaround is not None:
                    total_valid_turns += 1
                
            await asyncio.sleep(0.05)
            
        # Complete session
        call_end = time.time()
        services.active.pop(call_id, None)
        await store.execute(
            "UPDATE calls SET status='completed',ended=?,metrics=? WHERE id=?",
            (call_end, json.dumps(session.metrics), call_id),
        )
        await session.tts.close()
        session_records.append((call_id, len(session.metrics["turns"]), call_end - call_start))
        print(f"  Session {sess_idx} Completed: {len(session.metrics['turns'])} turns in {call_end - call_start:.1f}s")
        
    await store.close()
    await http_client.aclose()
    
    print(f"\n{'='*75}")
    print(f"BENCHMARK COLLECTION COMPLETE: {total_valid_turns} VALID TURNS ACROSS {len(session_records)} SESSIONS")
    print(f"{'='*75}\n")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
