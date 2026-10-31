---
layout: default
title: Droso project notes
---

# Droso

[![Tests: 621 passed · 11 skipped](https://img.shields.io/badge/Tests-621%20passed%20%C2%B7%2011%20skipped-1a7f37?style=flat-square&labelColor=0d1117)](STATE.html)
[![Held-out 24: 19/24 organ only](https://img.shields.io/badge/Held--out%2024-19%2F24%20organ%20only-0a3069?style=flat-square&labelColor=0d1117)](STATE.html)
[![Guards: 8/8 · 1.00 warm / cold](https://img.shields.io/badge/Guards-8%2F8%20%C2%B7%201.00%20warm%20%2F%20cold-5b2d8e?style=flat-square&labelColor=0d1117)](STATE.html)
[![Core Dataset: BANC v888](https://img.shields.io/badge/Core%20Dataset-BANC%20v888-7d4e00?style=flat-square&labelColor=0d1117)](https://doi.org/10.7910/DVN/7WTH1N)
[![License: MIT](https://img.shields.io/badge/License-MIT-24292f?style=flat-square&labelColor=0d1117)](https://github.com/SebSilent/Droso/blob/main/LICENSE)

<p class="eyebrow">Project notes</p>

Notes for a hybrid agent: a sparse associative memory bound to a small language
model, with a connectome layer for housekeeping. The pages below are dated logs,
design records and measurements. Figures in them name the file or commit they
came from.

<ul class="doc-list">
  <li>
    <a href="STATE.html">Repository state</a>
    <span class="doc-sub">Factual inventory: what is in the tree, what each harness does, and the last recorded numbers with the commit they were measured at.</span>
  </li>
  <li>
    <a href="selection_design.html">Selection design</a>
    <span class="doc-sub">Contract for the generational harness: the genome, the fitness tuple, and the battery it is scored on.</span>
  </li>
  <li>
    <a href="archive/experiment_log.html">Experiment log (archive)</a>
    <span class="doc-sub">Historical record of experiments and measurements, written by prior agents. Conclusions in it are theirs, not established fact.</span>
  </li>
  <li>
    <a href="benchmark_findings.html">Benchmark findings</a>
    <span class="doc-sub">Failure analysis of the warm scripts, with a 2026-10-27 addendum on where those failures stood then.</span>
  </li>
  <li>
    <a href="cross_session_design.html">Cross session design</a>
    <span class="doc-sub">Design note on cross-session recall: graded freshness restricted to who said it, and the measurements behind it.</span>
  </li>
  <li>
    <a href="mine_criteria.html">Mining criteria</a>
    <span class="doc-sub">Frozen contract for tools/mine_primitives.py: source corpus, what counts as a reusable primitive, verifier standard, admission, enumeration budget.</span>
  </li>
  <li>
    <a href="archive/role_chain_proposal.html">Role chain proposal (archive)</a>
    <span class="doc-sub">Historical proposal, not applied. Its raw input files were deleted; kept as a record.</span>
  </li>
</ul>