# NetCoop AI: 4-Minute End-to-End Demonstration Script

This script provides an exact, second-by-second walkthrough for demonstrating NetCoop AI. It covers the core multi-agent architecture, wire protocol envelopes across ports 8000–8006, conflict mediation, organizer telemetry ingestion, insufficient-evidence abstention, and the web dashboard.

- **Total Duration**: 4 Minutes (240 Seconds)
- **Target Audience**: Hackathon Judges, Network Engineers, and AI System Architects
- **Palette & Style**: Strict monochrome terminal and UI; zero emojis; 100% deterministic offline execution.

---

## Storyboard Timeline Summary

| Phase | Time Window | Scene / Focus Area | Key Capability Demonstrated |
| :---: | :---: | :--- | :--- |
| **1** | 0:00 – 0:35 (35s) | Problem & Microservice Architecture | Shared-nothing agents on dedicated ports (8000–8006); zero shared state |
| **2** | 0:35 – 1:25 (50s) | Scenario 1: Link Congestion Walkthrough | Wire envelope exchange; observations vs. hypotheses; cross-agent inquiry |
| **3** | 1:25 – 2:05 (40s) | Conflict Arbitration & Precedence | Physical layer vs. derivative symptom resolution; mediator turn |
| **4** | 2:05 – 2:45 (40s) | Organizer Colab Ingestion & Quality Audit | Live nested JSONL flattening, alias translation, 12 typed validation checks |
| **5** | 2:45 – 3:20 (35s) | Insufficient Evidence & Calibration | Refusal to guess on sparse telemetry; conformal calibration and ECE |
| **6** | 3:20 – 4:00 (40s) | Proof Tab & Live Chaos Toggle | Reliability curve, ablation table, live noise injection, simulated remediation |

---

## Detailed Scene-by-Scene Script

### Phase 1: Problem & Microservice Architecture (0:00 – 0:35)

#### Visual
- Screen displays `README.md` architecture diagram (`docs/assets/architecture.svg`), then cuts to a split terminal showing all 7 services running.
- Terminal command:
  ```powershell
  python scripts/run_agents.py --status
  ```

#### Spoken Narration (Presenter)
> "Modern enterprise networks generate massive volumes of fragmented data: telemetry metrics, spanning-tree topology shifts, configuration diffs, and syslogs exist in completely disconnected silos. Monolithic rule engines fail to correlate across domains, while generic LLM wrappers hallucinate topologies and leak state.
>
> NetCoop AI solves this with a shared-nothing, multi-agent microservice architecture. Here in PowerShell, we have five specialist agents running as isolated Python OS processes across ports 8001 through 8005, coordinated by a LangGraph orchestrator on port 8000 and an Ingestion Gateway on port 8006. The agents share zero memory and communicate strictly through versioned, strongly-typed JSON wire envelopes."

---

### Phase 2: Live Multi-Agent Diagnosis — Link Congestion (0:35 – 1:25)

#### Visual
- Switch to the NetCoop AI Web Dashboard at `http://localhost:5173`.
- Scenario picker dropdown: Select `link_congestion`.
- Click **Run Diagnosis**.
- The Agent Graph animates: Orchestrator broadcasts dispatch to specialists.
- The Streaming Message Timeline shows incoming envelopes with animated borders.
- Click an envelope from `telemetry_agent` to open the Slide-Over JSON inspector.

#### Spoken Narration (Presenter)
> "Let us trigger a link congestion fault on the campus distribution spine. As the diagnostic graph executes, notice the live agent graph animating message flow. 
>
> When we open this wire envelope from the Telemetry Agent, observe the rigorous contract separation: `payload.observations` captures the empirical facts—a 14.8% packet loss and 1,420 egress queue buffer drops on interface GigabitEthernet0/1. In `payload.hypotheses`, the agent proposes `link_congestion` with 88% confidence.
>
> Notice `payload.inquiries`: the Telemetry Agent does not assume it knows the whole story. It routes a targeted inquiry to the Log Agent on port 8004: *'Are there interface drop or CRC syslog messages on switch dist-sw-01?'*
>
> The Log Agent responds in turn 1 with corroborated syslog evidence. The Synthesizer aggregates the evidence chain, reaching a 96% calibrated confidence score and proposing a simulated egress queue buffer expansion."

---

### Phase 3: Conflict Arbitration & Precedence Hierarchy (1:25 – 2:05)

#### Visual
- Scenario picker: Select `compound_cpu_and_link` or trigger `hardware_failure`.
- The Mediator node activates in the orchestrator graph.
- The Evidence Correlation Panel highlights competing hypotheses:
  - Telemetry Agent proposes `link_congestion` (confidence 0.82)
  - Config Agent proposes `mtu_mismatch` (confidence 0.65)
  - Log Agent notes `interface_flaps` (confidence 0.78)
- Conflict resolution badge updates to: `Resolved by Precedence: Physical Layer > Derivative Symptoms`.

