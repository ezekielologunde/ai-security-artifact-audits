# OpenCode native permission/file-write conformance replay

This is a reproducibility supplement for documented behavior, not a new defense, vulnerability or standalone paper. Seven authored conditions use the unchanged OpenCode v2.3.0 Windows binary, an authored scripted local OpenAI-compatible provider and native built-in write. Physical readback distinguishes requested writes from effects. No real inference model or paid provider is used.

Use Windows, Python3.12, Git on PATH and psutil7.2.2. From a fresh extraction, run:

    python -m pip install -r requirements.txt
    python run_replay.py --binary C:/path/to/opencode.exe

Download the official baseline release separately from https://github.com/anomalyco/opencode/releases/download/v2.3.0/opencode-windows-x64-baseline.zip. ZIP SHA256:a3abde3f736a1b51acb28466001333189184507096cb2fe0d684fe822cbd37ec. Extracted EXE SHA256:2359208e2f81539fd16eb755a4d8a747e87c6fd5cd59a49bb552f8a610d33eb9. Native binary and archive are intentionally not bundled. The wrapper verifies the EXE before executing it.

The replay creates only its research work directories, fixture Git repositories and local native database. It starts password-protected loopback OpenCode and loopback scripted-provider servers, and stops the owned process tree. Configuration roots and inherited provider credentials are isolated, but this is not an OS sandbox or a verified zero-network-access environment. OpenCode may retrieve its normal metadata. No existing user approval database is intentionally used.

Read the protocol and amendment. An initial calibration run expected idle after rejection and stopped; native completed aborted-tool errors were observed instead. The amended confirmation accepts explicit completed tool errors separately from idle. It does not claim session quiescence, restart durability or in-flight revocation. Calibration is not added to confirmation counts. Generated native prompts/tool descriptions in recorded evidence retain the upstream MIT terms.

Stable comparisons exclude generated identifiers, ports, timestamps and process IDs. All seven complete native tool observations and physical contents must match EXPECTED_OBSERVATIONS.json. Output is written under results and work; use a new extraction to replay again. No automatic deletion occurs. A second execution is a repeat of these conditions, not seven additional independent tasks or external scientific validation.

Authored scripts: MIT (LICENSE_CODE.txt). OpenCode source-derived descriptions and native protocol output: upstream MIT (LICENSE_OPENCODE.txt), source tag a6b15d33daf6ab7d35569f6d711fdb630b9f04e7. Authored report terms elsewhere in the collection are CC BY4.0. This supplement contains no upstream binary, native database, real credential or model weights.
