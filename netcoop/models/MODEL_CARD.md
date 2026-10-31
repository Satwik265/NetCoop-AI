# NetCoop AI Model Card: Hybrid Rule-Classifier & LLM Bridge

## 1. Model Details

- **Model Name**: NetCoop Multi-Agent Hybrid Classifier & Mediator
- **Version**: 1.0.0
- **Type**: Multi-Agent Decision Graph + Isotonic Calibrated Heuristics + Optional LLM Synthesis
- **Developers**: Team inSANE MITRA (IIT Bhubaneswar Hackathon)
- **License**: MIT License
- **Framework**: LangGraph, Python 3.12/3.13, Pydantic v2

---

## 2. Intended Use

- **Primary Application**: Multi-agent network fault diagnosis and automated simulated remediation planning across enterprise campus fabrics.
- **Input Modalities**: Time-series telemetry, topology link matrices, device configuration diffs, BGP/STP routing states, and syslog event streams.
- **Output**: Calibrated fault hypotheses with probabilistic confidence scores, supporting/refuting evidentiary chains, and simulated rollback plans.
- **Out of Scope**: Direct execution of unverified commands on physical production hardware without human operator approval.

---

## 3. Architecture & Arbitration

The system employs a shared-nothing, multi-agent process architecture:
1. **Specialist Agents**: Five isolated microservices (Telemetry, Topology, Config, Log, Synthesizer) evaluate domain anomalies.
2. **Deterministic Correlation Engine**: Strict threshold evaluation and cross-domain correlation rules.
3. **Precedence Hierarchy**: Physical layer (CRC/optics) and buffer queue saturations take precedence over derivative route flaps and transient ping jitter.
4. **Offline Determinism**: Full operational pipeline runs offline with zero LLM dependence.
5. **Optional LLM Bridge (Gemini)**: Invoked strictly for executive summary formatting and natural-language debriefs; falls back gracefully when offline.

---

## 4. Calibration & Performance

- **In-Distribution Accuracy**: 98.5%
- **Held-Out (Non-Gaussian Noise) Accuracy**: 93.3%
- **Organizer Telemetry Accuracy**: 92.0%
- **Overall Macro F1**: 0.952
- **Expected Calibration Error (ECE)**: 0.042
- **Brier Score**: 0.038
- **Zero Risk Coverage**: 80% coverage at 88% confidence threshold.

---

## 5. Limitations & Caveats

- **Exchangeability Assumption**: Calibrated confidence scores assume operational telemetry distribution aligns with reference benchmarks.
- **Narrow Organizer Coverage**: Organizer evaluation dataset is constrained to single-device campus distribution telemetry snapshots.
- **Abstention Policy**: When corroboration is missing or confidence is below 50%, the model strictly returns `insufficient_evidence` without guessing.

