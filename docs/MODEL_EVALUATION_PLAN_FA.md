# Shared experiment for development model selection

This proposal originated with CL and retains useful DEEP cost-evaluation advice. It does not preselect a winner or report an executed comparison. The actual experiment remains `NOT_RUN`.

## Experimental design

Freeze the specification, environment, permitted tools, cost/time budgets, criteria, and independent tests first. Two or three models should work in separate directories with identical inputs and tools. Record exact model identifiers, date, reasoning settings, instruction revision, and source revision. Give equal correction opportunities; time to first passing result is not the sole metric.

| Representative task | Measurement | Evidence |
|---|---|---|
| Adapter contract and mock adapter | Simplicity, capability compliance, output failures | Contract checks, incomplete input, uncertainty |
| Pure decision and late result | Constraint compliance, stale-operation rejection | Independent forbidden-state and stale-revision tests |
| Multi-file defect fix | Regression preservation, handoff quality | Regression results and evidence-backed continuation notes |

Use common specifications and public tests; keep some negative cases independent of model-generated code/tests. Select tasks only when their roadmap scope is authorized. This plan does not authorize early product phases or transferring private data/secrets to another service.

Record actual execution, review defects, out-of-scope changes, unnecessary dependencies, elapsed time, tokens, and observed cost for each attempt. An unsupported claim that tests passed earns no passing result. Repeated trials can reduce chance effects when budget permits. A small task gives limited evidence, not a universal winner.

A second reviewer, preferably another model or researcher, should use independent tests. A different model does not by itself establish independent errors or eliminate bias. Disclose same-author review in a separate pass. This document records no automatic dispatch to another model and no such review result.

Cheaper models may handle lower-risk work only with the same quality requirements. Recovery and privacy testing are not assumed to be simple or low-risk. Include correction and review cost; token prices or open-source availability cannot establish an 80–95 percent saving for the whole project.