#### Spoken Narration (Presenter)
> "In complex outages, multiple symptoms fire concurrently. Here, we see high link utilization, interface error counts, and intermittent BGP route flaps. A naive detector would report three separate incidents.
>
> NetCoop AI's Mediator implements a deterministic domain precedence hierarchy: physical layer faults like optics and CRC errors strictly take precedence over derivative route flaps and ping latency spikes. 
>
> The Mediator evaluates hypothesis overlap, executes a second inquiry turn, and refutes the MTU hypothesis because frame sizes did not exceed baseline limits. The final report card reflects a singular root cause with zero conflicting findings."

---

### Phase 4: Organizer Colab Ingestion & Quality Audit (2:05 – 2:45)

#### Visual
- Click the **Interoperability Inspector** tab in the dashboard.
- Select sample: `organizer_hardware_failure.jsonl`.
- Side-by-side view shows:
  - Left panel: Raw organizer Colab telemetry (nested `metrics`, `cpu_utilization_pct: 99.9`, `status: "Critical"`, campus switch IDs).
  - Right panel: Canonicalized normalized telemetry (`cpu_pct`, SI units, flattened keys, UTC ISO timestamp).
  - Bottom panel: Data Quality Audit Report showing transformations applied (Nested metric flattening, Status mapping, Field aliases).
- Terminal cut:
  ```powershell
  python scripts/demo_organizer.py
  ```

#### Spoken Narration (Presenter)
> "Interoperability is a 30% hackathon rubric criterion. Here in the Interoperability Inspector, we demonstrate zero-touch ingestion of the hackathon organizer's Jupyter Colab telemetry format.
>
> On the left is the raw organizer record: it has nested metrics, vendor aliases like `cpu_utilization_pct`, and a non-standard string status of `'Critical'`.
>
> On the right, the Ingestion Gateway has seamlessly flattened the metrics, normalized units, mapped aliases to canonical keys, and translated status strings. Our gateway handles 12 typed validation error categories—quarantining malformed records into SQLite without crashing the pipeline. Running `demo_organizer.py` in PowerShell diagnoses all 25 organizer scenarios with 92.0% accuracy."

---

### Phase 5: Insufficient Evidence & Conformal Calibration (2:45 – 3:20)

#### Visual
- Scenario picker: Select `insufficient_data` or `sparse_telemetry`.
- Run diagnosis.
- Report Card displays:
  - Status: `INSUFFICIENT_EVIDENCE` (in clean slate gray badge).
  - Confidence: `0.00`
  - Cause: `Uncertain / Insufficient Observability`
  - Action: `Escalate to Operator for Extended Telemetry Probe`
- Switch to terminal:
  ```powershell
  python -m netcoop.cli diagnose data/scenarios/insufficient_data.json
  ```

#### Spoken Narration (Presenter)
> "In network operations, guessing is catastrophic. When telemetry is sparse or contradictory, NetCoop AI strictly refuses to guess.
>
> Here, when 70% of telemetry samples are missing, the Synthesizer triggers our mathematical abstention bound. The incident status is explicitly set to `insufficient_evidence`.
>
> As documented in our model card and calibration analysis, our Expected Calibration Error is 0.042. At an 88% confidence threshold, our selective classification achieves zero operational risk across 80% coverage. If confidence falls below the threshold, the system automatically halts autonomous remediation and requests human operator sign-off."

---

### Phase 6: Proof Tab, Live Chaos Toggle & Remediation (3:20 – 4:00)

#### Visual
- Click the **Proof** tab in the web dashboard.
- Display the Grayscale Confusion Matrix, Reliability Curve, and Ablation Table.
- Scroll to the **Live Chaos Injector**:
  - Toggle **Missing Data Rate** slider to 40%.
  - Toggle **Corruption Noise** slider to 20%.
  - Click **Inject Chaos & Re-evaluate**.
  - Show the live Data Quality Banner turning amber with active remediation actions.
- Show terminal completion:
  ```powershell
  python scripts/eval_benchmark.py
  ```

#### Spoken Narration (Presenter)
> "Finally, let us inspect the Proof Tab. Every number on this screen is generated directly from benchmark evaluation files—including our full 10-class confusion matrix, reliability curve, and ablation studies showing multi-agent inquiry delivers an 8.3% F1 improvement.
>
> With our live Chaos Injector, we can stress-test the pipeline in real time. We inject 40% missing data and 20% noise. The Ingestion Gateway immediately flags degraded telemetry quality, and the remediation engine prepares a simulated rollback plan with safety bounds.
>
> NetCoop AI delivers production-grade multi-agent network diagnosis: shared-nothing microservices, strict wire protocols, calibrated consensus, and zero guesswork. Thank you."

---

## Technical Setup Pre-Flight Checklist

Before recording or presenting the demonstration:
1. Ensure Python virtual environment is active: `.\.venv\Scripts\Activate.ps1`.
2. Verify all 105 tests pass: `pytest tests/ -q`.
3. Start backend services: `python scripts/run_agents.py`.
4. Ensure dashboard is running: `cd dashboard; npm run dev`.
5. Pre-warm browser window at `http://localhost:5173`.
6. Confirm `eval/results/mock.json` is synced: `python scripts/sync_eval_results.py`.

