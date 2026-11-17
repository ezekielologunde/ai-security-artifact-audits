# Respect an explicitly selected remote-code flag

17 November 2026, after a source-informed controlled counterexample reproduced an unwarranted finding. This is an implementation correction, not independent natural evaluation or a new research contribution.

Observed case: a snapshot selects AutoModel with `trust_remote_code: false`; its README contains a disabled-code call for the target model and an enabled-code call for another model. The current implementation uses a README-wide True match and reports the selected path as enabling custom code. The selected explicit Boolean must not be overridden by a different README example.

Correction contract: when present, `loading_path.trust_remote_code` must be a JSON Boolean. Explicit false prevents a README-wide True match from establishing selected-path custom-code use. Keep the document-level match visible as evidence and record the selected value separately. False does not establish successful loading or safety, does not override pickle exposure, and need not make a custom-mapped claim consistent. True or an absent flag does not independently authenticate a README example's target, so retain the existing README-association limitation explicitly rather than claiming complete call binding.

Preserve the pre-correction code and controlled counterexample. Check disabled-path behavior, an enabled-path positive control, independent pickle exposure and invalid flag types. Compare all prior fields except the new selected-flag evidence field across the original 36 cases and five modes; retain the original published controlled release unchanged. No models, scanners, deserialization or repository code execution.
