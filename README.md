# Documentation claim auditor

An offline, deterministic, standard-library-only CLI for checking documentation
claims about dictionary forms against static source evidence. Requires version
3.9 or newer of the interpreter. No network, telemetry, or file writes occur
during a scan.

## Install and run

```sh
python3 -m pip install .
lemmatization-claim-audit --version
lemmatization-claim-audit audit .
python3 -m lemmatization_claim_audit audit . --json
python3 -m lemmatization_claim_audit audit . --verbose --ignore vendor/ --ignore generated/
python3 -m lemmatization_claim_audit audit . --fail-on medium
python3 -m unittest discover
python3 -m build
```

The repository argument defaults to the current directory. Prefix exclusions
are repeatable and use repository-relative paths. Verbose decisions go to
standard error. JSON output is an array; each finding includes an identifier,
severity, path, matched phrase, verdict, and message.

Exit 0 means PASS at the selected threshold, exit 2 means FAIL, and exit 1
means a usage or input/output error. The default threshold is high; medium
also fails on test documentation findings. A passing result may still contain
medium findings. The reported version is 0.1.0.

```text
documented-lemmatization-claim-false HIGH
documented-no-lemmatization-claim-false HIGH
documented-lemmatization-claim-false MEDIUM
```

## Scope and interpretation

The scanner reads root README.md and Markdown files recursively under docs/.
Markdown fixtures under any tests/ directory can produce medium findings.
Triple-backtick fenced blocks are excluded; inline code remains prose.
Phrases match exact case-insensitive substrings, longest first, without
hyphen normalization. Negative spans are removed before positive matching.
Positive claims without source evidence fail; negative claims with evidence
fail. The source scan covers all source modules recursively, excluding Git
metadata, bytecode caches, and virtual environments. Syntax-invalid source
provides no evidence. Unreadable scanned input is an error.

Evidence is determined within each module using an AST, imported aliases,
constructor/instance pairs, calls, and canonical word form accessors. Local
function and class definitions shadow imported route names throughout that
module. Imports, strings, comments, subprocess commands, unrelated text
processing, and pairs split across modules do not establish evidence.

## Differentiation

The following neighboring tools check text splitting, per-token word-class
labels, typed entity spans, and head-dependent relations, respectively.
This tool checks claims about dictionary forms. Those operations alone cannot
establish evidence for the checked feature.

```text
tokenization-claim-audit
part-of-speech-tagging-claim-audit
named-entity-recognition-claim-audit
dependency-parsing-claim-audit
```

## Limitations

Static pattern matching is not semantic judgement. Exact phrases do not cover
paraphrases. Evidence indicates a recognized source pattern, not correctness,
execution, model availability, or behavior on every input. Dynamic imports,
reflection, and cross-module value tracking are outside the analysis.
The shared attribute below counts even on an unrelated object; this can
produce false evidence. Accessor evidence alone needs no constructor pair.

```text
.lemma
.lemma_
```

The license is MIT. Both source and wheel distributions use the standard
setuptools build backend.
