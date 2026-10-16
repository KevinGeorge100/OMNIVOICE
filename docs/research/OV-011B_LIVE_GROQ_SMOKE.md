# OV-011B optional live Groq smoke

On 2026-10-16, `scripts/live_sales_tool_selection.py` submitted three synthetic, single-turn requests to the configured Groq model. After tightening the tool-selection prompt, the final run selected `lookup_lead`, `check_demo_slots`, and `schedule_demo` for their matching requests: **3/3**. An earlier run selected only the two read tools and asked for booking confirmation itself; the server would not have committed a booking from that response. This prompted the instruction to stage a write before asking for confirmation.

This is a small live model-selection check, separate from the 25-case deterministic orchestration evaluation. It did not execute a live write, synthesize speech, connect to a carrier, or establish a statistically reliable selection accuracy. The synthetic lead and slot were held in a temporary SQLite database and removed after the run. No secret or caller data is in this report.
